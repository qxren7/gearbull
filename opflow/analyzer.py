# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: analyzer.py
Date: 2017/04/12 
"""

import os
import sys
import logging
import time
import pprint
import socket
import traceback

from django.db import connection

from fuxi_framework import framework
from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.models import FuxiActionRuntime
from fuxi_framework.job_engine import runtime_manager
from fuxi_framework.job_engine import id_generator
from fuxi_framework.common_lib import beehive_wrapper
from fuxi_framework.common_lib import config_parser_wrapper
from fuxi_framework.common_lib import util
from fuxi_framework.common_lib import log

from zhongjing import actions 
from zhongjing.models import JobInfo
from zhongjing.models import TaskInfo 
from zhongjing.lib import util
from zhongjing.security_strategy import SecurityStrategy

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
log.init_log("%s/log/analyzer" % CUR_DIR)
logger = logging.getLogger("analyzer")

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
conf = config_parser_wrapper.ConfigParserWrapper("%s/conf/zhongjing.conf" % CUR_DIR)
#conf = config_parser_wrapper.ConfigParserWrapper("%s/conf/zhongjing.conf.test" % CUR_DIR)


class Analyzer(framework.BaseAnalyzer):
    """
    TODO
    """
    def __init__(self):
        """
        TODO
        """
        super(Analyzer, self).__init__()

    def analyze(self, job):
        """
        TODO
        """
        try:

            logger.info('job_id=[%s], zhongjing analyze generate tasks plan.' % job.job_id)
            job_info = JobInfo.objects.get(job_id = job.job_id)
            security_strategy = SecurityStrategy(job_info, job_info.job_params['task_type'])
            hosts_info = security_strategy.filter_targets()
            self.generate_plan(job, job_info, hosts_info) 
   
            #update job state
            info = {"state":"READY"}
            logger.info('job_id=[%s], generate tasks plan done, update state=[%s]' % (job.job_id, info))
            runtime_manager.update_job_info(job, info)
        except Exception as e:
            logger.error(traceback.format_exc())
            msg = "job_id=[%s], update job state error in analyze, error=[%s]" % (job.job_id, e)
            logger.fatal(msg)
            info = {"state":"ERROR"}
            error = {"analyze": msg}
            job_info.errors.update(error)
            job_info.save()
            runtime_manager.update_job_info(job, info)
            raise Exception(msg)

    def generate_plan(self, job, job_info, host_infos):
        """
        TODO
        """
        _plan = []
        task_type = job_info.job_params['task_type']

        key = "%s_timeout" % task_type
        task_timeout = 0
        if key in conf.get_options("ultron"):
            task_timeout = int(conf.get_option_value("ultron", key))
        else: 
            task_timeout = job.timeout

        for _cluster, host_infos_list in host_infos.items():
            stage = {}
            host_infos_groups = self.__split_hosts_into_groups(host_infos_list, job_info.job_params)
            for index, _host_infos_list in enumerate(host_infos_groups):
                #for host_info in host_infos_list:
                task_ids = []
                for host_info in _host_infos_list:
                    _task = self.__gen_task(job, host_info.host, 'Host', task_timeout)
                    task_ids.append(_task.task_id)
                    self.__gen_actions(_cluster, job, task_type, _task, 
                            extra_params = job_info.job_params)
                    self.__gen_task_info(_cluster, _task, host_info, task_type)
                stage_name = "%s_%s" % (_cluster, index)
                stage[stage_name] = task_ids
            _plan.append(stage)
        job_info.tasks_plan = _plan
        job_info.save()
        connection.close()

    def __gen_task_params(self, job):
        task_info = {
            "task_id": id_generator.gen_task_id(job),
            "job_id":job.job_id,
            "task_priority":"90",
            "threshold":"100",
            "timeout": job.timeout,
            "state":"NEW",
        }
        return task_info

    def __gen_task(self, job, host, entity_type, task_timeout):
        task_info = {
            "task_id": id_generator.gen_task_id(job),
            "job_id":job.job_id,
            "task_priority":"90",
            "threshold":"100",
            "timeout": task_timeout,
            "state":"NEW",
            "entity_type": entity_type,
            "entity_name": host,
        }

        _task = runtime_manager.create_task(task_info)
        return _task

    def __gen_actions(self, _cluster, job, task_type, _task, extra_params=None):
        action_params = {
                'cluster': _cluster, 
                'host': _task.entity_name, 
                'task_id': _task.task_id,
                "timeout": job.timeout,
                "extra_params": extra_params,
                }
        actions.create_actions_for_task(task_type, _task, action_params)

    def __gen_task_info(self, _cluster, _task, host_info, _task_type):
        _apps = beehive_wrapper.get_host_main_tag(_cluster, host_info.host)
        # 一台机器只需要一个 tag 来保存task info 记录
        _apps = _apps[0:1]
        #如果这机器上没有app，那么设置一个空app
        if len(_apps) == 0:
            _apps = ['dummy']
        for _app in _apps:
            _task_info = TaskInfo(
                    task = _task, cluster = _cluster, app = _app, 
                    reason = host_info.reason, task_type = _task_type)
            _task_info.save()
        connection.close()

    def __split_hosts_into_groups(self, host_infos_list, job_params):
        conf.reload_conf()
        concurrency_key_postfix = ''
        if 'concurrency' not in job_params:
            concurrency_key_postfix = 'default'

        if 'concurrency_by_app' in job_params:
            concurrency_key_postfix = job_params['concurrency_by_app']

        concurrency_key = "%s_%s" % (job_params['task_type'], concurrency_key_postfix)
        concurrency = int(conf.get_option_value("concurrency", concurrency_key))
        host_infos_groups = util.split_list_into_groups(host_infos_list, concurrency)
        logger.info("__split_hosts_into_groups, job_params=[%s], "
                     "host_infos_list=[%s], host_infos_groups=[%s]" % (
                         job_params, host_infos_list, host_infos_groups))
        return host_infos_groups
            

