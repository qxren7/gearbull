#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import copy
import logging
import requests
import datetime
import traceback
import threading
from threading import Thread
from django.db import connection
from django.utils import timezone

from . import global_setttings

from WorkFlow.models import Job
from WorkFlow import exceptions
from WorkFlow.models import Task
from WorkFlow import action_trees
from WorkFlow.states import JobStatus

logger = global_setttings.get_logger("analyzer.log")


def analyze_execute(job):
    analyze(job)


def analyze(job):
    if not isinstance(job, Job):
        raise exceptions.WFTypeMismatch
    try:
        generate_plan(job)
        state_update_time = timezone.now()
        info = {"state": "READY", "state_update_time": state_update_time}
        logger.info(
            "job_id=[%s], generate tasks plan done, update state=[%s]" %
            (job.id, info))
        job.update_job_info(info)
    except Exception as e:
        logger.error(traceback.format_exc())
        msg = "job_id=[%s], update job state error in analyze, error=[%s]" % (
            job.id, e)
        logger.fatal(msg)
        info = {"state": "ERROR"}
        error = {"analyze": msg}
        job.errors.update(error)
        job.save()
        job.update_job_info(info)
        raise Exception(msg)


def generate_plan(job):
    _plan = []

    key = "%s_timeout" % job.task_type
    task_timeout = 0

    mode = job.params["execute_mode"]
    entities = job.params["entities"]

    level_indexs = list(entities.keys())
    level_indexs.sort()

    for level in level_indexs:
        level_name = "level_%s" % (level)
        entity_list = entities[level]
        entity_list = filter_duplicate(entity_list)
        if len(entity_list) <= 0:
            continue  # 如果没有entity, 说明都重复了，跳过

        hosts_groups = []
        if mode == "roll_mode":
            hosts_groups = [entity_list]
        elif mode == "batch_mode":
            group_len = (job.concurrency if job.concurrency <= len(entity_list)
                         else len(entity_list))
            hosts_groups = [
                entity_list[x:x + group_len]
                for x in range(0, len(entity_list), group_len)
            ]

        stage = bulk_grouping(job, level_name, hosts_groups)
        logger.info("hosts_groups=[%s], stage=[%s] " % (hosts_groups, stage))
        _plan.append(stage)

    job.tasks_plan = _plan
    job.save()


def filter_duplicate(entity_list):
    # TODO tmp disable filter_duplicate
    return entity_list

    result = []
    for e in entity_list:
        tasks = Task.objects.filter(entity_name=e,
                                    state__in=JobStatus.UNFINISH_STATES)
        if tasks.count() <= 0:
            result.append(e)
        else:
            logger.info("host=[%s] is duplicate, remove" % e)

    return result


def bulk_create_tasks_actions(job, hosts_list, task_timeout):
    task_ids = bulk_gen_tasks(job, hosts_list, "Host",
                              task_timeout).values_list("id", flat=True)
    return task_ids


def __gen_task_action(task_ids, job, host, task_timeout):
    _task = __gen_task(job, host, "Host", task_timeout)
    task_ids.append(_task.id)
    _extra_params = copy.copy(job.params)
    _extra_params["job_id"] = job.id
    __gen_actions(job, _task, extra_params=_extra_params)


def bulk_grouping(job, level_name, hosts_groups):
    stage = {}
    task_timeout = job.timeout
    for index, hosts_list in enumerate(hosts_groups):
        task_ids = bulk_create_tasks_actions(job, hosts_list, task_timeout)
        stage_name = "%s_stage_%s" % (level_name, index)
        stage[stage_name] = task_ids
    return stage


def __grouping(job, level_name, hosts_groups):
    stage = {}

    task_timeout = job.timeout
    for index, hosts_list in enumerate(hosts_groups):
        task_ids = []
        for host in hosts_list:
            __gen_task_action(task_ids, job, host, task_timeout)

        stage_name = "%s_stage_%s" % (level_name, index)
        stage[stage_name] = task_ids
    return stage


def __gen_task_params(self, job):
    task_info = {
        "task_id": id_generator.gen_task_id(job),
        "job_id": job.job_id,
        "task_priority": "90",
        "threshold": "100",
        "timeout": job.timeout,
        "state": "NEW",
    }
    return task_info


def bulk_gen_tasks(job, hosts_list, entity_type, task_timeout):
    now = datetime.datetime.now()
    tasks = []
    for host in hosts_list:
        t = Task(
            priority="90",
            threshold="100",
            timeout=task_timeout,
            state="NEW",
            entity_type=entity_type,
            entity_name=host,
            job=job,
            create_time=now,
        )
        tasks.append(t)

    Task.objects.bulk_create(tasks)
    new_tasks = Task.objects.filter(create_time=now, job_id=job.id)
    return new_tasks


def __gen_task(job, host, entity_type, task_timeout):
    task_info = {
        "priority": "90",
        "threshold": "100",
        "timeout": task_timeout,
        "state": "NEW",
        "entity_type": entity_type,
        "entity_name": host,
    }

    _task = Task.create_task(job, task_info)
    return _task


def bulk_gen_actions_old(job, tasks, extra_params=None):
    tasks_actionparams_dict = {}
    for t in tasks:
        params = {
            "host": t.entity_name,
            "task_id": t.id,
            "job_id": job.id,
            "timeout": job.timeout,
            "extra_params": extra_params,
        }
        tasks_actionparams_dict[t] = params

    action_trees.bulk_create_trees(job.task_type, tasks_actionparams_dict)


def bulk_gen_actions(job):
    tasks = job.task_set.all()
    tasks_actionparams_dict = {}
    for t in tasks:
        params = {
            "host": t.entity_name,
            "task_id": t.id,
            "job_id": job.id,
            "timeout": job.timeout,
            "extra_params": job.params,
        }
        tasks_actionparams_dict[t] = params

    action_trees.bulk_create_trees(job.task_type, tasks_actionparams_dict)


def gen_actions(job, ):
    action_params = {
        "host": _task.entity_name,
        "task_id": _task.id,
        "job_id": job.id,
        "timeout": job.timeout,
        "extra_params": job.params,
    }

    action_trees.create_trees(job.task_type, _task, action_params)


def __gen_actions(job, _task, extra_params=None):
    action_params = {
        "host": _task.entity_name,
        "task_id": _task.id,
        "job_id": job.id,
        "timeout": job.timeout,
        "extra_params": extra_params,
    }
    action_trees.create_trees(job.task_type, _task, action_params)
