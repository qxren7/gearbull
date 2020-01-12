#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import queue
import decimal
import logging
import datetime
import traceback
import subprocess
from threading import Thread

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append("%s/../" % CUR_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gearbull.settings")

from multiprocessing import Queue
from multiprocessing import Manager
from multiprocessing import Process

import django

django.setup()

from WorkFlow import global_setttings

from django.db.models import Q
from django.db import connection
from django.utils import timezone

from WorkFlow import states
from WorkFlow import exceptions
from WorkFlow.models import Job
from WorkFlow.models import Task
from WorkFlow.models import ActionTree

logger = global_setttings.get_logger("monitor.log")
CONF = global_setttings.WORKFLOW_CONF

MONITOR_JOB_LIST = []

(status, _server_ip) = subprocess.getstatusoutput("hostname")


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
        mgr = Manager()
        self._task_queue = Queue()
        self._working_task_queue = mgr.dict()

        self._cycle_time = int(CONF.get("monitor", "cycle_time"))
        self._job_worker_num = int(CONF.get("monitor", "max_job_worker_num"))
        self._start_gap_time = int(CONF.get("monitor", "start_gap_time"))

    def start(self):
        """
        启动入口

        :param:
        :return:
        """

        max_task_worker_num = int(CONF.get("monitor", "max_task_worker_num"))
        task_workers = [
            TaskWorker(self._task_queue, self._working_task_queue)
            for i in range(max_task_worker_num)
        ]
        for task_worker in task_workers:
            task_worker.start()

        logger.info("tasks worker start")

        job_progress_worker = JobProgressWorker()
        job_progress_worker.start()

        logger.info("job progress worker start")

        job_factory = JobFactory()
        while True:
            try:
                logger.info("monitor get job one cycle over")
                logger.info(MONITOR_JOB_LIST)
                for task_id in job_factory.get_tasks():
                    if task_id not in self._working_task_queue:
                        self._task_queue.put(task_id)
                        self._working_task_queue[task_id] = True
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
        pass

    def get_tasks(self):
        """
        从数据库中获取待监控job列表
        待监控job为两类：
        1. 正在运行的job
        2. 运行结束(FAILED, SUCCESS)但仍有部分长尾的job

        :param:
        :return:
        """
        try:
            longtail_states = CONF.get_option_values("monitor",
                                                     "longtail_states")
            running_states = CONF.get_option_values("monitor",
                                                    "running_states")
            max_longtail_timeout = CONF.get("monitor", "max_longtail_timeout")
            job_all = Job.objects.filter(
                Q(server_ip=_server_ip),
                Q(state__in=running_states) | Q(state__in=longtail_states),
            )
            job_need_monitor = []
            tasks_need_monitor = []
            for job in job_all:

                # progress为空的代表刚开始调度，还没计算进度
                if (job.progress is not None and job.progress != ""
                        and int(job.progress) >= 100):
                    continue
                # timeout或schedule_time为空为异常情况，理论上不应该出现
                # 如果出现了，这种情况只进行正常监控，不捞长尾
                if job.timeout is None or job.schedule_time is None:
                    if job.state not in longtail_states:
                        job_need_monitor.append(job)
                    continue

                # 对于处于finish状态的job，还需要检查它的tasks状态，如果有处于unfnish状态的，需要继续监控
                if job.is_finish() and job.has_task_unfinished():
                    job_need_monitor.append(job)
                    continue

                # 避免用户设的超时过长，临时采用最大超时限制，长远方案为job隔离
                max_timeout = max_longtail_timeout
                if int(job.timeout) < int(max_longtail_timeout):
                    max_timeout = job.timeout
                time_gap = int(time.mktime(timezone.now().timetuple())) - int(
                    time.mktime(job.schedule_time.timetuple()))
                if time_gap > int(max_timeout):
                    continue
                job_need_monitor.append(job)
                tasks_ids = job.task_set.filter(
                    Q(state="RUNNING")).values_list("id", flat=True)
                tasks_need_monitor += tasks_ids

            return tasks_need_monitor

        except django.db.utils.OperationalError as e:
            logger.error("django db exception, error=[%s]" % str(e))
        except Exception as e:
            logger.error("job factory get jobs error, error=[%s]" % str(e))
        finally:
            connection.close()


# class JobWorker(Thread):
class JobWorker(Process):
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
        self._task_queue = queue.Queue()
        self._cycle_time = int(CONF.get("monitor", "cycle_time"))
        self._max_task_worker_num = int(
            CONF.get("monitor", "max_task_worker_num"))
        logger.info("job_worker start, name=[%s]" % self.name)

    def run(self):
        """
        线程启动函数

        :param:
        :return:
        """
        while True:
            job_id = self._job_queue.get()
            try:
                job = Job.objects.get(id=job_id)
                # TODO 对于 SUCCESS, FAILED 的job，暂时不跳过，应该持续到job 的timeout
                self._monitor_job(job_id)
                MONITOR_JOB_LIST.remove(job_id)
            except ValueError as e:
                logger.error(
                    "remove job from list error, job=[%s], error=[%s]" %
                    (job_id, str(e)))
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
        job = Job.objects.get(id=job_id)
        # 对于暂停状态的job，不需要monitor
        if job.is_paused:
            return

        self._get_job_info(job)

        logger.info("get tasks, job=[%s]" % job_id)
        tasks = job.task_set.filter(Q(state="RUNNING"))
        for task in tasks:
            logger.info("get task of job, task=[%s]" % task.id)
            self._task_queue.put(task.id)

        logger.info("monitor a job one cycle over, job_id=[%s]" % job_id)

    def _get_job_info(self, job):
        """
        调用子系统的get_job_info获取job信息
        
        :param job: 待监控job对象
        :return:
        """
        logger.info("get job info, job=[%s]" % job.id)


class TaskWorker(Process):
    def __init__(self, task_queue, working_task_queue):
        """
        初始化

        :param task_queue: 待监控的task队列
        :param job: 待监控task所属的job
        :return:
        """
        super(TaskWorker, self).__init__()
        self._task_queue = task_queue
        self._working_task_queue = working_task_queue
        logger.info("task_worker start, name=[%s]" % self.name)

    def run(self):
        while True:
            task_id = self._task_queue.get()
            try:
                self._monitor_task(task_id)
                self._working_task_queue.pop(task_id)
                logger.info("one task monitor over, task=[%s]" % task_id)
            except ValueError as e:
                logger.error(
                    "remove job from list error, job=[%s], error=[%s]" %
                    (job_id, str(e)))
                logger.error(traceback.format_exc())
            except Exception as e:
                logger.error("monitor job error, error=[%s]" % str(e))
                logger.error(traceback.format_exc())
            finally:
                connection.close()

    def _monitor_task(self, task_id):
        """
        每一个task的进度监控
        具体的监控逻辑由各个子系统实际定义，此处通过反射调用各子系统的逻辑
    
        :params task_id: 待监控的task_id
        :params job: 待监控task所属的job
        :returns:
        """
        task = Task.objects.get(id=task_id)
        job = Job.objects.get(id=task.job.id)
        actions = task.action_set.all().order_by("seq_id")
        is_task_succ = True
        action_states = [a.state for a in actions]

        logger.info("monitor task, task=[%s], action_states=[%s]" %
                    (task_id, action_states))

        action_tree = task.actiontree_set.first()

        if not action_tree:
            task_info = {"state": "ERROR", "finish_time": timezone.now()}
            task.update_task_info(task_info)
            logger.info("task's action_tree is None, task=[%s]" % task.id)
            return

        # if "RUNNING" in action_states:
        if action_tree.state == ActionTree.RUNNING:
            # task 的timeout 应该比 job timeout 要小
            if int((timezone.now() - task.start_time).total_seconds()) > int(
                    task.timeout):
                logger.info(
                    "task timeout, start_time=[%s], current time=[%s], task_id=[%s]"
                    % (task.id, task.start_time, timezone.now()))
                task_info = {"state": "TIMEOUT", "finish_time": timezone.now()}
                task.update_task_info(task_info)

                # 当task被设置为TIMEOUT时，对应的action, 如果状态不为FAILED or SUCCESS,  也应该设置为TIMEOUT
                for action in actions:
                    if action.state in ["FAILED", "SUCCESS"]:
                        continue
                    action.state = "TIMEOUT"
                    action.save()

            return

        if action_tree.state == ActionTree.FAILED:
            logger.info(
                "task fail, there is fail actions, task=[%s], action_states=[%s]"
                % (task_id, action_states))
            task_info = {"state": "FAILED", "finish_time": timezone.now()}
            task.update_task_info(task_info)
            return

        _action_states = list(set(action_states))
        # if "SUCCESS" in _action_states and len(_action_states) == 1:
        if action_tree.state == ActionTree.SUCCESS:
            logger.info("task succ, all action states is succ, task=[%s]" %
                        (task_id))
            task_info = {"state": "SUCCESS", "finish_time": timezone.now()}
            task.update_task_info(task_info)


# class JobProgressWorker(Thread):
class JobProgressWorker(Process):
    """
    计算所有job进度的线程
    单独一个线程处理job进度的原因是为了避免job里task太多，
    更新一遍所有task状态比较慢导致job进度更新延迟
    """
    def __init__(self):
        super(JobProgressWorker, self).__init__()
        self._cycle_time = int(CONF.get("monitor", "job_progress_cycle_time"))
        self._longtail_states = CONF.get_option_values("monitor",
                                                       "longtail_states")
        self._running_states = CONF.get_option_values("monitor",
                                                      "running_states")

    def run(self):
        """
        job 进度计算线程的启动入口

        :param:
        :return: 
        """
        while True:
            try:
                # (status, _server_ip) = subprocess.getstatusoutput("hostname -i")
                jobs = Job.objects.filter(Q(server_ip=_server_ip),
                                          Q(state__in=self._running_states))
                for job in jobs:
                    self.__calculate_job_progress(job)
            except Exception as e:
                logger.error("calculate job progress error, error=[%s]" %
                             str(e))
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
        logger.info("calculate job progress, job=[%s]" % job.id)
        try:
            module = __import__(job.job_type + ".monitor",
                                fromlist=["Monitor"])
            monitor_module = module.Monitor
            monitor_obj = module.Monitor()
            if hasattr(monitor_module, "calculate_job_progress"):
                logger.info("has calculate_job_progress")
                func = getattr(monitor_module, "calculate_job_progress")
            else:
                logger.info("hos no calculate_job_progress, use default")
                raise exceptions.WFFailedRequest()
        except Exception as e:
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
            logger.info("calculate job progress, job=[%s]" % job.id)
            # tasks = Task.objects.filter(job_id=job.id)
            tasks = job.task_set.all()
            task_detail = {}
            for task in tasks:
                if task.state not in task_detail:
                    task_detail[task.state] = 1
                    continue
                task_detail[task.state] += 1

            for state in states.STATES:
                if state not in task_detail:
                    task_detail[state] = 0

            if tasks.count() <= 0:
                logger.info("all task num le 0, job_id=[%s]" % job.id)
                info = {
                    "progress": "100",
                    "state": "SUCCESS",
                    "finish_time": timezone.now(),
                }
            else:
                running_num = task_detail.get("RUNNING", 0)
                new_num = task_detail.get("NEW", 0)
                timeout_num = task_detail.get("TIMEOUT", 0)

                finish_num = task_detail.get("SUCCESS", 0) + task_detail.get(
                    "SKIPPED", 0)
                failed_num = task_detail.get("FAILED", 0) + task_detail.get(
                    "ERROR", 0)
                progress = "%d" % (float(
                    decimal.Decimal(finish_num) /
                    decimal.Decimal(tasks.count()) * 100))
                failed_rate = "%d" % (float(
                    decimal.Decimal(failed_num) /
                    decimal.Decimal(tasks.count()) * 100))
                logger.info(
                    "running_num %s, new_num %s, timeout_num %s, finish_num %s, failed_num %s, progress %s, failed_rate %s"
                    % (running_num, new_num, timeout_num, finish_num,
                       failed_num, progress, failed_rate))
                info = {"progress": str(progress)}
                # 对于已经FAIL或SUCCESS了的job，捞长尾的过程只更新progress，不改变state
                # TIMEOUT状态的job不继续捞长尾
                if job.schedule_time:
                    time_gap = int(time.mktime(
                        timezone.now().timetuple())) - int(
                            time.mktime(job.schedule_time.timetuple()))
                else:
                    time_gap = -1

                if time_gap > int(job.timeout):
                    logger.info("job timeout, job_id=[%s]" % job.id)
                    info["state"] = "TIMEOUT"
                    logger.info(
                        "job_id=[%s] time_gap=[%s], timeout=[%s], so job state set to [%s]"
                        % (job.id, time_gap, job.timeout, info["state"]))
                    job.update_job_info(info)
                    return

                if job.state in self._longtail_states:
                    pass
                elif int(progress) >= int(job.threshold):
                    info["state"] = "SUCCESS"
                    info["finish_time"] = timezone.now()
                    logger.info(
                        "job_id=[%s] progress=[%s], threshold=[%s], so job state set to [%s]"
                        % (job.id, progress, job.threshold, info["state"]))

                elif int(progress) < int(
                        job.threshold) and int(failed_rate) <= int(
                            job.fail_rate):

                    # 如果这个job 还有任务处于 running 或者 new 状态，并且没有超过timeout时间，那么不应该变更 job 的状态，跳过本轮计算
                    if (running_num > 0
                            or new_num > 0) and time_gap <= int(job.timeout):
                        logger.info(
                            "job_id=[%s] has [%s] running, [%s] new tasks, so waiting "
                            % (job.id, running_num, new_num))
                        return

                    info["state"] = "SUCCESS"
                    info["finish_time"] = timezone.now()
                    logger.info(
                        "job_id=[%s] progress=[%s], failed_rate=[%s], fail_rate=[%s], so job state set to [%s]"
                        % (job.id, progress, failed_rate, job.fail_rate,
                           info["state"]))

                # for deploy system, job should not FAILED or TIMEOUT
                elif int(failed_rate) > (int(
                        job.fail_rate
                )) and running_num <= 0:  #如果有running tasks, 就不要设置为fail
                    # elif int(failed_rate) > int(job.threshold):
                    info["state"] = "FAILED"
                    info["finish_time"] = timezone.now()
                    logger.info(
                        "job_id=[%s] failed_rate=[%s], fail_rate=[%s], so job state set to [%s]"
                        % (job.id, failed_rate, job.fail_rate, info["state"]))
                elif time_gap > int(job.timeout):
                    logger.info("job timeout, job_id=[%s]" % job.id)
                    info['state'] = "TIMEOUT"
                    logger.info(
                        "job_id=[%s] time_gap=[%s], timeout=[%s], so job state set to [%s]"
                        % (job.id, time_gap, job.timeout, info['state']))
            logger.info(info)
            job.update_job_info(info)
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error("cal job progress error in default, error=[%s]" %
                         str(e))


if __name__ == "__main__":
    monitor = JobMonitor()
    monitor.start()
