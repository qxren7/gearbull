#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: analyzer.py
Date: 2017/03/30 20:34:36
"""

import os
import sys
import logging
import traceback

from fuxi_framework.common_lib import util
from fuxi_framework.common_lib import log
from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.job_engine import runtime_manager

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
logger = logging.getLogger("scheduler")
if logger.handlers == []:
    log.init_log("%s/log/scheduler" % CUR_DIR)

def analyze(job):
    """
    job的执行决策分析
    具体的分析逻辑由各个子系统实际定义，此处通过反射调用各子系统的逻辑

    :praams job: 待分析的job对象
    :returns:
    """
    if not isinstance(job, FuxiJobRuntime):
        raise util.ETypeMismatch

    job_type = job.job_type
    module = __import__(job_type + ".analyzer", fromlist=['Analyzer'])

    logger.info(module)
    logger.info(module.Analyzer)
    logger.info(dir(module))
    logger.info(dir(module.Analyzer))

    analyzer_module = module.Analyzer
    analyzer_obj = module.Analyzer()
    if hasattr(analyzer_module, "analyze"):
        logger.info("has analyze")
        func = getattr(analyzer_module, "analyze")
        try:
            func(analyzer_obj, job)
        except Exception as e:
            logger.error("analyze error, error=[%s]" % str(e))
            logger.error(traceback.format_exc())
            raise util.EFailedRequest(str(e))
    else:
        logger.error("has no analyze")

