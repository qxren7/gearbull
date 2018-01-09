#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: executor.py
Date: 2017/03/30 20:32:58
"""

import os
import sys
import logging

from fuxi_framework.common_lib import util
from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.job_engine import runtime_manager

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
logger = logging.getLogger("scheduler")
if logger.handlers == []:
    log.init_log("%s/log/scheduler" % CUR_DIR)

def execute(job):
    """
    job执行入口，具体执行逻辑为各子系统自定义

    :param job: 待执行任务对象
    :return:
    :rtype:
    :raise:
    """
    if not isinstance(job, FuxiJobRuntime):
        raise util.ETypeMismatch

    job_type = job.job_type
    module = __import__(job_type + ".executor", fromlist=['Executor'])

    executor_module = module.Executor
    executor_obj = module.Executor()
    if hasattr(executor_module, "execute"):
        logger.info("has execute")
        func = getattr(executor_module, "execute")
        func(executor_obj, job)
    else:
        logger.info("has no execute")

