#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import logging
import threading
import traceback

from . import global_setttings

from WorkFlow import exceptions
from WorkFlow.models import Job
from WorkFlow.models import Task
from django.utils import timezone
from WorkFlow.models import Action
from WorkFlow.models import FlowMap
from WorkFlow.states import JobStatus
from WorkFlow.models import ActionTree

from subprocess import Popen, PIPE

from django.db import connection

logger = global_setttings.get_logger("executor.log")

#from gearbull.settings import TASKS_RESULT_REDIS


def execute(_task_id):
    try:
        logger.info("get task and exec task, task_id=[%s]" % _task_id)
        task = Task.objects.get(id=_task_id)

        # 为了让 job 可以重入，对task 的状态做判断，如果不是 NEW，说明已经运行过，应该跳过
        if task.state != "NEW":
            logger.info("task=[%s] has started, ignore it." % _task_id)
            return

        task_info = {"state": "RUNNING", "start_time": timezone.now()}
        task.update_task_info(task_info)
        if task.job.executor == "BashExecutor":
            bash_exec_actions(task)
        elif task.job.executor == "WorkFlowExecutor":
            exec_actions(task)
        else:
            # not support executor
            return False
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.fatal("exec task failed, task_id=[%s] error=[%s]" %
                     (_task_id, str(e)))
    finally:
        connection.close()


def bash_exec_actions(task):
    job = task.job
    action_tree = task.actiontree_set.first()

    actions = task.action_set.all()
    action_ids = []
    action_contents = []

    for a in actions:
        cmd = "echo 'do action=[id:%s, method:%s] for task=[%s]'    " % (
            a.id,
            a.method_name,
            task.id,
        )
        p = Popen(cmd, shell=True, stdout=PIPE)
        cmd = (
            "echo 'do action=[id:%s, method:%s] for task=[%s], subprocess id=[%s]'    "
            % (a.id, a.method_name, task.id, p.pid))
        logger.info("call cmd=[%s] by popen, async command" % cmd)
        info = {"state": "SUCCESS", "finish_time": timezone.now()}
        a.update_action_info(info)
        action_ids.append(a.id)

    action_tree.state = ActionTree.SUCCESS
    action_tree.save()

    result_key = "%s-%s-%s" % (job.juuid, job.id, task.id)
    result_value = (
        "juuid=[%s], job_id=[%s], task_id=[%s], action_ids=[%s], action_contents=[%s], execute done."
        % (job.juuid, job.id, task.id, action_ids, action_contents))
    #TASKS_RESULT_REDIS.set(result_key, result_value)

    return True


def exec_actions(task):
    action_tree = task.actiontree_set.first()
    action_tree.state = ActionTree.RUNNING
    action_tree.save()
    result = action_tree.root.iterate_execute()
    return result
