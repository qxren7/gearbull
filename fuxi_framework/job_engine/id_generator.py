#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: id_generator.py
Date: 2017/04/01 10:24:19

update: marui06
Date: 2017/12/19
"""

import os
import sys
import time
import random
import uuid

from ..common_lib import util

def gen_job_id(job_type):
    """
    生成job_id

    :param job_type: job类型
    :return job_id: 生成的job_id
    """
    job_id = ("%s_%s_%s" % 
            (job_type, 
            time.strftime("%Y%m%d%H%M%S", time.localtime(time.time())), 
            str(uuid.uuid4())[0:8]))
    return job_id


def gen_task_id(job):
    """
    生成task_id

    :param job: task所属的job对象
    :return task_id: 生成的task_id
    """
    task_id = ("%s_%s" % (job.job_id, str(uuid.uuid4())[0:8]))
    return task_id


def gen_action_id(task):
    """
    生成action_id

    :param task: action所属的task对象
    :return action_id: 生成的action_id
    """
    action_id = ("%s_%s" % (task.task_id, str(uuid.uuid4())[0:8]))
    return action_id


def gen_uuid():
    """生成通用uuid
    :return uuid
    """
    return str(uuid.uuid4())

