#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: framework.py
Date: 2017/03/31 13:26:16
"""

import os
import sys
import time
import threading
from django.db import connection

from fuxi_framework.common_lib import util
from models import FuxiJobRuntime
from models import FuxiTaskRuntime

class BaseAnalyzer(object):
    """
    伏羲中所有analyzer的基类
    """
    def __init__(self):
        """
        TODO
        """
        pass

    def analyze(self, job):
        """
        分析决策函数

        :param job: 待分析的job对象
        :return:
        :raise util.ENotImplement: 未实现的基类异常
        """
        raise util.ENotImplement()


class BaseExecutor(object):
    """
    伏羲中所有子系统executor的基类
    """
    def __init__(self):
        """
        TODO
        """
        pass

    def __execute(self, job):
        """
        内部执行函数
        
        :param job: 待执行的job对象
        :return:
        """
        self.exec_tasks(job)

    def execute(self, job):
        """
        任务执行函数

        :param job: 待执行的job对象
        :return:
        """
        t = threading.Thread(target=self.__execute, args=(job,))
        t.start()

    def exec_tasks(self, job):
        """
        job内部具体执行task的逻辑

        :param job: 待执行的job对象
        :return:
        :raise util.ENotImplement: 未实现的基类异常
        """
        raise util.ENotImplement()


class BaseMonitor(object):
    """
    伏羲中所有monitor的基类
    """
    def __init__(self):
        """
        TODO
        """
        pass

    def get_job_info(self, job_id):
        """
        job执行进度获取接口

        :param job_id: 待监控的job的job_id
        :return:
        :raise util.ENotImplement: 未实现的基类异常
        """
        raise util.ENotImplement()

    def get_task_info(self, task_id):
        """
        task执行进度获取接口

        :param task_id: 待监控的task的task_id
        :return:
        :raise util.ENotImplement: 未实现的基类异常
        """
        raise util.ENotImplement()

    def get_action_info(self, action_id):
        """
        task执行进度获取接口

        :param aciton_id: 待监控的action的action_id
        :return:
        :raise util.ENotImplement: 未实现的基类异常
        """
        raise util.ENotImplement()

    def on_job_state_change(self, job, state):
        """
        job状态改变的后置动作

        :param job: 状态改变的job对象
        :param state: 改变后的状态
        :return:
        :raise util.ENotImplement: 未实现的基类异常
        """
        raise util.ENotImplement()

    def on_task_state_change(self, task, state):
        """
        task状态改变的后置动作

        :param task: 状态改变后的task对象
        :param state: 改变后的状态
        :return:
        :raise util.ENotImplement: 未实现的基类异常
        """
        raise util.ENotImplement()

    def on_action_state_change(self, action, state):
        """
        action状态改变的后置动作

        :param action: 状态改变的action对象
        :param state: 改变后的状态
        :return:
        :raise util.ENotImplement: 未实现的基类异常
        """
        raise util.ENotImplement()


class BaseTaskExecutor(BaseExecutor):
    """
    task动作执行的基类
    """
    def __init__(self):
        """
        TODO
        """
        super(BaseTaskExecutor, self).__init__()

    def __execute(self, task):
        """
        task的执行框架

        :param task: 待执行的task对象
        :return:
        """
        while True:
            job_control_action = self.__check_control_action(task)
            if job_control_action == "pause":
                time.sleep(60)
                continue
            elif job_control_action == "cancel":
                break
            else:
                self.__exec_pre_action(task)
                self.exec_actions(task)
                self.__exec_post_action(task)
                break

    def __check_control_action(self, task):
        """
        检查task对应的job是否被pause、cancel

        :param task: 待执行的task对象
        :return job.control_action: 当前的人工干预状态
        """
        job = FuxiJobRuntime.objects.get(job_id=task.job_id)
        connection.close()
        return job.control_action

    def execute(self, task):
        """
        task执行的入口

        :param task:
        :param task: 待执行的task对象
        :return:
        """
        t = threading.Thread(target=self.__execute, args=(task,))
        t.start()

    def __exec_pre_action(self, task):
        """
        task执行的前置动作,平台强制的动作放在这里

        :param task: 待执行的task对象
        :return:
        """
        pass

    def __exec_post_action(self, task):
        """
        task执行的后置动作,平台统一的强制动作放在这里
        
        :param task: 待执行的task对象
        :return:
        """
        pass

    def exec_actions(self, task):
        """
        task的具体执行动作

        :param task: 待执行的task对象
        :return:
        :raise util.ENotImplement: 未实现的基类异常
        """
        raise util.ENotImplement()


class BaseController(object):
    """
    对job的控制基类
    """
    def __init__(self):
        """
        TODO
        """
        pass

    def pause(self, jobs=None):
        """
        暂停job

        :param jobs: 要暂停的job_id列表,默认为空
        :return:
        """
        raise util.ENotImplement()

    def resume(self, jobs=None):
        """
        恢复暂停的job

        :param job_id: 要恢复的job_id列表，默认为空
        :return:
        """
        raise util.ENotImplement()

    def cancel(self, jobs=None):
        """
        取消job

        :param job_id: 要取消的job_id列表，默认为空
        :return:
        """
        raise util.ENotImplement()

    def filter_jobs(self, conditions):
        """
        获取满足特定条件的job对象列表

        :param conditions: dict类型的查询条件
        :return:
        """
        raise util.ENotImplement()

