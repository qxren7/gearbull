#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: executor.py
Date: 2017/04/05 16:32:45
"""

import os
import sys
import json
import logging

from django.utils import timezone

from fuxi_framework import framework
from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.models import FuxiActionRuntime
from fuxi_framework.job_engine import runtime_manager
from fuxi_framework.common_lib import log

from zhongjing.lib import util
from models import JobInfo

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
log.init_log("%s/log/task_executor" % CUR_DIR)
logger = logging.getLogger("task_executor")


class TaskExecutor(framework.BaseTaskExecutor):
    """
    TODO
    """
    def __init__(self):
        """
        TODO
        """
        super(TaskExecutor, self).__init__()

    def exec_actions(self, task):
        """
        一个task内部具体的actions执行逻辑

        :param task: task对象
        :return:
        :raise:
        """

        actions = FuxiActionRuntime.objects.filter(task_id=task.task_id).order_by("seq_id")
        job = FuxiJobRuntime.objects.get(job_id=task.job_id)
        logger.info("exec actions, job_id=[%s], task_id=[%s], actions_ids=[%s]" % (
            job.job_id, task.task_id, actions))
        for action in actions:
            declaration = json.loads(action.action_content)
            mod = __import__(declaration['module'], fromlist=[declaration['class']])
            klass = getattr(mod, declaration['class'])
            instance = klass()
            method = getattr(instance, declaration['method'])
            info = {"state":"RUNNING", "start_time": timezone.now()}
            runtime_manager.update_action_info(job.job_type, action, info)
            try:
                result = method(declaration['params'])
                if result:
                    logger.info("exec action succ, task_id=[%s], action=[%s], entity_name=[%s]" % (
                        task.task_id, action.action_id, task.entity_name))
                    info = {"state":"SUCCESS", "finish_time": timezone.now()}
                    runtime_manager.update_action_info(job.job_type, action, info)
                else:
                    logger.error("exec action=[%s] fail, task=[%s] break off now. "
                                "action=[%s], entity_name=[%s]" % (declaration,
                                    task.task_id, action.action_id, task.entity_name))
                    info = {"state":"FAILED", "finish_time": timezone.now()}
                    runtime_manager.update_action_info(job.job_type, action, info)
                    break
            except Exception as e:
                import traceback
                logger.error(traceback.format_exc())
                break
