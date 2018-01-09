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
import logging
import json
import threading
import time
from enum import Enum

from django.utils import timezone

from fuxi_framework import framework
from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.job_engine import runtime_manager
from fuxi_framework.common_lib import util
from fuxi_framework.common_lib import log
from fuxi_framework.common_lib import config_parser_wrapper

from zhongjing.models import JobInfo
from task_executor import TaskExecutor

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
log.init_log("%s/log/executor" % CUR_DIR)
logger = logging.getLogger("executor")
conf = config_parser_wrapper.ConfigParserWrapper("%s/conf/zhongjing.conf" % CUR_DIR)

class Executor(framework.BaseExecutor):
    """
    TODO
    """
    def __init__(self):
        """
        TODO
        """
        super(Executor, self).__init__()
        self.task_executor = TaskExecutor()

    def execute(self, job):
        """
        job执行入口函数

        :param job: job对象
        :return:
        :raise:
        """
        t = threading.Thread(target=self.__execute_thread, args=(job,))
        t.start()
        
        ### TODO  
        # 多线程测试时，不调用join会导致数据丢失，临时加入join，完成测试，提交时需要删除;同时搞清楚如何不join完成测试
        # join 的时候，会阻塞其他进程，例如 monitor，导致状态跟新不及时，多线程如何测试?
        #t.join()
        ### TODO

    def __execute_thread(self, job):
        """
        具体job执行逻辑
        根据底层执行引擎的不同，job执行分为三类：
        1. 工作流，如：compass、airflow
        2. BJE
        3. 用户自己控制执行流程
        此处，对于机器操作来说，暂时用第三种
        """
        job_info = JobInfo.objects.get(job_id = job.job_id)
        plan = job_info.tasks_plan
        for index, stage in enumerate(plan):
            #cluster, tasks_ids = stage.items()[0]
            for cluster, tasks_ids in stage.items():
                for _task_id in tasks_ids:
                    try:
                        logger.info("get task and exec task, task_id=[%s]" % _task_id)
                        task = FuxiTaskRuntime.objects.get(task_id=_task_id)

                        # 为了让 job 可以重入，对task 的状态做判断，如果不是 NEW，说明已经运行过，应该跳过
                        if task.state != 'NEW':
                            logger.info("task=[%s] has started, ignore it." % _task_id)
                            continue
                            
                        task_info = {"state":"RUNNING", "start_time": timezone.now()}
                        runtime_manager.update_task_info(job.job_type, task, task_info)
                        self.task_executor.execute(task)
                    except Exception as e:
                        logger.fatal("exec task failed, task_id=[%s] error=[%s]" % (
                            _task_id, str(e)))
                        raise util.EFailedRequest()
                # check task state of the stage until succ
                stage_release_tasks = conf.get_option_values("concurrency", 'stage_release_tasks')
                if job_info.job_params['task_type'] in stage_release_tasks:
                    while True:
                        if self.__is_tasks_in_end_states(tasks_ids):
                            break
                        else:
                            logger.info("wait for task stage=[%s] to finish, job_id=[%s]" % (
                                index, job.job_id))
                            time.sleep(10)
                logger.info("stage=[%s] execute finish, job_id=[%s]" % (index, job.job_id))
        logger.info("plan execute succ, job_id=[%s]" % job.job_id)

    def __is_tasks_in_end_states(self, tasks_ids):
        end_states = ["CANCELLED", "SUCCESS", "FAILED", "TIMEOUT", "SKIPPED"]
        is_tasks_in_end_states = True
        #print tasks_ids
        for _task_id in tasks_ids:
            task = FuxiTaskRuntime.objects.get(task_id=_task_id)
            logger.info("check task, task=[%s], state=[%s]" % (task.task_id, task.state))
            if task.state not in end_states:
                is_tasks_in_end_states = False

        return is_tasks_in_end_states
