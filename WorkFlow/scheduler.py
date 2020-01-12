#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import queue
import signal
import traceback
import threading
import subprocess
from threading import Thread
from multiprocessing import Queue
from multiprocessing import Process
from multiprocessing import Manager

import django
import global_setttings

django.setup()

from django.db.models import Q
from django.db import connection
from django.utils import timezone

from WorkFlow import msgs
from WorkFlow import analyzer
from WorkFlow import executor
from WorkFlow.models import Job
from WorkFlow.models import Task
#from WorkFlow import global_setttings

from WorkFlow.analyzer import analyze_execute
from WorkFlow.queue_executor import thread_execute

logger = global_setttings.get_logger("scheduler.log")
CONF = global_setttings.WORKFLOW_CONF


class JobScheduler(object):
    """
    scheduler主程序
    工作模式如下：
    1. 从数据库中取出满足条件的job，即NEW和READY状态的job
    2. 将任务分发给各个线程处理
    """
    def __init__(self):
        # 使用 mgr.dict 会带来一个额外的进程，数量由 mgr 内部自己控制
        mgr = Manager()
        self._job_queue = Queue()
        self._working_job_queue = mgr.dict()
        self._task_queue = Queue()
        self._working_task_queue = mgr.dict()
        self._jobs_allocate_queues = {}
        global_setttings.init_users()

        self._cycle_time = int(CONF.get("scheduler", "cycle_time"))
        self._analyzer_worker_num = int(
            CONF.get("scheduler", "analyzer_worker_num"))
        self._task_worker_num = int(CONF.get("scheduler", "task_worker_num"))
        self_filename = os.path.basename(__file__).split(".")[0]
        self._pid_file = "%s/%s.pid" % (global_setttings.VAR_DIR,
                                        self_filename)

        self.__write_pid()

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.stop()

    def __write_pid(self):
        # Write process id to a file
        fp = open(self._pid_file, "w")
        fp.write(str(os.getpid()))
        fp.close()

    def start(self):
        """
        scheduler启动函数
        """
        logger.info("start scheduler")
        workers = [
            Worker(self._job_queue, self._working_job_queue)
            for i in range(self._analyzer_worker_num)
        ]
        for worker in workers:
            worker.start()

        workers = [
            TaskWorker(self._task_queue, self._working_task_queue)
            for i in range(self._task_worker_num)
        ]
        for worker in workers:
            worker.start()

        job_factory = JobFactory()

        while True:
            try:
                for job in job_factory.get_jobs():
                    if job.id not in self._working_job_queue:
                        self._job_queue.put(job.id)
                        self._working_job_queue[job.id] = True

                for task_id in job_factory.get_tasks():
                    if task_id not in self._working_task_queue:
                        self._task_queue.put(task_id)
                        self._working_task_queue[task_id] = True
                msg = msgs.cur_queue_size % (
                    self._job_queue.qsize(), len(self._working_job_queue),
                    self._task_queue.qsize(), len(self._working_task_queue))
                logger.info(msg)
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error(msgs.schedule_exception % str(e))
            finally:
                connection.close()

            time.sleep(self._cycle_time)

    def stop(self):
        # stop all workers
        for w in self._workers:
            logger.info("stop worker=[%s]" % w.name)
            w.stop()

        self.__stop.set()
        self.join()

    def is_stopped(self):
        return self.__stop.isSet()


