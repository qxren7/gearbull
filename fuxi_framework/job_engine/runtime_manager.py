#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: runtime_manager.py
Date: 2017/04/01 10:05:34
"""

import os
import sys
import logging
import commands
import traceback
from django.db import connection
from django.utils import timezone
import django.core.exceptions

from ..common_lib import util
from ..common_lib import log
from ..models import FuxiJobRuntime
from ..models import FuxiTaskRuntime
from ..models import FuxiActionRuntime
from ..models import FuxiControlState

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
logger = logging.getLogger("scheduler")
if logger.handlers == []:
    log.init_log("%s/../log/scheduler" % CUR_DIR)

#为了兼容子系统中老的代码，这部分暂时保留
STATES = ["NEW", "INIT", "READY", "LAUNCHING", "RUNNING", 
        "PAUSED", "CANCELLED", "SUCCESS", "FAILED", "TIMEOUT", "SKIPPED"]

class JobStatus(object):
    """
    job状态
    """
    NEW = "NEW"
    INIT = "INIT"
    READY = "READY"
    LAUNCHING = "LAUNCHING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    SKIPPED = "SKIPPED"

    FINISH_STATES = [SUCCESS, FAILED, TIMEOUT, CANCELLED, SKIPPED]
    UNFINISH_STATES = [NEW, INIT, READY, LAUNCHING, RUNNING, PAUSED]
    REDO_STATES = [CANCELLED, FAILED, TIMEOUT]

def create_job(runtime_info):
    """
    创建job，在job的runtime表中插入记录

    :param runtime_info: 待创建的job字段信息
    :return job_runtime: 创建之后的job对象
    :raise util.EFailedRequest: 创建失败异常
    """
    (status, ip_addr) = commands.getstatusoutput("hostname -i")
    if "create_time" not in runtime_info:
        runtime_info['create_time'] = timezone.now()

    #对于一键暂停期间内发起的任务，需要自动停住
    control_action = ""
    try:
        control_state = FuxiControlState.objects.get(job_type=runtime_info['job_type'])
        if control_state.new_job_state != 0:
            control_action = "pause"
    except django.core.exceptions.ObjectDoesNotExist:
        pass
    except KeyError as e:
        raise util.EMissingParam("missing params, error=[%s]" % str(e))

    try:
        job_runtime = FuxiJobRuntime(
                job_id=runtime_info['job_id'], 
                job_type=runtime_info['job_type'], 
                job_priority=runtime_info['job_priority'], 
                threshold=runtime_info['threshold'], 
                create_time=runtime_info['create_time'], 
                timeout=runtime_info['timeout'], 
                control_action=control_action,
                user=runtime_info['user'], 
                server_ip=ip_addr, 
                state=runtime_info['state'])
        job_runtime.save()
    except KeyError as e:
        raise util.EMissingParam("missing params, error=[%s]" % str(e))
    except Exception as e:
        logger.error(traceback.format_exc())
        raise util.EFailedRequest(
                "save job runtime info error, error=[%s], runtime_info=[%s]" % (
            str(e), str(runtime_info)))
    finally:
        connection.close()
    logger.info("create job succ, job=[%s]" % job_runtime.job_id)
    return job_runtime


def create_task(runtime_info):
    """
    创建task，在task的runtime表中插入记录

    :param runtime_info: 待创建的task字段信息
    :return task_runtime: 创建之后的task对象
    :raise util.EFailedRequest: 创建失败异常
    """
    option_params = ["entity_type", "entity_name"]
    for param in option_params:
        if param not in runtime_info:
            runtime_info[param] = ""
    if "create_time" not in runtime_info:
        runtime_info['create_time'] = timezone.now()

    try:
        task_runtime = FuxiTaskRuntime(
                task_id=runtime_info['task_id'], 
                job_id=runtime_info['job_id'], 
                task_priority=runtime_info['task_priority'], 
                threshold=runtime_info['threshold'], 
                entity_type=runtime_info['entity_type'], 
                entity_name=runtime_info['entity_name'], 
                create_time=runtime_info['create_time'], 
                timeout=runtime_info['timeout'], 
                state=runtime_info['state'])
        task_runtime.save()
    except KeyError as e:
        raise util.EMissingParam("missing params, error=[%s]" % str(e))
    except Exception as e:
        logger.error(traceback.format_exc())
        raise util.EFailedRequest(
                "save task runtime info error, error=[%s], runtime_info=[%s]" % (
            str(e), str(runtime_info)))
    finally:
        connection.close()
    return task_runtime


def create_action(runtime_info):
    """
    创建action，在action的runtime表中插入记录

    :param runtime_info: 待创建的action字段信息
    :return action_runtime: 创建之后的action对象
    :raise util.EFailedRequest: 创建失败异常
    """
    try:
        action_runtime = FuxiActionRuntime(
                action_id=runtime_info['action_id'], 
                task_id=runtime_info['task_id'], 
                action_content=runtime_info['action_content'], 
                seq_id=runtime_info['seq_id'], 
                timeout=runtime_info['timeout'], 
                state=runtime_info['state'])
        action_runtime.save()
    except KeyError as e:
        raise util.EMissingParam("missing params, error=[%s]" % str(e))
    except Exception as e:
        logger.error(traceback.format_exc())
        raise util.EFailedRequest(
                "save action runtime info error, error=[%s], runtime_info=[%s]" % (
            str(e), str(runtime_info)))
    finally:
        connection.close()
    return action_runtime


def update_job_info(job, info):
    """
    更新job_runtime表的信息

    :param info: dict类型，key为job的属性，value为要更新到的值
    :return:
    """
    logger.info("update job info, job_id=[%s], info=[%s]" % (job.job_id, info))
    is_state_change = False
    if "state" in info:
        job_state = FuxiJobRuntime.objects.get(job_id=job.job_id).state
        if job_state != info['state']:
            is_state_change = True

    for k, v in info.items():
        if hasattr(job, k):
            setattr(job, k, v)
    job.save()
    connection.close()

    if is_state_change:
        on_job_state_change(job, info['state'])


def update_task_info(job_type, task, info):
    """
    更新task_runtime表的信息

    :param info: dict类型，key为task的属性，value为要更新到的值
    :return:
    """
    logger.info("update task info, task_id=[%s], info=[%s]" % (task.task_id, info))
    is_state_change = False
    if "state" in info:
        task_state = FuxiTaskRuntime.objects.get(task_id=task.task_id).state
        if task_state != info['state']:
            is_state_change = True

    for k, v in info.items():
        if hasattr(task, k):
            setattr(task, k, v)
    task.save()
    connection.close()

    if is_state_change:
        on_task_state_change(job_type, task, info['state'])


def update_action_info(job_type, action, info):
    """
    更新action_runtime表的信息

    :param info: dict类型，key为action的属性，value为要更新到的值
    :return:
    """
    logger.info("update action info, action_id=[%s], info=[%s]" % (action.action_id, info))
    is_state_change = False
    if "state" in info:
        action_state = FuxiActionRuntime.objects.get(action_id=action.action_id).state
        if action_state != info['state']:
            is_state_change = True
        
    for k, v in info.items():
        if hasattr(action, k):
            setattr(action, k, v)
    action.save()
    connection.close()

    if is_state_change:
        logger.info("action state change, exec post action, action=[%s]" % action.action_id)
        on_action_state_change(job_type, action, info['state'])


def on_job_state_change(job, state):
    """
    job状态改变时的后置动作

    :params job: 状态改变的job对象
    :params state: job的目标状态
    :returns:
    """
    if not isinstance(job, FuxiJobRuntime):
        raise util.ETypeMismatch

    try:
        job_type = job.job_type
        module = __import__(job_type + ".monitor", fromlist=['Monitor'])
        monitor_module = module.Monitor
        monitor_obj = module.Monitor()
        if hasattr(monitor_module, "on_job_state_change"):
            func = getattr(monitor_module, "on_job_state_change")
            func(monitor_obj, job, state)
        else:
            logger.error("has no on_job_state_change")
    except Exception as e:
        logger.error("on job state change error, error=[%s]" % str(e))
        logger.error(traceback.format_exc())


def on_task_state_change(job_type, task, state):
    """
    task状态改变时的后置动作

    :params job_type: job类型
    :params task: 状态改变的task对象
    :params state: task的目标状态
    :returns:
    """
    if not isinstance(task, FuxiTaskRuntime):
        raise util.ETypeMismatch
    
    try:
        module = __import__(job_type + ".monitor", fromlist=['Monitor'])
        monitor_module = module.Monitor
        monitor_obj = module.Monitor()
        if hasattr(monitor_module, "on_task_state_change"):
            func = getattr(monitor_module, "on_task_state_change")
            func(monitor_obj, task, state)
        else:
            logger.error("has no on_task_state_change")
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("on task state change error, error=[%s]" % str(e))


def on_action_state_change(job_type, action, state):
    """
    action状态改变时的后置动作

    :params job_type: job类型
    :params action: 状态改变的action对象
    :params state: action的目标状态
    :returns:
    """
    if not isinstance(action, FuxiActionRuntime):
        raise util.ETypeMismatch

    try:
        module = __import__(job_type + ".monitor", fromlist=['Monitor'])
        monitor_module = module.Monitor
        monitor_obj = module.Monitor()
        if hasattr(monitor_module, "on_action_state_change"):
            logger.info("has on_action_state_change")
            func = getattr(monitor_module, "on_action_state_change")
            func(monitor_obj, action, state)
        else:
            logger.error("has no on_action_state_change")
    except Exception as e:
        logger.error("on action state change error, error=[%s]" % str(e))
        logger.error(traceback.format_exc())



