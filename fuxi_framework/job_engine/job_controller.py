#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: controller.py
Date: 2017/03/30 20:37:15
"""
import os
import sys
import logging
import json
import traceback
from django.utils import timezone
from django.db import connection
from django.apps import apps
import django.core.exceptions

from fuxi_framework.job_engine import runtime_manager
from fuxi_framework.job_engine.runtime_manager import JobStatus
from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.models import FuxiControlInfo
from fuxi_framework.models import FuxiControlState
from fuxi_framework.common_lib import util
from fuxi_framework.common_lib import log

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
logger = logging.getLogger("controller")
if logger.handlers == []:
    log.init_log("%s/../log/controller" % CUR_DIR)

class JobController(object):
    """
    TODO
    """
    VALID_ACTIONS = ["pause", "resume", "cancel"]

    def __init__(self):
        """
        TODO
        """
        pass

    def control(self, action, control_type, user, conditions=None):
        """
        对伏羲平台的全局控制, 干预流程如下：
        1. 如果条件、或者动作不合法，直接返回，不做干预
        2. 在数据库中记录人工干预纪录，包含动作、条件、触发人、时间等信息
        3. 对出于NEW、READY、RUNNING状态的job设置人工干预状态，下次调度时将会根据此状态做出是否调度的决定
        4. 触发各个涉及到的子系统实际执行人工干预动作，具体动作执行逻辑由子系统实现

        :param action: str，具体动作，pause/resume/cancel
        :param control_type: str，要控制的任务范围，取值有all/new/running，代表对所有job、新建的job、运行中的job做控制
        :param user: str，触发人工干预的用户
        :param conditions: dict, 执行动作的目标job的筛选条件, 如：{"cluster":"beijing", prduct="www"}, None表示对所有job执行操作
        :return:
        """
        if conditions is None:
            return

        if action not in self.VALID_ACTIONS:
            logger.error("invalid action, action=[%s]" % action)
            raise util.EFailedRequest("invalid action, action=[%s]" % action)

        self.__set_control_state(action, control_type, conditions)

        control_info = self.__record_control_info(action, user, conditions)
        jobs_to_control = self.__filter_jobs(action, conditions)

        all_jobs = []
        for k, v in jobs_to_control.items():
            if v == []:
                logger.info("job list empty, del it, job_type=[%s]" % k)
                del jobs_to_control[k]
                continue
            all_jobs.extend(v)

        failed_jobs = self.__set_control_flag(action, all_jobs)
        failed_subsystems = self.__control_subsystem(action, jobs_to_control)

        ret = {"failed_jobs":failed_jobs, "failed_subsystems":failed_subsystems}
        result = "finish"
        self.__update_control_info(control_info, result, json.dumps(ret))

        return ret

    def __control_subsystem(self, action, jobs_to_control):
        """
        对伏羲平台的全局控制

        :param action: str，具体动作，pause/resume/cancel
        :param jobs_to_control: dict, 将要干预的job，格式为{"job_type":[job_id]}
        :return:
        """
        failed_subsystems = []
        for job_type, jobs in jobs_to_control.items():
            try:
                module = __import__(job_type + ".controller", fromlist=['Controller'])
            except Exception as e:
                logger.error("import controller error, job_type=[%s], error=[%s]" % 
                            (job_type, str(e)))
                failed_subsystems.append(job_type)
                continue
            controller_module = module.Controller
            controller_obj = module.Controller()
            if hasattr(controller_module, action):
                logger.info("has action, action=[%s]" % action)
                func = getattr(controller_module, action)
                try:
                    func(controller_obj, jobs)
                except Exception as e:
                    logger.error("call subsystem action error, error=[%s]" % str(e))
                    logger.error(traceback.format_exc())
                    failed_subsystems.append(job_type)
                    continue
            else:
                logger.error("subsystem has no control_func, action=[%s], job_type=[%s]" % 
                        (action, job_type))
                failed_subsystems.append(job_type)
                continue

        return failed_subsystems

    def __filter_jobs(self, action, conditions):
        """
        对于用户自定义的查询条件，需要调用各子系统的接口来查询对应的job_id, 因为自定义字段在runtime表中可能没有

        :param conditions: dict类型的查询条件
        :return jobs: dict类型的job结果，key为job_type, value为list类型的job_id列表
        """
        jobs = {}
        job_types = []
        if "job_type" not in conditions:
            raise util.EFailedRequest("job_type is required")
        elif conditions['job_type'] != "all":
            job_types.append(conditions['job_type'])
        else:
            job_types = self.__get_all_subsystems()

        for job_type in job_types:
            conditions['job_type'] = job_type
            try:
                module = __import__(job_type + ".controller", fromlist=['Controller'])
            except Exception as e:
                logger.error("import controller error, job_type=[%s], error=[%s]" %
                             (job_type, str(e)))
                continue
            controller_module = module.Controller
            controller_obj = module.Controller()
            if hasattr(controller_module, "filter_jobs"):
                logger.info("has filter_jobs")
                func = getattr(controller_module, "filter_jobs")
                try:
                    job_list = func(controller_obj, conditions)
                except Exception as e:
                    logger.error("call subsystem filter_jobs error, error=[%s]" % str(e))
                    logger.error(traceback.format_exc())
                    continue
            else:
                logger.error("subsystem has no filter_jobs, job_type=[%s]" % (job_type))
                continue

            jobs[job_type] = []
            for job in job_list:
                if not self.__is_active_job(action, job.state):
                    continue
                jobs[job_type].append(job.job_id)

        return jobs

    def __is_active_job(self, action, state):
        """
        判断一个job当前的状态是否可以被一个干预动作干预

        :param state:
        :return:
        """
        active_status = [JobStatus.RUNNING, JobStatus.LAUNCHING, JobStatus.READY,
                         JobStatus.INIT, JobStatus.NEW]
        if action == "resume" or action == "cancel":
            active_status.append(JobStatus.PAUSED)

        if state in active_status:
            return True
        return False

    def __get_all_subsystems(self):
        """

        :return:
        """
        subsystems = []
        for app in apps.get_app_configs():
            if not isinstance(app.verbose_name, str):
                continue
            subsystems.append(app.verbose_name.lower())

        return subsystems

    def __set_control_flag(self, action, jobs):
        """
        在触发动作前先把对应的job设为对应的状态

        :param action: str, 动作名称
        :param conditions: dict, 要设置的job筛选条件
        :return failed_jobs: 设置失败的job_id列表
        """
        logger.info("set control flag, jobs=[%s]" % str(jobs))
        #对于pause、cancel直接设置为对应的action，对于resume则设置为空字符串
        if action == "resume":
            info = {"control_action":""}
        elif action == "pause":
            info = {"control_action":action}
        elif action == "cancel":
            info = {"control_action":action, "state":JobStatus.CANCELLED}

        failed_jobs = []
        for job_id in jobs:
            job = FuxiJobRuntime.objects.get(job_id=job_id)
            if action == "pause" and job.state == JobStatus.RUNNING:
                info["state"] = JobStatus.PAUSED
            elif action == "resume" and job.state == JobStatus.PAUSED:
                info['state'] = JobStatus.RUNNING
            elif action == "cancel":
                info['state'] = JobStatus.CANCELLED
            try:
                runtime_manager.update_job_info(job, info)
            except Exception as e:
                logger.error("update job control_action failed, error=[%s]" % str(e))
                failed_jobs.append(job.job_id)

        return failed_jobs

    def __record_control_info(self, action, user, conditions):
        """
        记录人工干预历史信息

        :param action:
        :param conditions:
        :return:
        """
        try:
            control_info = FuxiControlInfo(
                    action=action,
                    user = user,
                    trigger_time=timezone.now(),
                    result="",
                    conditions=json.dumps(conditions),
                    detail="")
            control_info.save()
            return control_info
        except Exception as e:
            logger.error("save control info error, error=[%s]" % (str(e)))
            logger.error(traceback.format_exc())
        finally:
            connection.close()
        logger.info("record control info succ")

    def __update_control_info(self, control_info_obj, result, detail):
        """
        记录人工干预历史

        :param control_info_obj: control_info对象
        :param result: 人工干预执行结果
        :param detail: 人工干预执行详情，失败列表
        :return:
        """
        control_info_obj.result = result
        control_info_obj.detail = detail
        control_info_obj.finish_time = timezone.now()
        control_info_obj.save()
        connection.close()

    def __parse_dict_to_sql(self, conditions, table):
        """
        将dict格式的条件转化为sql查询表达式

        :param conditions: dict类型的查询条件
        :param table: 数据库表名
        :return sql: str类型的查询语句
        """
        sql = "select * from %s where " % table
        i = 0
        for k, v in conditions.items():
            if i != 0:
                sql += "and "
            if isinstance(v, int):
                con = "%s=%s " % (k, v)
            else:
                con = "%s='%s' " % (k, v)
            sql += con
            i += 1
        logger.info("parse dict to sql over, sql=[%s]" % (sql))
        return sql

    def __set_control_state(self, action, control_type, conditions):
        """
        """
        job_types = []
        if "job_type" not in conditions:
            raise util.EFailedRequest("job_type is required")
        elif conditions['job_type'] != "all":
            job_types.append(conditions['job_type'])
        else:
            job_types = self.__get_all_subsystems()

        if action == "resume":
            state = 0
        else:
            state = 1

        for job_type in job_types:
            try:
                control_state = FuxiControlState.objects.get(job_type=job_type)
            except django.core.exceptions.ObjectDoesNotExist:
                control_state = FuxiControlState(job_type=job_type)

            if control_type == "new":
                control_state.new_job_state = state
            elif control_type == "running":
                control_state.running_job_state = state
            elif control_type == "all":
                control_state.new_job_state = state
                control_state.running_job_state = state
            else:
                raise util.EFailedRequest("control type invalid")
            control_state.save()

