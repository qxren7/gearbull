#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import queue
import traceback
import threading
import importlib
from retry import retry
from threading import Thread
from django.utils import timezone

from . import global_setttings

import django

django.setup()

from django.db.models import Q
from django.db import connection
from django.utils import timezone

from WorkFlow.models import Job
from WorkFlow.models import Task
from WorkFlow.models import Action
from WorkFlow.models import FlowMap
from WorkFlow.models import ActionTree
from WorkFlow.states import JobStatus

from WorkFlow import analyzer
from WorkFlow import executor
from WorkFlow import exceptions

logger = global_setttings.get_logger("queue_executor.log")
CONF = global_setttings.WORKFLOW_CONF


def thread_execute(job):
    t = threading.Thread(target=start_execute, args=(job, ))
    t.start()
    t.join()
    logger.info("process  working for job=[%s]  start " % job.id)


def start_execute(job):
    queue_executor = QueueExecutor(job)
    queue_executor.start()


class QueueExecutor(object):
    """
    QueueExecutor主程序
    工作模式如下：
    1. 从数据库中取出满足条件的job，即NEW和READY状态的job
    2. 将任务分发给各个线程处理
    """
    def __init__(self, job):
        self._job = job
        self._task_queue = queue.Queue()
        self._cycle_time = int(CONF.get("queue_executor", "cycle_time"))
        self._task_lock = threading.Lock()

        max_worker_num = int(CONF.get("queue_executor", "max_worker_num"))
        if self._job.concurrency < max_worker_num:
            self._worker_num = self._job.concurrency
        else:
            self._worker_num = max_worker_num

    def start(self):
        logger.info("start QueueExecutor, working for job=[%s]" % self._job.id)
        workers = [Worker(self) for i in range(self._worker_num)]
        self._workers = workers
        for worker in workers:
            logger.info("start worker=[%s], working for job=[%s]" %
                        (worker.name, self._job.id))
            worker.start()

        tasks_plan = self._job.tasks_plan

        for level, entities_dict in enumerate(tasks_plan):
            try:
                for stage_name, entities_list in entities_dict.items():
                    for entity in entities_list:
                        self._task_queue.put(entity)

                    self._task_queue.join()

                    if (not self._job.continue_after_stage_finish
                            and level < len(tasks_plan) - 1):
                        self._job.pause()

                    logger.info(
                        "stage=[%s] execute finish, pause job=[%s], wait for user resume."
                        % (stage_name, self._job.id))
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error("QueueExecutor exception, error=[%s]" % str(e))
            finally:
                connection.close()

        for w in workers:
            logger.info("queue stop worker=[%s], working for job=[%s]" %
                        (w.name, self._job.id))
            w.stop()

        connection.close()
        logger.info("QueueExecutor finish, working for job=[%s]" %
                    self._job.id)


class Worker(Thread):
    def __init__(self, executor):
        super(Worker, self).__init__()
        self._executor = executor
        self.__stop = threading.Event()

    def stop(self):
        self.__stop.set()
        self.join()

    def is_stopped(self):
        return self.__stop.isSet()

    def run(self):
        while not self.is_stopped():
            try:
                _job = Job.objects.get(id=self._executor._job.id)
                if _job.is_paused:
                    logger.info("worker=[%s], job=[%s],job is paused, wait." %
                                (self.name, _job.id))
                    time.sleep(3)
                elif self._executor._task_queue.qsize() > 0:
                    entity = self._executor._task_queue.get()
                    exec_task(_job, entity, self._executor._task_lock)
                    self._executor._task_queue.task_done()
                elif _job.state in JobStatus.FINISH_STATES:
                    logger.info("job=[%s] is finish, worker=[%s] quit." %
                                (_job.id, self.name))
                    connection.close()
                    break
                else:
                    logger.info("worker=[%s], job=[%s],empty queue, wait." %
                                (self.name, _job.id))
                    time.sleep(3)
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.fatal(
                    "exec task failed, worker=[%s], job=[%s] error=[%s]" %
                    (self.name, _job.id, str(e)))
            finally:
                connection.close()

        logger.info("worker:%s  end" % self.name)


def exec_task(job, _task_id, task_lock):
    try:
        logger.info("get task and exec task, task_id=[%s]" % _task_id)
        task = Task.objects.get(id=_task_id)

        # 为了让 job 可以重入，对task 的状态做判断，如果不是 NEW，说明已经运行过，应该跳过
        if task.state != "NEW":
            logger.info("task=[%s] has started, ignore it." % _task_id)
            return

        task_info = {"state": "RUNNING", "start_time": timezone.now()}
        task.update_task_info(task_info)
        exec_actions(task)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.fatal("exec task failed, task_id=[%s] error=[%s]" %
                     (_task_id, str(e)))
    finally:
        connection.close()


def exec_actions(task):
    action_tree = task.actiontree_set.first()
    action_tree.state = ActionTree.RUNNING
    action_tree.save()
    result = action_tree.root.iterate_execute()
    return result