class JobFactory(object):
    """
    job来源
    scheduler只关注NEW和READY状态的job
    """
    def __init__(self):
        (status, server_ip) = subprocess.getstatusoutput("hostname")
        self._server_ip = server_ip

    def get_tasks(self):
        try:
            jobs = Job.objects.filter(
                Q(control_action=""),
                Q(state="RUNNING"),
                Q(server_ip=self._server_ip),
            )
            logger.info("job factory get RUNNING jobs")
            task_ids = []
            for j in jobs:
                tasks_plan = j.tasks_plan
                for level, entities_dict in enumerate(tasks_plan):
                    can_next = True
                    for stage_name, entities_list in entities_dict.items():
                        _task_ids = entities_list
                        can_next, to_run_ids, not_finish_ids = Task.can_next_stage(
                            _task_ids)
                        if can_next:
                            continue
                        else:
                            logger.info(msgs.still_running %
                                        (j.id, not_finish_ids))
                            task_ids += to_run_ids
                            break
                    if not can_next:
                        break  # 如果stage 是 NOT_COMPLETE, 下一个level 不应该执行，所以break

            return task_ids
        except django.db.utils.OperationalError as e:
            logger.error("django db exception, error=[%s]" % str(e))
            logger.error(traceback.format_exc())
        except Exception as e:
            logger.error("job factory get jobs error, error=[%s]" % str(e))
            logger.error(traceback.format_exc())
        finally:
            # pass
            connection.close()

    def get_jobs(self):
        """
        从数据库中获取待调度job列表

        :param:
        :return:
        """
        try:
            jobs = Job.objects.filter(
                Q(control_action=""),
                Q(state="NEW") | Q(state="READY"),
                # Q(state="NEW"), # Test only analyzer performace
                Q(server_ip=self._server_ip),
            )
            job_ids = [j.id for j in jobs]
            logger.info("job factory get NEW or READY jobs, jobs=[%s]" %
                        job_ids)
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
        reentry_job_types = CONF.get("scheduler", "reentry_job_types")
        try:
            # 系统重启时，只有状态为 RUNNING 的job需要重新执行
            jobs = Job.objects.filter(state="RUNNING")
            return jobs
        except Exception as e:
            logger.error("schedule job error, error=[%s]" % str(e))
            logger.error(traceback.format_exc())
        finally:
            connection.close()


class Worker(Process):
    """
    job处理线程,每个线程的工作如下：
    1. NEW状态的job，交给analyzer处理，并将状态改为INIT
    2. READY状态的job，交给executor处理，并将状态改为RUNNING
    """
    def __init__(self, job_queue, working_job_queue):
        super(Worker, self).__init__()
        self._job_queue = job_queue
        self._working_job_queue = working_job_queue
        logger.info("init work process %s" % self.name)

    def run(self):
        """
        job调度逻辑

        :param:
        :return:
        """
        while True:
            try:

                logger.info("work process=[%s] working" % self.name)
                job_id = self._job_queue.get()
                logger.info("get job to work, job_id=[%s]" % job_id)
                job = Job.objects.get(id=job_id)
                if job.control_action != "":
                    continue
                if job.state == "NEW":
                    job_info = {"state": "INIT"}
                    job.update_job_info(job_info)
                    logger.info("start analyzer , job id %s" % job.id)
                    analyzer.analyze(job)
                    self._working_job_queue.pop(job.id)
                    logger.info("end analyzer , job id %s" % job.id)
                elif job.state == "READY":
                    logger.info("bulk_gen_actions, job_id=[%s]" % job_id)
                    analyzer.bulk_gen_actions(job)
                    schedule_time = timezone.now()
                    job_info = {
                        "schedule_time": schedule_time,
                        "state_update_time": schedule_time,
                        "state": "RUNNING",
                    }
                    job.update_job_info(job_info)
                    self._working_job_queue.pop(job.id)
            except Exception as e:
                logger.error("schedule job error, error=[%s]" % str(e))
                logger.error(traceback.format_exc())
            finally:
                connection.close()


class TaskWorker(Process):
    def __init__(self, task_queue, working_task_queue):
        super(TaskWorker, self).__init__()
        self._task_queue = task_queue
        self._working_task_queue = working_task_queue
        logger.info("init task work process %s" % self.name)

    def run(self):
        while True:
            try:
                task_id = self._task_queue.get()
                logger.info(msgs.get_task % (self.name, task_id))
                executor.execute(task_id)
                self._working_task_queue.pop(task_id)
            except Exception as e:
                logger.error("task execute error, error=[%s]" % str(e))
                logger.error(traceback.format_exc())
            finally:
                connection.close()


if __name__ == "__main__":
    scheduler = JobScheduler()
    scheduler.start()
