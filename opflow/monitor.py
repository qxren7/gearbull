#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: ../zhongjing/monitor.py
Date: 2017/04/12 
"""

import os
import sys
import logging

from django.utils import timezone

from fuxi_framework import framework
from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.models import FuxiActionRuntime
from fuxi_framework.job_engine import runtime_manager
from fuxi_framework.common_lib import config_parser_wrapper
from fuxi_framework.common_lib import log


from zhongjing.host import Ultron
from zhongjing.models import FailLog
from zhongjing.models import JsonData

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
log.init_log("%s/log/monitor" % CUR_DIR)
logger = logging.getLogger("monitor")
conf = config_parser_wrapper.ConfigParserWrapper("%s/conf/zhongjing.conf" % CUR_DIR)

FAIL_TASK_KEY = 'zhongjing_fail_timeout_tasks'

class Monitor(framework.BaseMonitor):
    """
    TODO
    """
    def __init__(self):
        """
        TODO
        """
        pass

    def get_job_info(self, job_id):
        """
        job执行进度获取接口

        :param:
        :return:
        """
        logger.info("query job info, job_id=[%s]" % job_id)

    def get_task_info(self, task_id):
        """
        task执行进度获取接口

        :param:
        :return:
        """
        logger.info("query task info, task_id=[%s]" % task_id)
        task = FuxiTaskRuntime.objects.get(task_id=task_id)
        job = FuxiJobRuntime.objects.get(job_id=task.job_id)
        actions = FuxiActionRuntime.objects.filter(task_id=task.task_id).order_by("seq_id")
        is_task_succ = True
        action_states = [a.state for a in actions]
        if "RUNNING" in action_states:
            
            if int((timezone.now() - task.start_time).total_seconds()) > int(task.timeout):
                logger.info("task timeout, task_id=[%s]" % task.task_id)
                task_info = {"state":"TIMEOUT", "finish_time": timezone.now()}

                #runtime_manager.update_task_info(job.job_type, task, task_info)

                self._save_fail_tasks_data([task.task_id, task.entity_name, task_info])

                # 当task被设置为TIMEOUT时，对应的action, 如果状态不为FAILED or SUCCESS,  也应该设置为TIMEOUT
                #for action in actions:
                #    if action.state in ['FAILED', 'SUCCESS']:
                #        continue
                #    action.state = 'TIMEOUT'
                #    action.save()
                    
            return

        if "FAILED" in action_states:
            task_info = {"state": "FAILED", "finish_time": timezone.now()}
            runtime_manager.update_task_info(job.job_type, task, task_info)
            self._save_fail_tasks_data([task.task_id, task.entity_name, task_info])
            return

        _action_states = list(set(action_states))
        if "SUCCESS" in _action_states and len(_action_states) == 1:
            task_info = {"state":"SUCCESS", "finish_time": timezone.now()}
            runtime_manager.update_task_info(job.job_type, task, task_info)

    def on_job_state_change(self, job, state):
        """
        job状态改变的后置动作

        :param state:
        :return:
        """
        logger.info("on_job_state_change, job_id=[%s]" % job.job_id)
        if state == 'TIMEOUT':
            self._save_fail_tasks_data([job.job_id, 'job', ''])
            tasks = FuxiTaskRuntime.objects.filter(job_id = job.job_id, state = "RUNNING")
            for task in tasks:
                logger.info("update task state to TIMEOUT, since job has timetout."
                            "job_id=[%s], task_id=[%s]" % (job.job_id, task.task_id))
                task_info = {"state":"TIMEOUT", "finish_time": timezone.now()}
                runtime_manager.update_task_info(job.job_type, task, task_info)
            return
            

    def on_task_state_change(self, task, state):
        """
        task状态改变的后置动作

        :param state:
        :return:
        """
        logger.info("on task state change, task_id=[%s], state=[%s]" % (task.task_id, state))

        # 保存机器操作超时后，其执行层错误日志
        if state == 'TIMEOUT':
            u = Ultron()
            msg = u.host_state(task.entity_name)
            job = FuxiJobRuntime.objects.get(job_id = task.job_id)
            f = FailLog(task_type='job_timeout', entity=task.entity_name, 
                    reason=msg, job_id=job.job_id)
            f.save()
            logger.error('save job_timeout log, jobid: %s' % job.job_id)
            logger.error(msg)
            return
 


    def on_action_state_change(self, action, state):
        """
        action状态改变的后置动作

        :param state:
        :return:
        """
        logger.info("on action state change, action_id=[%s], state=[%s]" % (
            action.action_id, state))
 
    def _save_fail_tasks_data(self, data):
        fail_tasks_data, _ =JsonData.objects.get_or_create(key=FAIL_TASK_KEY)
        fail_tasks = fail_tasks_data.json_data
        fail_tasks.append(data) 
        fail_tasks_data.json_data = fail_tasks
        fail_tasks_data.save()
    
