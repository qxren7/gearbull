#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: scheduler.py
Date: 2017/03/30 20:23:11
"""
import os
import sys
import Queue
import logging
import time
import commands
import datetime
import traceback
from threading import Thread

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
COMMON_DIR = "%s/../common_lib" % CUR_DIR
sys.path.append(COMMON_DIR)
sys.path.append("%s/../" % CUR_DIR)
sys.path.append("%s/../../" % CUR_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fuxi.settings")

import django
django.setup()
from django.db.models import Q
from django.db import connection
from django.utils import timezone
from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.job_engine import job_analyzer
from fuxi_framework.job_engine import job_executor
from fuxi_framework.job_engine import runtime_manager
from fuxi_framework.common_lib import config_parser_wrapper
from fuxi_framework.common_lib import log

logger = logging.getLogger("scheduler")
if logger.handlers == []:
    log.init_log("%s/../log/scheduler" % CUR_DIR)
conf = config_parser_wrapper.ConfigParserWrapper("%s/../conf/job_engine.conf" % CUR_DIR)

class JobScheduler(object):
    """
    scheduler主程序
    工作模式如下：
    1. 从数据库中取出满足条件的job，即NEW和READY状态的job
    2. 将任务分发给各个线程处理
    """
    def __init__(self):
        """
        TODO
        """
        self._job_queue = Queue.Queue()
        self._cycle_time = int(conf.get_option_value("scheduler", "cycle_time"))
        self._worker_num = int(conf.get_option_value("scheduler", "max_worker_num"))

    def start(self):
        """
        scheduler启动函数
        """
        logger.info("start scheduler")
        workers = [Worker(self._job_queue) for i in range(self._worker_num)]
        for worker in workers:
            worker.start()

        job_factory = JobFactory()

        for job in job_factory.get_reentry_jobs():
            self._job_queue.put(job.job_id)

        while True:
            try:
                for job in job_factory.get_jobs():
                    self._job_queue.put(job.job_id)
                logger.info("scheduler one cycle over")
            except Exception as e:
                logger.error("scheduler exception, error=[%s]" % str(e))
            finally:
                connection.close()

            time.sleep(self._cycle_time)


class JobFactory(object):
    """
    job来源
    scheduler只关注NEW和READY状态的job
    """
    def __init__(self):
        """
        TODO
        """
        pass

    def get_jobs(self):
        """
        从数据库中获取待调度job列表

        :param:
        :return:
        """
        try:
            (status, _server_ip) = commands.getstatusoutput("hostname -i")
            jobs = FuxiJobRuntime.objects.filter(
                    Q(control_action=""), 
                    Q(state="NEW") | Q(state="READY"),
                    Q(server_ip=_server_ip))
            logger.info("job factory get jobs, jobs=[%s]" % jobs)
            return jobs
        except django.db.utils.OperationalError as e:
            logger.error("django db exception, error=[%s]" % str(e))
        except Exception as e:
            logger.error("job factory get jobs error, error=[%s]" % str(e))
        finally:
            connection.close()

    def get_reentry_jobs(self):
        """ 
        对可重入的job类型，重新执行；用于恢复因系统重启而中断的job 

        :param:
        :return:
        """
        reentry_job_types = conf.get_option_values("scheduler", "reentry_job_types")
        try:
            # 系统重启时，只有状态为 RUNNING 的job需要重新执行
            jobs = FuxiJobRuntime.objects.filter(job_type__in=reentry_job_types, state="RUNNING")
            return jobs
        except Exception as e:
            logger.error("schedule job error, error=[%s]" % str(e))
            logger.error(traceback.format_exc())
        finally:
            connection.close()



class Worker(Thread):
    """
    job处理线程,每个线程的工作如下：
    1. NEW状态的job，交给analyzer处理，并将状态改为INIT
    2. READY状态的job，交给executor处理，并将状态改为RUNNING
    """
    def __init__(self, job_queue):
        """
        TODO
        """
        super(Worker, self).__init__()
        self._job_queue = job_queue

    def run(self):
        """
        job调度逻辑

        :param:
        :return:
        """
        while True:
            try:
                logger.info("scheduler thread working")
                job_id = self._job_queue.get()
                logger.info("get job to schedule, job_id=[%s]" % job_id)
                job = FuxiJobRuntime.objects.get(job_id=job_id)
                if job.control_action != "":
                    continue
                if job.state == "NEW":
                    job_info = {"state":"INIT"}
                    runtime_manager.update_job_info(job, job_info)
                    job_analyzer.analyze(job)
                    logger.info("update state")
                elif job.state == "READY":
                    schedule_time = timezone.now()
                    job_info = {"schedule_time":schedule_time, "state":"LAUNCHING"}
                    runtime_manager.update_job_info(job, job_info)
                    job_executor.execute(job)
                    job_info = {"state":"RUNNING"}
                    runtime_manager.update_job_info(job, job_info)
                elif job.state == "RUNNING":
                    job_executor.execute(job)
                    logger.info("reexcute job=[%s]" % job.job_id)
            except Exception as e:
                logger.error("schedule job error, error=[%s]" % str(e))
                logger.error(traceback.format_exc())
            finally:
                connection.close()


if __name__ == "__main__":
    scheduler = JobScheduler()
    scheduler.start()
