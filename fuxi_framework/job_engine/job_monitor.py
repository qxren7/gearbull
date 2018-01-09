#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: job_monitor.py
Date: 2017/03/30 22:33:44
"""

import os
import sys
import Queue
import logging
import commands
from threading import Thread
import time
import datetime
import decimal
import traceback

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
from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.job_engine import runtime_manager
from fuxi_framework.common_lib import config_parser_wrapper
from fuxi_framework.common_lib import util
from fuxi_framework.common_lib import log

logger = logging.getLogger("monitor")
if logger.handlers == []:
    log.init_log("%s/../log/monitor" % CUR_DIR)
conf = config_parser_wrapper.ConfigParserWrapper("%s/../conf/job_engine.conf" % CUR_DIR)
MONITOR_JOB_LIST = []

class JobMonitor(object):
    """
    job监控模块，负责在job运行过程中监控job进度
    工作模式入下：
    1. 从数据库中取出未结束的job
    2. 将job分发给各个线程
    3. 分管每个job的线程从数据库中取出该job的所有未结束的task
    4. 通过协程方式并行完成该job的所有task状态回收
    5. 每个job完成状态收集后，计算一次该job的progress，并判断是否达到结束阈值，或是否超时
    """
    def __init__(self):
        """
        初始化
        
        :param:
        :return:
        """
        self._job_queue = Queue.Queue()
        self._cycle_time = int(conf.get_option_value("monitor", "cycle_time"))
        self._job_worker_num = int(conf.get_option_value("monitor", "max_job_worker_num"))
        self._start_gap_time = int(conf.get_option_value("monitor", "start_gap_time"))

    def start(self):
        """
        启动入口

        :param:
        :return:
        """
        logger.info("job monitor start")

        job_progress_worker = JobProgressWorker()
        job_progress_worker.start()

        time.sleep(self._start_gap_time)

        workers = [JobWorker(self._job_queue) for i in range(self._job_worker_num)]
        for worker in workers:
            worker.start()

        job_factory = JobFactory()
        while True:
            try:
                logger.info("monitor get job one cycle over")
                logger.info(MONITOR_JOB_LIST)
                for job in job_factory.get_jobs():
                    if job.job_id not in MONITOR_JOB_LIST:
                        MONITOR_JOB_LIST.append(job.job_id)
                        self._job_queue.put(job.job_id)
            except Exception as e:
                logger.error("monitor exception, error=[%s]" % str(e))
            finally:
                connection.close()

            time.sleep(self._cycle_time)


class JobFactory(object):
    """
    job producer
    monitor关注RUNNING/PAUSED状态的job，以及FAILED、SUCCESS了但没超时的长尾部分
    """
    def __init__(self):
        """
        TODO
        """
        pass

    def get_jobs(self):
        """
        从数据库中获取待监控job列表
        待监控job为两类：
        1. 正在运行的job
        2. 运行结束(FAILED, SUCCESS)但仍有部分长尾的job

        :param:
        :return:
        """
        try:
            (status, _server_ip) = commands.getstatusoutput("hostname -i")
            longtail_states = conf.get_option_values("monitor", "longtail_states")
            running_states = conf.get_option_values("monitor", "running_states")
            max_longtail_timeout = conf.get_option_value("monitor", "max_longtail_timeout")
            job_all = FuxiJobRuntime.objects.filter(
                    Q(server_ip=_server_ip),
                    Q(state__in=running_states) | Q(state__in=longtail_states))
            job_need_monitor = []
            for job in job_all:
                #progress为空的代表刚开始调度，还没计算进度
                if job.progress is not None and job.progress != "" and int(job.progress) >= 100:
                    continue
                #timeout或schedule_time为空为异常情况，理论上不应该出现
                #如果出现了，这种情况只进行正常监控，不捞长尾
                if job.timeout is None or job.schedule_time is None:
                    if job.state not in longtail_states:
                        job_need_monitor.append(job)
                    continue

                 # 对于处于finish状态的job，还需要检查它的tasks状态，如果有处于unfnish状态的，需要继续监控
                if job.is_finish() and job.has_task_unfinished():
                    job_need_monitor.append(job)
                    continue

                #避免用户设的超时过长，临时采用最大超时限制，长远方案为job隔离
                max_timeout = max_longtail_timeout
                if int(job.timeout) < int(max_longtail_timeout):
                    max_timeout = job.timeout
                time_gap = (int(time.mktime(timezone.now().timetuple())) - 
                        int(time.mktime(job.schedule_time.timetuple())))
                if time_gap > int(max_timeout):
                    continue
                job_need_monitor.append(job)
            logger.info("job factory get jobs to monitor")
            job_ids = [ j.job_id for j in job_need_monitor]
            logger.info("job_need_monitor=[%s]" % job_ids)
            return job_need_monitor
        except django.db.utils.OperationalError as e:
            logger.error("django db exception, error=[%s]" % str(e))
        except Exception as e:
            logger.error("job factory get jobs error, error=[%s]" % str(e))
        finally:
            connection.close()


class JobWorker(Thread):
    """
    job级别的监控线程
    """
    def __init__(self, job_queue):
        """
        初始化job监控的工作线程

        :param job_queue: 待监控队列
        :return:
        """
        super(JobWorker, self).__init__()
        self._job_queue = job_queue
        self._task_queue = Queue.Queue()
        self._cycle_time = int(conf.get_option_value("monitor", "cycle_time"))
        self._max_task_worker_num = conf.get_option_value("monitor", "max_task_worker_num")

    def run(self):
        """
        线程启动函数

        :param:
        :return:
        """
        while True:
            logger.info("job worker working")
            job_id = self._job_queue.get()
            try:
                job = FuxiJobRuntime.objects.get(job_id=job_id)
                # TODO 对于 SUCCESS, FAILED 的job，暂时不跳过，应该持续到job 的timeout  by @hejianming
                self._monitor_job(job_id)
                MONITOR_JOB_LIST.remove(job_id)
            except ValueError as e:
                logger.error("remove job from list error, job=[%s], error=[%s]" % (job_id, str(e)))
                logger.error(traceback.format_exc())
            except Exception as e:
                logger.error("monitor job error, error=[%s]" % str(e))
                logger.error(traceback.format_exc())
            finally:
                connection.close()

    def _monitor_job(self, job_id):
        """
        job监控流程

        :param job_id: 待监控job的job_id
        :return:
        """
        job = FuxiJobRuntime.objects.get(job_id=job_id)
        # 对于以及处于finish状态的job，仍然需要继续跟踪其状态为running 的tasks
        #if job.state in ["CANCELLED", "SUCCESS", "FAILED"]:
        #    return

        self._get_job_info(job)

        logger.info("get tasks, job=[%s]" % job_id)
        tasks = FuxiTaskRuntime.objects.filter(Q(job_id=job_id), Q(state="RUNNING"))
        logger.info(tasks)
        for task in tasks:
            logger.info("get task of job, task=[%s]" % task.task_id)
            self._task_queue.put(task.task_id)

        if len(tasks) < self._max_task_worker_num:
            task_worker_num = len(tasks)
        else:
            task_worker_num = self._max_task_worker_num
        logger.info("task worker num, %s" % str(task_worker_num))

        task_workers = [TaskWorker(self._task_queue, job) for i in range(task_worker_num)]
        for task_worker in task_workers:
            task_worker.start()

        self._task_queue.join()
        logger.info("monitor a job one cycle over, job_id=[%s]" % job_id)

    def _get_job_info(self, job):
        """
        调用子系统的get_job_info获取job信息
        
        :param job: 待监控job对象
        :return:
        """
        logger.info("get job info, job=[%s]" % job.job_id)
        try:
            module = __import__(job.job_type + ".monitor", fromlist=['Monitor'])
        except Exception as e:
            logger.error(str(e))
            raise util.EFailedRequest(str(e))
        monitor_module = module.Monitor
        monitor_obj = module.Monitor()
        if hasattr(monitor_module, "get_job_info"):
            logger.info("has get_job_info")
            func = getattr(monitor_module, "get_job_info")
            try:
                func(monitor_obj, job.job_id)
            except Exception as e:
                logger.error("get job monitor info error, error=[%s]" % str(e))
                logger.error(traceback.format_exc())
                raise util.EFailedRequest(str(e))
        else:
            logger.error("subsystem has no monitor_job_func, job_id=[%s], job_type=[%s]" % 
                    (job.job_id, job.job_type))


class TaskWorker(Thread):
    """
    监控task状态的线程
    """
    def __init__(self, task_queue, job):
        """
        初始化

        :param task_queue: 待监控的task队列
        :param job: 待监控task所属的job
        :return:
        """
        super(TaskWorker, self).__init__()
        self._task_queue = task_queue
        self._job = job

    def run(self):
        """
        从queue中获取该job的所有task，并挨个监控
        
        :param:
        :return:
        """
        logger.info("in task_worker, job=[%s]" % self._job.job_id)
        while True:
            try:
                task_id = self._task_queue.get(timeout=1)
                logger.info("task worker working, task=[%s]" % task_id)
                self._monitor_task(task_id, self._job)
                self._task_queue.task_done()
                logger.info("one task monitor over, task=[%s]" % task_id)
            except Queue.Empty:
                logger.info("task queue empty, job=[%s]" % self._job.job_id)
                break
            except Exception as e:
                logger.error("monitor task error, error=[%s]" % str(e))
                logger.error(traceback.format_exc())
                self._task_queue.task_done()
            finally:
                connection.close()

    def _monitor_task(self, task_id, job):
        """
        每一个task的进度监控
        具体的监控逻辑由各个子系统实际定义，此处通过反射调用各子系统的逻辑
    
        :params task_id: 待监控的task_id
        :params job: 待监控task所属的job
        :returns:
        """
        logger.info("monitor task, task=[%s]" % task_id)
        try:
            module = __import__(job.job_type + ".monitor", fromlist=['Monitor'])
        except Exception as e:
            logger.error(str(e))
            raise util.EFailedRequest(str(e))
        monitor_module = module.Monitor
        monitor_obj = module.Monitor()
        if hasattr(monitor_module, "get_task_info"):
            logger.info("has get_task_info")
            func = getattr(monitor_module, "get_task_info")
            try:
                func(monitor_obj, task_id)
            except Exception as e:
                logger.error("get task monitor info error, error=[%s]" % str(e))
                logger.error(traceback.format_exc())
                raise util.EFailedRequest(str(e))
        else:
            logger.error("subsystem has no monitor_task_func, job_id=[%s], job_type=[%s]" % 
                    (job.job_id, job.job_type))


class JobProgressWorker(Thread):
    """
    计算所有job进度的线程
    单独一个线程处理job进度的原因是为了避免job里task太多，
    更新一遍所有task状态比较慢导致job进度更新延迟
    """
    def __init__(self):
        """
        TODO
        """
        super(JobProgressWorker, self).__init__()
        self._cycle_time = int(conf.get_option_value("monitor", "job_progress_cycle_time"))
        self._longtail_states = conf.get_option_values("monitor", "longtail_states")
        self._running_states = conf.get_option_values("monitor", "running_states")

    def run(self):
        """
        job 进度计算线程的启动入口

        :param:
        :return: 
        """
        while True:
            try:
                (status, _server_ip) = commands.getstatusoutput("hostname -i")
                jobs = FuxiJobRuntime.objects.filter(
                        Q(server_ip=_server_ip),
                        Q(state__in=self._running_states))
                for job in jobs:
                    self.__calculate_job_progress(job)
            except Exception as e:
                logger.error("calculate job progress error, error=[%s]" % str(e))
                logger.error(traceback.format_exc())
            finally:
                connection.close()

            time.sleep(self._cycle_time)

    def __calculate_job_progress(self, job):
        """
        计算一个job的进度
        当用户在子系统中自定义了计算方法时，使用用户自定义的方式
        当用户没有自定义时，使用默认的计算方式

        :param job: 待计算的job对象
        :return:
        """
        logger.info("calculate job progress, job=[%s]" % job.job_id)
        try:
            module = __import__(job.job_type + ".monitor", fromlist=['Monitor'])
            monitor_module = module.Monitor
            monitor_obj = module.Monitor()
            if hasattr(monitor_module, "calculate_job_progress"):
                logger.info("has calculate_job_progress")
                func = getattr(monitor_module, "calculate_job_progress")
            else:
                logger.info("hos no calculate_job_progress, use default")
                raise util.EFailedRequest()
        except Exception as e:
            logger.error("load calculate_job_progress error, use default, error=[%s]" % str(e))
            self.__cal_job_progress_default(job)
            return

        try:
            func(monitor_obj, job)
        except Exception as e:
            logger.error("cal job progress error, error=[%s]" % str(e))
            logger.error(traceback.format_exc())

    def __cal_job_progress_default(self, job):
        """
        计算一个job的进度，使用默认逻辑计算
        progress = (SUCCESS的task数 + SKIPPED的task数) / 所有task个数

        :param job: 待计算的job对象
        :return:
        """
        try:
            logger.info("calculate job progress, job=[%s]" % job.job_id)
            tasks = FuxiTaskRuntime.objects.filter(job_id=job.job_id)
            task_detail = {}
            for task in tasks:
                if task.state not in task_detail:
                    task_detail[task.state] = 1
                    continue
                task_detail[task.state] += 1
    
            for state in runtime_manager.STATES:
                if state not in task_detail:
                    task_detail[state] = 0
    
            if tasks.count() <= 0:
                logger.info("all task num le 0, job_id=[%s]" % job.job_id)
                info = {"progress":"100", "state":"SUCCESS", "finish_time":timezone.now()}
            else:
                logger.info(task_detail)
                finish_num = task_detail['SUCCESS'] + task_detail['SKIPPED']
                failed_num = task_detail['FAILED']
                progress = "%d" % (float(decimal.Decimal(finish_num) / 
                                decimal.Decimal(tasks.count()) * 100))
                failed_rate = "%d" % (float(decimal.Decimal(failed_num) / 
                                decimal.Decimal(tasks.count()) * 100))
                info = {"progress":str(progress)}
                #对于已经FAIL或SUCCESS了的job，捞长尾的过程只更新progress，不改变state
                #TIMEOUT状态的job不继续捞长尾
                time_gap = (int(time.mktime(timezone.now().timetuple())) - 
                        int(time.mktime(job.schedule_time.timetuple())))
                if job.state in self._longtail_states:
                    pass
                elif int(progress) >= int(job.threshold):
                    info['state'] = "SUCCESS"
                    info['finish_time'] = timezone.now()
                elif int(failed_rate) > (100 - int(job.threshold)):
                    info['state'] = "FAILED"
                    info['finish_time'] = timezone.now()
                elif time_gap > int(job.timeout):
                    logger.info("job timeout, job_id=[%s]" % job.job_id)
                    info['state'] = "TIMEOUT"
    
            logger.info(info)
            runtime_manager.update_job_info(job, info)
        except Exception as e:
            logger.error("cal job progress error in default, error=[%s]" % str(e))


if __name__ == "__main__":
    monitor = JobMonitor()
    monitor.start()
