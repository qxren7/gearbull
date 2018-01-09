# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: security_strategy.py
Date: 2017/04/12 
"""

import os
import sys
import copy
import logging
import datetime
import socket
from pprint import pprint

from django.db.models import Count

from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.job_engine import runtime_manager
from fuxi_framework.common_lib import beehive_wrapper
from fuxi_framework.common_lib import config_parser_wrapper
from fuxi_framework.common_lib import log

from zhongjing.models import JobInfo
from zhongjing.models import TaskInfo
from zhongjing.host import PhysicalHost
from zhongjing.host import FrozenHost
from zhongjing.actions import TaskTypes
from zhongjing.models import FailLog
from zhongjing.host import CheckHostDeadTask

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
log.init_log("%s/log/security_strategy" % CUR_DIR)
logger = logging.getLogger("security_strategy")
SECURITY_CHECK_STATES = ["NEW", "INIT", "READY", "LAUNCHING", "RUNNING", "PAUSED"]
SECURITY_CHECK_STATES_EXCLUDED = ["CANCELLED", "SUCCESS", "FAILED", "TIMEOUT", "SKIPPED", "ERROR"]
conf = config_parser_wrapper.ConfigParserWrapper("%s/conf/zhongjing.conf" % CUR_DIR)
#conf = config_parser_wrapper.ConfigParserWrapper("%s/conf/zhongjing.conf.test" % CUR_DIR)

OFFLINE_HOSTS_KEY = 'zhongjing_offlie_hosts'

MIX_DEPLOY_APP_PATTERNS = {
        'bs': 'wwwbs',
        'zcache': 'wwwcache',
        'mint': 'wwwmint',
        }

class SecurityStrategy(object):
    """
    安全策略类, 工作流程:
        1、将job要操作的对象保存为 _targets
        2、依次执行filter，过滤掉不符合条件的 target
    """

    @classmethod
    def get_task_num_by_type(cls, _task_type):
        """
        根据任务类型获取当前任务数

        :_task_type: 任务类型
        :returns: 任务数
        """
        jobs = FuxiJobRuntime.objects.filter(job_type='zhongjing', 
                state__in = SECURITY_CHECK_STATES)
        jobs_ids = [j.job_id for j in jobs]
        tasks = FuxiTaskRuntime.objects.filter(job_id__in= jobs_ids, 
                state__in = SECURITY_CHECK_STATES)
        task_infos_Q = TaskInfo.objects.filter(task__in = tasks, task_type = _task_type)
        logger.info("get_task_num_by_type: %s" % task_infos_Q.count())
        return task_infos_Q.count()

    @classmethod
    def is_host_has_apps_threshould(cls, host, apps):
        has_threshould = False
        for app in apps:
            key = "app_%s" % app
            if key in conf.get_options("repair_threshold"):
                has_threshould = True
        return has_threshould

    @classmethod
    def get_apps_by_host(cls, cluster, host):
        """
        获取机器上运行的apps
        对于混部机器，根据app pattern，获取混部的所有apps
        
        :cluster: 集群名
        :host: 机器ip
        :returns: app列表
        """
        host_tags = beehive_wrapper.get_tags_by_host(cluster, host)
        mix_deploy_host_tags = conf.get_option_values("beehive", "mix_deploy_host_tags")
        is_mix_deploy_host = False
        # 如果此机器的tag不是混部tag，直接返回当前机器tags作为apps
        for tag in mix_deploy_host_tags:
            for _host_tag in host_tags:
                if tag in _host_tag:
                    is_mix_deploy_host = True
        if not is_mix_deploy_host:
            return host_tags
        apps = []
        running_apps = beehive_wrapper.get_apps_by_host(cluster, host)
        # 对于混部的app，由于其名字不规范，需要根据 app pattern，获取响应的名字, 例如: pcpr-zcache-0.www.hna -> wwwcache
        print running_apps, host
        for app in running_apps:
            for app_pattern, app_name in MIX_DEPLOY_APP_PATTERNS.items():
                if app_pattern in app:
                    if app_name not in apps:
                        apps.append(app_name)
        return apps


    def __init__(self, job_info, strategy_type = "default"):
        """ """
        # 安全策略关联定义
        # 任务类型: 安全策略列表
        # 例如, 重装机器任务: 安全策略[去重, 过滤指定tags, 阈值保护]
        self._strategy_dict = {
                "default": [self.filter_in_service_hosts, self.filter_duplicate, self.filter_tags, self.filter_threshold],
                "filter_threshold": [self.filter_threshold],
                "filter_in_service_hosts": [self.filter_in_service_hosts],
                "filter_not_safe_for_deploy_agent": [self.filter_not_safe_for_deploy_agent],
                "filter_by_date": [self.filter_by_date],
                TaskTypes.repair_beehive_host: [self.filter_by_date, self.filter_duplicate, self.filter_offline_hosts,
                    self.filter_tags, self.filter_threshold, self.filter_in_service_hosts_threads],

                TaskTypes.repair_alading_host: [self.filter_duplicate, self.filter_offline_hosts,
                    self.filter_tags, self.filter_threshold, self.filter_in_service_hosts_threads],

                TaskTypes.repair_fake_dead_beehive_host: [self.filter_duplicate, self.filter_offline_hosts,
                    self.filter_threshold, self.filter_in_service_hosts_threads],

                TaskTypes.deploy_beehive_agent: [self.filter_duplicate, self.filter_offline_hosts,
                    self.filter_threshold_by_task_type, self.filter_not_safe_for_deploy_agent],

                TaskTypes.reinstall_beehive_host: [self.filter_duplicate, 
                    self.filter_threshold_by_task_type, self.filter_offline_hosts],

                TaskTypes.reinstall_alading_host: [self.filter_duplicate, 
                    self.filter_threshold_by_task_type, self.filter_offline_hosts],

                #TaskTypes.freeze_beehive_host: [self.filter_duplicate, self.filter_freeze_hosts],
                TaskTypes.freeze_beehive_host: [self.filter_duplicate],

                TaskTypes.reinstall_galaxy_host: [self.filter_duplicate],

                TaskTypes.fake_operate: [self.filter_offline_hosts, self.filter_threshold],

                TaskTypes.mount_to_beehive_node: [],

                }

        self._job_info = job_info
        self._host_infos = copy.deepcopy(self._job_info.host_infos)
        self._filters = self._strategy_dict[strategy_type]

    def filter_targets(self):
        """
        security_filter
        """
        for filter in self._filters:
            to_remove_targets = filter()
            self.__remove_from_targets(to_remove_targets)
        return self._host_infos

    def __remove_from_targets(self, to_remove_targets):
        result_host_infos = {}
        for cluster, host_infos_list in self._host_infos.items():
            result_host_infos[cluster] = []
            for host_info in host_infos_list:
                if host_info.host not in to_remove_targets:
                    result_host_infos[cluster].append(host_info)
        self._host_infos = result_host_infos

    def filter_offline_hosts(self):
        """ 过滤无效ip"""
        logger.info("apply filter_offline_hosts strategy.")
        to_remove_targets = []
        for cluster, host_infos_list in self._host_infos.items():
            for host_info in host_infos_list:
                h = host_info.host
                try:
                    socket.gethostbyaddr(h)[0]
                except Exception as e:
                    to_remove_targets.append(h)
                    msg = "filter_offline_hosts: %s is offline cmd 'host %s' get error, \
should not operate, remove it." % (h, h)
                    f = FailLog(task_type='filter_offline_hosts', 
                            entity=h, reason=msg, job_id=self._job_info.job.job_id)
                    f.save()
                    logger.info(msg)
        return to_remove_targets
                   

    def filter_in_service_hosts(self):
        """机器复查策略: 确保要操作的机器是死机或假死、无实例的，避免重装了有服务的机器"""
        logger.info("apply filter_in_service_hosts strategy.")
        to_remove_targets = []
        for cluster, host_infos_list in self._host_infos.items():
            for host_info in host_infos_list:
                h = host_info.host
                #if PhysicalHost.is_alive(h) or PhysicalHost.is_ssh_ok(h):
                # 可以ping通，但是ssh异常的机器，定义为假死机器，可以维修或重装 
                if PhysicalHost.is_alive(h, 5) and PhysicalHost.is_ssh_ok(h):
                    to_remove_targets.append(h)
                    msg = "filter_in_service_hosts: %s is alive or ssh ok, \
should not operate, remove it." % h
                    f = FailLog(task_type='filter_in_service_hosts', 
                            entity=h, reason=msg, job_id=self._job_info.job.job_id)
                    f.save()
                    logger.info(msg)
        return to_remove_targets

    def filter_in_service_hosts_threads(self):
        """机器复查策略: 确保要操作的机器是死机或假死、无实例的，避免重装了有服务的机器"""
        logger.info("apply filter_in_service_hosts strategy.")
        to_remove_targets = []
        to_check_targets = []
        for cluster, host_infos_list in self._host_infos.items():
            for host_info in host_infos_list:
                h = host_info.host
                to_check_targets.append(h)

        check_task = CheckHostDeadTask()
        data = check_task.run(to_check_targets)
        ssh_ok_targets = data['ssh_ok']
        for h in ssh_ok_targets:
            # 可以ping通，但是ssh异常的机器，定义为假死机器，可以维修或重装 
            to_remove_targets.append(h)
            msg = "filter_in_service_hosts: %s is ssh ok,should not operate, remove it." % h
            f = FailLog(task_type='filter_in_service_hosts', 
                    entity=h, reason=msg, job_id=self._job_info.job.job_id)
            f.save()
            logger.info(msg)
        return to_remove_targets

    
    def filter_duplicate(self):
        """去重安全策略: 过滤掉已经处于流程中的target，避免重复处理"""
        logger.info("apply filter_duplicate strategy.")
        to_remove_targets = []

        for cluster, host_infos_list in self._host_infos.items():
            for host_info in host_infos_list:
                h = host_info.host
                tasks = FuxiTaskRuntime.objects.filter(entity_name = h, 
                        state__in = SECURITY_CHECK_STATES)

                # 如果这个entity 已经有任务处于 RUNNING 或 NEW 状态的，再检查其对应的job
                if tasks.exists():
                    for t in tasks:
                        for j in FuxiJobRuntime.objects.filter(job_id=t.job_id):
                            #对应的job，如果是非 TIMEOUT, FAILED 状态的，则过滤
                            if j.state not in SECURITY_CHECK_STATES_EXCLUDED:
                                to_remove_targets.append(h)
                                msg = "filter_duplicate: %s is duplicated, remove it." % h
                                f = FailLog(task_type='filter_duplicate', 
                                        entity=h, reason=msg, job_id=self._job_info.job.job_id)
                                f.save()
                                logger.info(msg)
        return to_remove_targets

    def filter_tags(self):
        """过滤指定tag策略"""
        logger.info("apply filter_tags strategy.")
        exclude_tags = conf.get_option_value("repair_threshold", "tag_not_reapir").split(",")
        to_remove_targets = []

        for cluster, host_infos_list in self._host_infos.items():
            for host_info in host_infos_list:
                h = host_info.host
                host_tags = beehive_wrapper.get_tags_by_host(cluster, h)
                # if this host's tags in exclude_tags
                if set(host_tags).intersection(exclude_tags):
                    to_remove_targets.append(h)
                    msg = "filter_tags: %s should not be operated, \
it has exclude_tags=[%s], remove it." % (h, host_tags)
                    f = FailLog(task_type='filter_tags', 
                            entity=h, reason=msg, job_id=self._job_info.job.job_id)
                    f.save()
                    logger.info(msg)
        return to_remove_targets

    def filter_freeze_hosts(self):
        """ 过滤超出freeze 机器阈值的机器"""
        logger.info("apply filter_freeze_hosts strategy.")
        logger.info("reload conf.")
        conf.reload_conf()
        max_freeze_hosts_count = int(conf.get_option_value("beehive", "max_freeze_hosts_count"))
        to_remove_targets = []
        frozen_hosts = FrozenHost()
        for cluster, host_infos_list in self._host_infos.items():
            for host_info in host_infos_list:
                h = host_info.host
                if frozen_hosts.length() > max_freeze_hosts_count:
                    to_remove_targets.append(h)
                    msg =  "filter_freeze_hosts: %s should not be operated, \
it exceed max_freeze_hosts_count, remove it." % h
                    f = FailLog(task_type='filter_freeze_hosts', 
                            entity=h, reason=msg, job_id=self._job_info.job.job_id)
                    f.save()
                    logger.info(msg)
                else:
                    frozen_hosts.add(h)
        return to_remove_targets

    def filter_threshold_by_task_type(self):
        logger.info("apply filter_threshold_by_task_type strategy.")
        logger.info("reload conf.")
        conf.reload_conf()
        to_remove_targets = []

        if 'skip_threshould' in self._job_info.job_params and\
                self._job_info.job_params['skip_threshould'] == 'true':
            logger.info("skip_threshould")
            return to_remove_targets

        for cluster, host_infos_list in self._host_infos.items():
            for host_info in host_infos_list:
                h = host_info.host
                exceed_type = 'not_filter'

                _task_type = self._job_info.job_params['task_type']
                task_num = SecurityStrategy.get_task_num_by_type(_task_type)
                task_threshold = int(conf.get_option_value("%s_threshold" % _task_type, "default"))
                if task_num >= task_threshold:
                    to_remove_targets.append(h)
                    logger.info("exceed task threshold, task_num=[%s], "
                                "task_threshold=[%s], to_remove_targets=[%s]" % (
                                    task_num, task_threshold, to_remove_targets))
        return to_remove_targets

    def filter_threshold(self):
        """阈值保护策略: 先统计当前按机房、app维度的机器数,当超出阈值时，过滤后续的操作目标"""
        logger.info("apply filter_threshold strategy.")
        logger.info("reload conf.")
        conf.reload_conf()
        to_remove_targets = []
        cur_repair_num_per_cluster, cur_repair_num_per_app = self.__get_cur_repair_nums()

        if 'is_manual' in self._job_info.job_params and\
                self._job_info.job_params['is_manual'] == True:
            return to_remove_targets


        for cluster, host_infos_list in self._host_infos.items():
            for host_info in host_infos_list:
                h = host_info.host
                exceed_type = 'not_filter'

                cluster_threshold = int(conf.get_option_value("repair_threshold", "cluster_%s" % cluster))
                cluster_cur_repair_num = cur_repair_num_per_cluster.get(cluster, 0)
                if cluster_cur_repair_num >= cluster_threshold:
                    #to_remove_targets.append(h)
                    logger.info("exceed cluster threshold, but ignore it, "
                                "cluster threshould disabled, cluster_cur_repair_num=[%s], "
                                "cluster_threshold=[%s], to_remove_targets=[%s]" % (
                                    cluster_cur_repair_num, cluster_threshold, to_remove_targets))
                    exceed_type = 'cluster'
 
                _apps = self._get_apps_by_host(cluster, h)
                # 如果此机器上没有apps，则可以安全进行维修
                if len(_apps) <= 0:
                    continue
                
                # 如果这机器上的apps，都没有配置阈值，则这机器不应该维修
                if not SecurityStrategy.is_host_has_apps_threshould(h, _apps):
                    exceed_type = 'app_not_in_conf'
                    to_remove_targets.append(h)
                    logger.info("filter_threshold: host=[%s] is exceed %s, no threshold in conf,"
                                "apps=[%s], to_remove_targets=[%s]" % (
                                    h, exceed_type, _apps, to_remove_targets))
                    continue

                for _app in _apps:
                    app_threshold = self.__get_app_threshold(_app)
                    app_cur_repair_num = cur_repair_num_per_app.get(_app, 0)

                    # 如果此app 没有配置，则不参与阈值计算
                    if app_threshold == 0:
                        continue

                    if app_cur_repair_num >= app_threshold:
                        logger.debug("cur_repair_num_per_app=[%s]" % (cur_repair_num_per_app))
                        to_remove_targets.append(h)
                        exceed_type = 'app'
                        logger.info("filter_threshold: %s is exceed %s threshold, "
                                    "app_cur_repair_num=[%s], cluster_cur_repair_num=[%s], "
                                    "cluster_threshold=[%s], app_threshold=[%s], "
                                    "app=[%s], to_remove_targets=[%s]" % (h, exceed_type, 
                                        app_cur_repair_num, cluster_cur_repair_num, 
                                        cluster_threshold, app_threshold, _app, to_remove_targets))
                        continue
        return to_remove_targets

    def filter_not_safe_for_deploy_agent(self):
        """ filter_not_safe_for_deploy_agent """
        logger.info("apply filter_not_safe_for_deploy_agent strategy.")
        to_remove_targets = []
        msg = ''
        for cluster, host_infos_list in self._host_infos.items():
            for host_info in host_infos_list:
                h = host_info.host
                if not self.__check_if_host_in_cluster(h, cluster): 
                    to_remove_targets.append(h)
                    msg = "filter_not_safe_for_deploy_agent: %s not in given cluster=[%s], \
remove it." % (h, cluster)
                    f = FailLog(task_type='filter_not_safe_for_deploy_agent', 
                            entity=h, reason=msg, job_id=self._job_info.job.job_id)
                    f.save()
                    logger.info(msg)
                elif self.__check_if_host_has_instance_running(h, cluster):
                    to_remove_targets.append(h)
                    msg = "filter_not_safe_for_deploy_agent: %s has running instances, \
remove it." % h

                    f = FailLog(task_type='filter_not_safe_for_deploy_agent', 
                            entity=h, reason=msg, job_id=self._job_info.job.job_id)
                    f.save()
                    logger.info(msg)
        #logger.info("filter_not_safe_for_deploy_agent: remove hosts=[%s]" % to_remove_targets)
        return to_remove_targets

    def filter_by_date(self):
        """按日期过滤机器，在一个星期内的某一天，只能维修对应机房的机器"""
        logger.info("apply filter_by_date strategy.")
        clusters_can_repair = self.__clusters_today_can_repair()
        to_remove_targets = []

        for cluster, host_infos_list in self._host_infos.items():
            for host_info in host_infos_list:
                h = host_info.host
                if cluster not in clusters_can_repair:
                    to_remove_targets.append(h)
                    msg = "filter_by_date: %s should not be operated, it has cluster=[%s], \
but today clusters_can_repair=[%s], remove it." % (h, cluster, clusters_can_repair)
                    f = FailLog(task_type='filter_by_date', 
                            entity=h, reason=msg, job_id=self._job_info.job.job_id)
                    f.save()
                    logger.info(msg)
        return to_remove_targets

    def __check_if_host_in_cluster(self, host, cluster):
        """ check_if_host_match_cluster """
        return beehive_wrapper.if_host_in_cluster(host, cluster)

    def __check_if_host_match_tag(self, host, tag):
        """ check_if_host_match_tag """
        tags = beehive_wrapper.get_tags_by_host(host)
        result = tag in tags
        return result

    def __check_if_host_has_instance_running(self, host, cluster):
        """ check_if_host_has_instance_running """
        return beehive_wrapper.if_host_has_instance_running(host, cluster)

    def __get_sum_num_by_group(self, query_set, group_name):
        query_result = query_set.values(group_name).annotate(total=Count(group_name)).order_by('total')
        sum_num_per_group = {} 
        for dict in query_result:
            sum_num_per_group[dict[group_name]] =  dict['total']
        return sum_num_per_group

    def __get_app_threshold(self, app):
        key = "app_%s" % app
        logger.info("reload conf.")
        conf.reload_conf()
        if key in conf.get_options("repair_threshold"):
            app_threshold = int(conf.get_option_value("repair_threshold", key))
        else: 
            #app_threshold = int(conf.get_option_value("repair_threshold", "app_default"))  
            app_threshold = 0
        return app_threshold

    def __clusters_today_can_repair(self):
        logger.info("reload conf.")
        conf.reload_conf()
        repair_by_date = dict(conf.cf.items('repair_by_date')) 
        today_weekday = str(datetime.datetime.today().weekday())
        clusters_can_repair = repair_by_date[today_weekday].split(',')
        today_can_repairs = conf.get_option_values("repair_by_date", "today_can_repairs")
        return clusters_can_repair + today_can_repairs
        
    def __get_cur_repair_nums(self):
        jobs = FuxiJobRuntime.objects.filter(job_type='zhongjing', 
                state__in = SECURITY_CHECK_STATES)
        jobs_ids = [j.job_id for j in jobs]
        tasks = FuxiTaskRuntime.objects.filter(job_id__in= jobs_ids, 
                state__in = SECURITY_CHECK_STATES)
        task_infos_Q = TaskInfo.objects.filter(task__in = tasks)
        cur_repair_num_per_cluster = self.__get_sum_num_by_group(task_infos_Q, 'cluster')
        cur_repair_num_per_app = self.__get_sum_num_by_group(task_infos_Q, 'app')
        logger.info("cur_repair_num_per_cluster: %s, cur_repair_num_per_app: %s" % (
            cur_repair_num_per_cluster, cur_repair_num_per_app))
        return cur_repair_num_per_cluster, cur_repair_num_per_app

    def _get_apps_by_host(self, cluster, host):
        if self._job_info.job_params['task_type'] == TaskTypes.repair_fake_dead_beehive_host:
            logger.info("repair_fake_dead_beehive_host, use SecurityStrategy.get_apps_by_host")
            return SecurityStrategy.get_apps_by_host(cluster, host)
        else:
            logger.info("not repair_fake_dead_beehive_host, use beehive_wrapper.get_host_main_tag")
            return beehive_wrapper.get_host_main_tag(cluster, host)


