# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: sli.py
Date: 2017/06/05
"""

import os
import sys  
import time
import Queue  
import logging
import threading  
import traceback
from collections import Counter

from zhongjing.lib import util
from zhongjing.host import PhysicalHost
from fuxi_framework.common_lib import config_parser_wrapper
from fuxi_framework.common_lib import beehive_wrapper
from fuxi_framework.common_lib import log
from fuxi_framework.job_engine import id_generator
from zhongjing.models import Sli

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
log.init_log("%s/../log/sli" % CUR_DIR)
logger = logging.getLogger("sli")

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
conf = config_parser_wrapper.ConfigParserWrapper("%s/../conf/zhongjing.conf" % CUR_DIR)

class SliStat(object):
    """机器各类指标统计"""

    def __init__(self):
        self._result_queue = Queue.Queue()  
        
    def __is_alive(self, host):  
        result = PhysicalHost.is_alive(host, 3)
        self._result_queue.put((host, result)) 

    def __get_alive_stat(self, hosts_groups):
        result = []
        for idx, group in enumerate(hosts_groups):
            print 'group: ', idx
            threads = []
            for host in group:
                t = threading.Thread(target=self.__is_alive, args=(host, ))  
                t.start()  
                threads.append(t)
            for t in threads:
                t.join()  
    
        while not self._result_queue.empty():  
            result.append(self._result_queue.get())  
        return result 

    def __calc_online_rate(self, alive_result, cluster):
        alive_hosts = []
        dead_hosts = []
        for alive_item in alive_result:
            host = alive_item[0]
            is_alive = alive_item[1]
            if is_alive:
                alive_hosts.append(host)
            else:
                dead_hosts.append(host)

        logger.info("cluster=[%s], dead hosts=[%s]" % (cluster, " ".join(dead_hosts)))
            
        online_rate = 1.0 * len(alive_hosts) / len(alive_result)
        return online_rate, dead_hosts

    def __calc_service_alive_rate(self, cluster, app_prefix, product, this_round_uuid):
        details = beehive_wrapper.get_apps_full_detail(cluster, app_prefix)
        for app, instances_dict in details.items():
            abnormal_ins = []
            running_ins = []
            try:
                for ins in instances_dict['app_instance']:
                    if  'runtime' in ins and 'run_state' in ins['runtime'] and\
                            ins['runtime']['run_state'] == 'RUNNING':
                        running_ins.append(ins['app_instance_id'])
                    else:
                        abnormal_ins.append(ins['app_instance_id'])
                all_ins = running_ins + abnormal_ins
                alive_rate = 1.0 * len(running_ins) / len(all_ins)

            except Exception as e:
                alive_rate = 0
                all_ins = []
                traceback.print_exc()
                logger.error(traceback.format_exc())

            sli = Sli(target=product, cluster=cluster, value=alive_rate, 
                total_num=len(all_ins), type='service_alive_rate',
                uuid=this_round_uuid, extra_data=abnormal_ins,
                service=app)
            sli.save()

    def __calc_service_alive_rate_selector__tmp(self, cluster, selector, product, this_round_uuid):
        details = beehive_wrapper.get_apps_full_detail_by_selector(cluster, selector)
        for app, instances_dict in details.items():
            abnormal_ins = []
            running_ins = []
            try:
                for ins in instances_dict['app_instance']:
                    if  'runtime' in ins and 'run_state' in ins['runtime'] and\
                            ins['runtime']['run_state'] == 'RUNNING':
                        running_ins.append(ins['app_instance_id'])
                    else:
                        abnormal_ins.append(ins['app_instance_id'])
                all_ins = running_ins + abnormal_ins
                alive_rate = 1.0 * len(running_ins) / len(all_ins)

            except Exception as e:
                alive_rate = 0
                all_ins = []
                traceback.print_exc()
                logger.error(traceback.format_exc())
            sli = Sli(target=product, cluster=cluster, value=alive_rate, 
                total_num=len(all_ins), type='service_alive_rate',
                uuid=this_round_uuid, extra_data=abnormal_ins,
                service=selector)
            sli.save()

    def __calc_service_alive_rate_selector(self, cluster, selector, product, this_round_uuid):
        details = beehive_wrapper.get_apps_full_detail_by_selector(cluster, selector)
        abnormal_ins = []
        running_ins = []
        for app, instances_dict in details.items():
            for ins in instances_dict['app_instance']:
                try:
                    if  'runtime' in ins and 'run_state' in ins['runtime'] and\
                            ins['runtime']['run_state'] == 'RUNNING':
                        running_ins.append(ins['app_instance_id'])
                    else:
                        abnormal_ins.append(ins['app_instance_id'])
                except Exception as e:
                    traceback.print_exc()
                    logger.error(traceback.format_exc())
                    raise util.EFailedRequest("calc_service_alive_rate fail")

        all_ins = running_ins + abnormal_ins
        if len(all_ins) > 0:
            alive_rate = 1.0 * len(running_ins) / len(all_ins)
        else:
            alive_rate = 0
        print '%s all ins len %s, cluster %s' % (selector, len(all_ins), cluster)
        sli = Sli(target=product, cluster=cluster, value=alive_rate, 
            total_num=len(all_ins), type='service_alive_rate',
            uuid=this_round_uuid, extra_data=abnormal_ins,
            service=selector)
        sli.save()



    def stat_host_online_rate(self, host_tag):
        """ 根据 机器tag 统计online 率"""
        online_rates = []
        total_nums = []
        this_round_uuid = util.gen_uuid()
        dead_hosts = []
        dead_hosts_all = []
        for c in beehive_wrapper.CLUSTERS:
            hosts = beehive_wrapper.get_hosts_list(c, host_tag)
            hosts = filter(None, hosts)
            print host_tag, c, len(hosts)
            if len(hosts) <= 0:
                online_rate = 0
                alive_result = []
                online_rates.append(online_rate)
                total_nums.append(0)
            else:
                hosts_groups = util.split_list_into_groups(hosts, 3000)
                alive_result = self.__get_alive_stat(hosts_groups)
                online_rate, dead_hosts = self.__calc_online_rate(alive_result, c)
                online_rates.append(online_rate)
                dead_hosts_all += dead_hosts
                total_nums.append(len(alive_result))

            sli = Sli(target=host_tag, cluster=c, value=online_rate, 
                    total_num=len(alive_result), type='host_online_rate',
                    uuid=this_round_uuid, extra_data=dead_hosts)
            sli.save()
        online_rates_len = len(filter(None, online_rates))
        if online_rates_len == 0:
            online_rate_all = 0
        else:
            online_rate_all =  1.0 * sum(online_rates) / online_rates_len
        total_num_all = 1.0 * sum(total_nums) 
        sli = Sli(target=host_tag, cluster='all', value=online_rate_all, 
                total_num=total_num_all, type='host_online_rate',
                uuid=this_round_uuid, extra_data=dead_hosts_all)
        sli.save()
        
    def stat_service_alive_rate(self, product):
        """ 根据产品线统计 服务存活率 """
        app_prefix = conf.get_option_value('beehive', '%s_app_prefixs' % product)
        this_round_uuid = util.gen_uuid()
        #app_prefix = 'gssda'
        threads = []
        for c in beehive_wrapper.CLUSTERS:
            t = threading.Thread(target=self.__calc_service_alive_rate, 
                    args=(c, app_prefix, product, this_round_uuid))  
            t.start()  
            threads.append(t)
        for t in threads:
            t.join()  

    def stat_service_alive_rate_by_selector(self, product):
        """ 根据产品线统计 服务存活率 """
        selector = conf.get_option_value('beehive', '%s_selector' % product)
        this_round_uuid = util.gen_uuid()
        #app_prefix = 'gssda'
        threads = []
        for c in beehive_wrapper.CLUSTERS:
            t = threading.Thread(target=self.__calc_service_alive_rate_selector, 
                    args=(c, selector, product, this_round_uuid))  
            t.start()  
            threads.append(t)
        for t in threads:
            t.join()  

    def save_online_rate(self, hosts_info, stat_type):
        """ 根据 机器tag 统计online 率"""
        host_tag = hosts_info['app']
        this_round_uuid = util.gen_uuid()
        dead_hosts = []
        for c in beehive_wrapper.CLUSTERS:
            if c in hosts_info:
                _total_num = hosts_info[c]['total_num']
                dead_num = hosts_info[c]['dead_num']
                dead_hosts = hosts_info[c]['deads']
                online_rate =  1 - (1.0 * dead_num / _total_num)
                #hosts = filter(None, hosts)
            else:
                _total_num = 0
                dead_num = 0
                dead_hosts = []
                online_rate = 0.0
            app = hosts_info['app'] 
            sli = Sli(target=host_tag, cluster=c, value=online_rate, 
                    total_num=_total_num, type=stat_type, service=app,
                    uuid=this_round_uuid, extra_data=dead_hosts)
            sli.save()



