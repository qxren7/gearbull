# -*- coding: utf-8 -*-

import traceback

from . import global_setttings

from WorkFlow import exceptions

logger = global_setttings.get_logger("states.log")

# 为了兼容子系统中老的代码，这部分暂时保留
STATES = [
    "NEW",
    "INIT",
    "READY",
    "LAUNCHING",
    "RUNNING",
    "PAUSED",
    "CANCELLED",
    "SUCCESS",
    "FAILED",
    "TIMEOUT",
    "SKIPPED",
]


class JobStatus(object):
    """
    job状态
    """
    WAIT_CONFIRM = "WAIT_CONFIRM"
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
    ERROR = "ERROR"

    FINISH_STATES = [SUCCESS, FAILED, TIMEOUT, CANCELLED, SKIPPED, TIMEOUT]
    UNFINISH_STATES = [
        WAIT_CONFIRM, NEW, INIT, READY, LAUNCHING, RUNNING, PAUSED
    ]
    REDO_STATES = [CANCELLED, FAILED, TIMEOUT]


def on_job_state_change(job, state):
    # ImportError: cannot import name Job
    from WorkFlow.models import Job
    from django.utils import timezone

    if not isinstance(job, Job):
        raise exceptions.WFTypeMismatch

    from WorkFlow.models import Task

    logger.info("on_job_state_change, job_id=[%s], state=[%s]" %
                (job.id, state))
    if state == "TIMEOUT" or state == "FAILED":
        # self._save_fail_tasks_data([job.job_id, 'job', ''])
        tasks = Task.objects.filter(job_id=job.id, state="RUNNING")
        for task in tasks:
            logger.info(
                "update running task state to %s, since job has timetout."
                "job_id=[%s], task_id=[%s]" % (state, job.id, task.id))
            task_info = {"state": state, "finish_time": timezone.now()}
            task.update_task_info(task_info)
        return


def on_task_state_change(task, state):
    from WorkFlow.models import Action
    from django.utils import timezone

    # 保存机器操作超时后，其执行层错误日志
    if state == "TIMEOUT" or state == "FAILED":
        logger.info("timeout action id=[%s]" % task.id)

        actions = Action.objects.filter(task_id=task.id, state="RUNNING")
        for action in actions:
            logger.info(
                "update running action state to %s, since task has timetout."
                "task_id=[%s], action_id=[%s]" % (state, task.id, action.id))
            action_info = {"state": state, "finish_time": timezone.now()}
            action.update_action_info(action_info)
        return


def on_action_state_change(action, state):
    pass
