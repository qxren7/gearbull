# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: actions.py
Date: 2017/04/19 
"""

import os 
import sys
import json
import time
import random
import logging
import requests
import commands
import traceback
import socket

from django.conf import settings

from fuxi_framework.entity import Host
from fuxi_framework.common_lib import config_parser_wrapper
from fuxi_framework.common_lib import beehive_wrapper
from fuxi_framework.common_lib import archer_wrapper
from fuxi_framework.common_lib import bns_wrapper
from fuxi_framework.common_lib import log
from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.common_lib import util
from zhongjing.lib.thread_task import ThreadTask
from zhongjing.models import TaskInfo
from zhongjing.models import Sli
from zhongjing.models import FailLog
from zhongjing.models import JsonData

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
log.init_log("%s/log/host_entity" % CUR_DIR)
logger = logging.getLogger("host_entity")

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
conf = config_parser_wrapper.ConfigParserWrapper("%s/conf/zhongjing.conf" % CUR_DIR)
#conf = config_parser_wrapper.ConfigParserWrapper("%s/conf/zhongjing.conf.test" % CUR_DIR)

   

class PhysicalHost(Host):
    """物理机器实体"""
    def __init__(self):
        """@todo: to be defined """
        Host.__init__(self)
        self.ultron = Ultron()



    @classmethod
    def is_alive(self, host, ping_count=600):
        """ 检查机器是否死机"""
        # ping -c 600, 持续10min，如果连续10min ping不通，判定为机器死机
        response = os.system("ping -c %s %s &> /dev/null " % (ping_count, host))
        if response == 0:
          return True
        else:
          return False

    @classmethod
    def is_ssh_ok(self, host):
        """ 检查机器是否登录异常"""
        # TODO
        cmd = "ssh  -n -o StrictHostKeyChecking=no -o PasswordAuthentication=no \
                -o ConnectTimeout=3 -o ServerAliveInterval=5 %s 'ls' " % host
        status, output = commands.getstatusoutput(cmd)
        #print "|",  status, '|', output
        # 0 表示 ok, 255 表示 Permission denied, 说明机器的sshd正常
        if '0' == str(status) or 'Permission denied' in output:
            return True
        else:
            return False

    @classmethod
    def ssh_with_status(self, host):
        """ 检查机器是否登录异常"""
        cmd = "ssh  -n -o StrictHostKeyChecking=no -o PasswordAuthentication=no \
                -o ConnectTimeout=3 -o ServerAliveInterval=5 %s 'ls' " % host
        status, output = commands.getstatusoutput(cmd)
        if '0' == str(status) or 'Permission denied' in output:
            result = {"host": host, "fake_dead": False, "ssh_status": "ok"}
        else:
            result = {"host": host, "fake_dead": True, "ssh_status": output}
        return result 


    @classmethod
    def has_service(self, host):
        """ 检查是否有服务运行 """
        # TODO
        raise util.ENotImplement()

    def repair_beehive_host(self, params):
        """
        0. 只有检测到故障的机器，才会执行维修, 对于无故障机器，不会执行操作
        1. 维修beehive机器前，先freeze
        2. 调用奥创维修，等待完成
        3. 维修完成后，unfreeze机器
        """
        return self.__ultron_operate_host('repair', params)

    def reinstall_beehive_host(self, params):
        """
        0. 直接重装机器，不做是否有故障检查
        1. 其他逻辑同 repair_beehive_host
        """
        #return True
        return self.__ultron_operate_host('reinstall', params)

    def __ultron_operate_host(self, action, params):
        """ __reapir_or_reinstall_beehive_host """
        host = params['host']
        cluster = params['cluster']
        _task_id = params['task_id']
        t = FuxiTaskRuntime.objects.get(task_id=_task_id)

        if not beehive_wrapper.freeze_host(cluster, host):
            msg = 'beehive_wrapper freeze host fail, host=[%s]' % host
            logger.error(msg)
            f = FailLog(task_type='freeze_host', entity=host, reason=msg, job_id=t.job_id)
            f.save()
            return False
        
        if not hasattr(self.ultron, action):
            msg = 'ultron do not support action=[%s]' % action
            logger.error(msg)
            f = FailLog(task_type='not support action', entity=host, reason=msg, job_id=t.job_id)
            f.save()
            return False

        action_method = getattr(self.ultron, action)
        if not action_method(host):
            msg = "%s fail" % action
            f = FailLog(task_type=action, entity=host, reason=msg, job_id=t.job_id)
            f.save()
            return False

        if not beehive_wrapper.unfreeze_host(cluster, host):
            msg = 'beehive_wrapper unfreeze host fail, host=[%s]' % host
            logger.error(msg)
            f = FailLog(task_type='unfreeze_host', entity=host, reason=msg, job_id=t.job_id)
            f.save()
            return False

        return True

    def reinstall_galaxy_host(self, params):
        """
        0. 直接重装galaxy机器，不做是否有故障检查
        """
        host = params['host']
        cluster = params['cluster']
        _task_id = params['task_id']
        t = FuxiTaskRuntime.objects.get(task_id=_task_id)

        logger.info('reinstall_galaxy_host start: host=[%s], task=[%s]' % (host, _task_id))
        if not self.ultron.reinstall(host):
            logger.error('reinstall_galaxy_host: host=[%s], task=[%s]' % (host, _task_id))
            msg = "reinstall galaxy host fail" 
            f = FailLog(task_type='reinstall_galaxy_host', entity=host, reason=msg, job_id=t.job_id)
            f.save()
            return False
        logger.info('reinstall_galaxy_host end: host=[%s], task=[%s]' % (host, _task_id))
        return True


    def quick_init(self, params):
        """ 执行机器初始化"""
        host = params['host']
        cluster = params['cluster']
        pass
       
    def deploy_single_beehive_agent(self, params):
        """ deploy_single_beehive_agent """
        host = params['host']
        cluster = params['cluster']
        _task_id = params['task_id']
        #result, urls = archer_wrapper.deploy_beehive_agent(_task_id, cluster, [host])
        deployer = Deployer()
        result, urls = deployer.deploy_beehive_agent(_task_id, cluster, [host])
        if result:
            try:
                # save archer urls, so that we can check archer log
                task = FuxiTaskRuntime.objects.get(task_id = _task_id)
                task_info = task.taskinfo

                data = {'archer_urls': urls}
                task_info.update_task_data(data)
                return archer_wrapper.is_archer_tasks_finish(urls)
            except Exception as e:
                import traceback
                logger.error(traceback.format_exc())
                logger.error('deploy_single_beehive_agent fail, error=[%s]' % e)
                return False

        else:
            logger.error('deploy_single_beehive_agent fail, urls=[%s]' % urls)
            return False

    def mount_to_beehive_node(self, params):
        """将其他产品线的机器，挂载到beehive agent节点下, 不动原来的节点 """

        cmd_template = 'add_host_to_service -p %s -t %s -s %s -k %s %s'
        agent_services = dict(conf.cf.items('beehive_agent_services'))

        ip = params['host']
        if ip.startswith('10.'):
            try:
                host = socket.gethostbyaddr(ip)[0]
            except Exception as e:
                logger.error('mount_to_beehive_node get hostname error, '
                            'ip=[%s], error=[%s]' % (ip, e))
                return False
        else:
            host = ip

        cluster = params['cluster']
        _task_id = params['task_id']
        product_line = params['extra_params']['product_line']
        noah_token = params['extra_params']['noah_token']
        service = agent_services[cluster]
        cmd = cmd_template % (product_line, noah_token, service, WWW_BNS_TOKEN, host)

        # 随机等待一定秒数，为了避免bns压力过大，加入机器失败导致的长尾 
        time.sleep(random.uniform(1, 20))

        status, output = commands.getstatusoutput(cmd)
        cmd_result = status == 0 and 'success' in output and 'true' in output
        logger.info('mount_to_beehive_node %s, cmd=[%s], status=[%s], output=[%s]' % (
            cmd_result, cmd, status, output))

        if cmd_result:
            # save task result, so that we can check it later
            data = {"cmd": cmd, "result": output}
            task_info = TaskInfo.objects.get(task_id = _task_id)
            #_task_data = task_info.task_data
            #_task_data.update(data)
            #task_info.task_data = _task_data
            #task_info.save()
            task_info.update_task_data(data)
            return True
        else:
            return False

    def fake_operate(self, params):
        """ fake_operate """
        return True

    def repair_common_host(self, host):
        """ repair_common_host """
        pass

    def reinstall(self):
        """ reinstall"""
        pass

    def reinit(self):
        """ reinit"""
        pass

    def reboot(self):
        """ reboot"""
        pass

    def freeze(self, params):
        """ freeze beehive host """
        host = params['host']
        cluster = params['cluster']
        if beehive_wrapper.freeze_host(cluster, host):
            return True
        else:
            logger.error('beehive_wrapper freeze host fail, host=[%s]' % host)
            return False
        
    def unfreeze(self, params):
        """ unfreeze beehive_wrapper host """
        host = params['host']
        cluster = params['cluster']
        if beehive_wrapper.unfreeze_host(cluster, host):
            return True
        else:
            logger.error('beehive_wrapper unfreeze host fail, host=[%s]' % host)
            return False

    def chownwork(self, params):
        """ chownwork """
        host = params['host']
        ccs = CcsWrapper()
        ccs.gen_cred()
        cmd = 'chowm work.work  /home/work'
        job_id = ccs.add_job(self, cmd, '', 1, 60)


class Deployer(object):
    """机器环境部署工具"""

    def deploy_beehive_agent(self, task_id, cluster, hosts):
        """部署beehive agent服务
    
        :agent_version: agent scm 四位版本号
        :cluster: 需要部署agent的机器所属cluster
        :hosts: 机器列表
        :returns: True/False
    
        """
        archer_urls = None
        host = hosts[0]
        t = FuxiTaskRuntime.objects.get(task_id=task_id)
        is_succ, node = bns_wrapper.is_host_in_node(hosts[0], "agent")
        #logger.info(' debug ,,,  is_succ=[%s], node=[%s], host=[%s] ' % (is_succ, node, host ))
        if not is_succ:
            #bns_wrapper.add_host_to_node(cluster, host)
            if not bns_wrapper.add_host_to_node(cluster, host):
                msg = "add %s to %s fail" % (host, cluster)
                logger.error(msg)
                f = FailLog(task_type='is_host_in_node', 
                        entity=host, reason=msg, job_id=t.job_id)
                f.save()
                return (False, None)
    
    
        result, archer_urls = self.call_archer_to_deploy_agent(task_id, cluster, node, host)
        if not result:
            msg = "call_archer_to_deploy_agent fail, archer_urls=[%s]" % archer_urls
            logger.error(msg)
            f = FailLog(task_type='call_archer_to_deploy_agent', 
                    entity=host, reason=msg, job_id=t.job_id)
            f.save()
            return (False, archer_urls)
        else:
            return (True, archer_urls)

    def call_archer_to_deploy_agent(self, task_id, cluster, node, host):
        """ 调用archer部署agent """
        # 随机sleep一定时间，否则并发发起请求时，archer 会失败
        time.sleep(random.randint(0, 10))
        agent_scm_version = self.__get_beehive_agent_version()
        deploy_path = "/home/work/agent"
        tmp_des_path = archer_wrapper.generate_archer_des(task_id, node, deploy_path, host)
        agent_value_confs = {
                'beijing': "value/agent.www.jx/conf_template.value",  
                'hangzhou': "value/agent.www.hz/conf_template.value",
                'hna': "value/agent.www.hna/conf_template.value", 
                'hnb': "value/agent.www.hnb/conf_template.value",
                'nanjing': "value/agent.www.nj/conf_template.value",
                'shanghai': "value/agent.www.sh01/conf_template.value",
                'tucheng': "value/agent.www.tc/conf_template.value",
                'hb': "value/agent.www.hb/conf_template.value",
                'yangquan': "value/agent.www.yq/conf_template.value",
            }
    
        archer_result = {}
        agent_value_conf = agent_value_confs[cluster]
        cmd = '''  cd %s  &&   archer  --machinetimeout=900 \
    --buildid=123 --buildplatform=64  --token=xx\
    --serverlist=servers.des -f deploy.des --module=module/eden/agent \
    --scm --version=%s  --invalue=%s --diff  --totaltime=0     ''' % (
                        tmp_des_path, agent_scm_version, agent_value_conf)
        status, output = commands.getstatusoutput(cmd)
        logger.info('call_archer_to_deploy_agent: cmd=[%s], status=[%s], output=[%s]' % (
            cmd, status, output))
        urls = archer_wrapper.parse_archer_output(output)
        archer_result[cluster]  = {
                'status': status, 
                'output': output, 
                'urls': urls, 
                'agent_version': agent_scm_version
                }
        return (True, urls)
       
    def __get_beehive_agent_version(self):
        url = 'http://master.archer.com/management/api/getreleaseinfo?\
process_name=ps_se_eden_release_agent'
        res = requests.get(url).json()
        version = res['data'][0]
        logger.info('get agent version from 863, version=[%s]' % version)
        return version

class DeadHostTask(ThreadTask):
    """并发获取死机信息任务"""
    def task(self, host):
        cluster = beehive_wrapper.get_host_cluster(host)
        self._result_queue.put((host, cluster))
        
class CheckHostDeadTask(ThreadTask):
    """并发获取死机信息任务"""
    def task(self, host):
        if not PhysicalHost.is_alive(host, 5):
            self._result_queue.put((host, 'real_dead'))
        elif PhysicalHost.is_alive(host, 10) and not PhysicalHost.is_ssh_ok(host):
            self._result_queue.put((host, 'ssh_fail'))
        else:
            self._result_queue.put((host, 'ssh_ok'))
 
    def collect(self):
        """ collect """
        results = {'real_dead': [], 'ssh_fail': [], 'ssh_ok': []}
        while not self._result_queue.empty():  
            host, dead_type = self._result_queue.get()
            results[dead_type].append(host)
        return results

class CheckHostFakeDeadTask(ThreadTask):
    """并发获取死机信息任务"""
    def task(self, host):
        result = PhysicalHost.ssh_with_status(host)
        self._result_queue.put(result)
 
    def collect(self):
        """ collect """
        results = []
        while not self._result_queue.empty():  
            # result = {"host": host, "fake_dead": True, "ssh_status": output}
            ssh_result = self._result_queue.get()
            if ssh_result["fake_dead"]:
                results.append(ssh_result)
        return results


class Ultron(object):
    """奥创机器操作类"""


    ULTRON_HOST = 'common.callback.matrix.com'
    ULTRON_SITE = 'http://%s:8889' % ULTRON_HOST
    ULTRON_API = {
            "repair": "%s/callback/push_repair_machines" % ULTRON_SITE, 
            "reinstall": "%s/callback/push_reinstall_machines" % ULTRON_SITE, 
            "pre_handover": "%s/callback/pre_handover_machine_list?per_page=5000" % ULTRON_SITE,
            "push_handover": "%s/callback/push_pre_handover_machines" % ULTRON_SITE,
            "state": "http://{server}:9784/state/{{_host}}/last".format(server = ULTRON_HOST),
            "get_fail": "http://{server}:9784/report/{{_host}}/last".format(server = ULTRON_HOST),
            "get_fails_by_pool_n_type": "http://{server}:9784/report/all?\
pool={{pool}}&per_page=1000000&type={{ftype}}".format(server = ULTRON_HOST),
            "get_all_fails": "http://%s:9784/report/all?pool=ps_bcbs\
&pool=ps_ac&pool=ps_mint_hna&pool=ps_mint_non_hna\
&pool=ps-ndi&per_page=1000000" % ULTRON_HOST,
            "get_fails_by_type": "http://{server}:9784/report/all?\
pool=ps_bcbs&pool=ps_ac&pool=ps_mint_hna&pool=ps_mint_non_hna\
&pool=ps-ndi&per_page=1000000&type={{ftype}}".format(
                        server = ULTRON_HOST),
            "get_galaxy_fails": "http://%s:9784/report/all?pool=galaxy_nvme\
&pool=galaxy_main&pool=galaxy_linkbase&per_page=1000000" % ULTRON_HOST,
            }
    
    TEST_ULTRON_HOST = 'cp01-cos-dev01.cp01'
    TEST_ULTRON_SITE = 'http://%s:8889' % TEST_ULTRON_HOST
    TEST_ULTRON_API = {
            "repair": "%s/callback/push_repair_machines" % TEST_ULTRON_SITE,
            "reinstall": "%s/callback/push_reinstall_machines" % TEST_ULTRON_SITE, 
            "state": "http://{server}:9784/state/{{_host}}/last".format(server = ULTRON_HOST),
            "pre_handover": "%s/callback/pre_handover_machine_list" % TEST_ULTRON_SITE,
            "push_handover": "%s/callback/push_pre_handover_machines" % TEST_ULTRON_SITE,
            "checkin": "%s/callback/checkin" % TEST_ULTRON_SITE,
            }

    APP_POOL_MAPS = {
            "wwwbs": ['www_beehive_bcbs_root_ssd', 'www_beehive_bcbs_home_ssd'],
            "wwwac": ['ps_ac'],
            "wwwaladdin": ['ae'],
            "wwwda": ['da'],
            "wwwus": ['www_beehive_us'],
            "wwwmint": ['ps_mint_hna', 'ps_mint_non_hna'],
            "galaxy": ['galaxy_nvme', 'galaxy_main', 'galaxy_linkbase'],
            }

    def __init__(self):
        """@todo: to be defined """
        
        # used in prodution env
        self.ultron_api = Ultron.ULTRON_API
        self.ultron_token = Ultron.ULTRON_TOKEN

        self.ultron_host_check_cycle_time =  int(conf.get_option_value("ultron", 
            'host_check_cycle_time'))
        
    def repair(self, host):
        """
        1. 调用奥创接口发送维修请求, 只有被奥创判定为有故障的机器，才会执行维修
        2. 循环查询机器状态，直到机器维修完成
        3. 机器维修完成后，向奥创发送handover请求，确认业务已经回收此机器投入使用, 此后奥创不可再对此机器有后续操作
        """
        api = self.ultron_api['repair'] 
        result =  self.__repair_or_reinstall(api, host)
        return result

    def reinstall(self, host):
        """
        1. 调用奥创接口发送重装请求, 重装接口不会进行故障判断，即正常机器也会被执行重装，由调用方保证调用正确性
        2. 循环查询机器状态，直到机器维修完成
        3. 机器维修完成后，向奥创发送handover请求，确认业务已经回收此机器投入使用, 此后奥创不可再对此机器有后续操作
        """
        api = self.ultron_api['reinstall'] 
        result =  self.__repair_or_reinstall(api, host)
        return result

    def quick_init(self, host):
        """ 执行机器初始化，host绑定了初始化策略组"""
        return False
        result = False
        api = self.ultron_api['reinstall'] 
        if self.__send_ultron_operation_request(request_api, host):
            while True:
                if self.__is_ultron_operation_ok(host):
                    self.__handover_host(host)
                    result = True
                    break
                else:
                    logger.debug("check ultron host state=[%s]" % (host))
                    time.sleep(self.ultron_host_check_cycle_time)
        else:
            logger.error("ultron operation fail, request_api=[%s], host=[%s]" % (
                request_api, host))
        logger.info('ultron operation host done, request_api=[%s], host=[%s]' % (
            request_api, host))
        return result

    def __repair_or_reinstall(self, request_api, host):
        """ 故障维修和重装接口逻辑一样 """
        logger.info('ultron host operation start: request_api=[%s], host=[%s]' % (
            request_api, host))
        result = False
        host = host.replace('\r', "")
        if self.__send_ultron_operation_request(request_api, host):
            while True:
                self.save_fail_log('reinstall_beehive_host', host)
                if self.__is_ultron_operation_ok(host):
                    self.__handover_host(host)
                    result = True
                    logger.info("ultron operation host done, "
                                "request_api=[%s], host=[%s], result=[%s]" % (
                        request_api, host, result))
                    break
                else:
                    logger.info("check ultron host state=[%s]" % (host))
                    time.sleep(self.ultron_host_check_cycle_time)
        else:
            logger.error("ultron operation fail, request_api=[%s], host=[%s]" % (
                request_api, host))

        logger.info('ultron host operation done: request_api=[%s], host=[%s]' % (
            request_api, host))
        return result

    def __send_ultron_operation_request(self, api, host):
        """调用奥创接口发送reapir机器请求

        :host: 待维修机器
        :returns: 如果奥创接口返回成功，本方法返回True，否则返回False

        """
        #api = self.ultron_api['repair'] 
        to_repair_hosts = [host]
        repair_data = {"ip": to_repair_hosts, "token":self.ultron_token}
        result = False
        try:
            res = requests.post(api, data = json.dumps(repair_data)).json()  
            logger.info("ultron request=[%s], params=[%s], resonse=[%s]" % (
                api, repair_data, res))
            if 'error_code' in res and res['error_code'] == 0:
                result = True
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            logger.error("request=[%s], error=[%s]" % (api, e))
        return result

    def __is_ultron_operation_ok(self, host):
        """ is_ultron_reapir_ok """
        api = self.ultron_api['pre_handover'] 
        result = False
        logger.info("check ultron status, host=[%s], api=[%s]" % (host, api))
        try:
            res = requests.get(api).json()
            pre_handover_hosts = res['result']['machines']
            logger.info("check ultron status, host=[%s],  is host in pre_handover_hosts=[%s]" % (
                host, host in pre_handover_hosts))
            if host in pre_handover_hosts:
                result = True
             
        except Exception as e:
            logger.error("call ultron fail, api:[%s],  error=[%s]" % (api, e))
        
        return result

    def is_ultron_operation_ok_tmp(self, host):
        """ is_ultron_reapir_ok """
        api = self.ultron_api['pre_handover'] 
        result = False
        logger.info("check ultron status, host=[%s], api=[%s]" % (host, api))
        try:
            res = requests.get(api).json()
            pre_handover_hosts = res['result']['machines']
            logger.info("check ultron status, host=[%s],  is host in pre_handover_hosts=[%s]" % (
                host, host in pre_handover_hosts))
            if host in pre_handover_hosts:
                result = True
             
        except Exception as e:
            logger.error("call ultron fail, api:[%s],  error=[%s]" % (api, e))
        
        return result


    def __handover_host(self, host):
        """ handover_host """
        if not self.__is_ultron_operation_ok(host):
            logger.error("try to handover host=[%s] not in pre_handover_hosts, \
                    please check it." % (host))
            return False
            
        api = self.ultron_api['push_handover'] 
        to_handover_hosts = [host]
        logger.info("handover host in ultron, host=[%s], api=[%s]" % (host, api))

        params = {"ip": to_handover_hosts, "token":self.ultron_token}
        result = False
        try:
            res = requests.post(api, data = json.dumps(params)).json()
            if res['error_code'] == 0 and res['result']['success_num'] == 1:
                result = True
            logger.info('ultron handover api=[%s], data=[%s], response=[%s]' % (api, params, res))
        except Exception as e:
            logger.error('ultron handover api=[%s], data=[%s], error=[%s]' % (api, params, e))
            
        return result

    def save_fail_log(self, _task_type, host):
        try:
            states = self.host_state(host)
            if 'error_status' in states and len(states['error_status']) > 0:
                _reason = str(states['error_status'])
                f = FailLog(task_type=_task_type, entity=host, reason=_reason)
                f.save()
        except Exception as e:
            logger.error('save_fail_log error, _task_type=[%s], host=[%s], error=[%s]' % (
                _task_type, host, e))
        

    def host_state(self, host):
        """ get_host_status_in_json """
        api = self.ultron_api['state'].format(_host=host)
        ret = {}
        try:
            ret = requests.get(api).json()
        except Exception, e:
            logger.error("get_host_status_in_json http get %s fail, error=[%s]" % (api, e) )
        return ret

    def get_fail(self, host):
        """ 获取单台机器故障信息 """
        api = self.ultron_api['get_fail'].format(_host=host)
        ret = {"host": host}
        try:
            res = requests.get(api).json()
            fails = []
            for r in res['reports']:
                if r['type'] == "config.diff": continue
                item = {'type': r['type'], 'details': r["details"]}
                fails.append(item)

                
            ret['fails'] = fails 
            ret['in_ultron'] = True
        except Exception as e:
            logger.error("get_host_status_in_json http get %s fail, error=[%s]" % (api, e))
            ret['in_ultron'] = False
        return ret


    def get_fail_reports(self, _pool, _fail_type):
        """ 根据机器pool和失败类型查询机器故障信息 """
        ssh_lost_hosts = []
        print 'get_fail_hosts start'
        fail_hosts_reports  = []
        try:
            fails = self.get_fails(_pool, _fail_type)
            for detail in fails['data']:
                item = {"host": detail['ip'], "report_time": detail["reports"][0]["create_time"]}
                fail_hosts_reports.append(item)
            return fail_hosts_reports
        except Exception, e:
            print e
            traceback.print_exc()
            logger.error("get_fail_reports, error=[%s]" % (e))

        return fail_hosts_reports

    def get_galaxy_fails(self):
        """ 根据机器pool和失败类型查询机器故障信息 """
        ssh_lost_hosts = []
        fail_hosts_reports  = []

        try:
            api = Ultron.ULTRON_API['get_galaxy_fails']
            fails= requests.get(api).json()
            for detail in fails['data']:
                for report in detail['reports']:
                    item = {"host": detail['ip'], 
                            "report_time": report["create_time"],
                            "type": report['type']
                            }
                    fail_hosts_reports.append(item)
            return fail_hosts_reports
        except Exception as e:
            traceback.print_exc()
            logger.error("get_fail_reports, error=[%s]" % (e))

        return fail_hosts_reports



    def get_fail_hosts(self, _pool, _fail_type):
        """ 根据机器pool和失败类型查询机器 """
        ssh_lost_hosts = []
        print 'get_fail_hosts start'
        try:
            fails = self.get_fails(_pool, _fail_type)
            ssh_lost_hosts = [detail['ip'] for detail in fails['data']]

            #if len(ssh_lost_hosts) > 10:
            #    ssh_lost_hosts = ssh_lost_hosts[0:10]
            #print 'ssh_lost_hosts', len(ssh_lost_hosts)

            return ssh_lost_hosts
        except Exception, e:
            print e
            traceback.print_exc()
            logger.error("get_fail_hosts, error=[%s]" % (e))

        return ssh_lost_hosts

    def get_dead_hosts(self, _pool, _fail_type):
        """ 获取纯死机列表 """
        dead_hosts = self.get_fail_hosts(_pool, _fail_type)
        dead_hosts_task = DeadHostTask()
        result = dead_hosts_task.run(dead_hosts)
        return result


    def get_root_env_inconsistent(self, _pool, _fail_type):
        """ 获取root环境不一致性信息"""
        env_infos = []
        try:
            fails = self.get_fails(_pool, _fail_type)
            for detail in fails['data']:
                s = Sli()
                s.host = detail['ip']
                s.fail_type = "config.diff"
                s.state = 'ignore'
                s.create_time = 'not started'
                s.detail = "<br>".join(detail['reports'][0]['details']['diff_log'].split(';'))
                env_infos.append(s)
            return env_infos
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error("get_fail_hosts, error=[%s]" % (e))
        return env_infos

    def get_fails(self, _pool, _fail_type):
        """ 根据机器pool和失败类型查询机器 """
        api = Ultron.ULTRON_API['get_fails_by_pool_n_type'].format(pool=_pool, ftype=_fail_type)
        res = {}
        try:
            res = requests.get(api).json()
        except Exception as e:
            logger.error("get_fail_hosts fail, api=[%s], error=[%s]" % (api, e))
        return res


class Alading(object):
    """alading 业务机器hook方法 """

    def __init__(self):
        self._hook_server = 'http://10.36.166.12:9100'
        self._pre_hook = '%s/prehook' % self._hook_server
        self._post_hook = '%s/posthook' % self._hook_server

        self._pre_hooks = {
                "wwwaladdin_ala-root": "%s/alaroot_pre_hook" % self._hook_server,
                "wwwaladdin_gssda": "%s/gssda_pre_hook" % self._hook_server,
                "wwwaladdin_ae": '%s/pre_hook' % self._hook_server,
                }
        self._post_hooks = {
                "wwwaladdin_ala-root": "%s/alaroot_post_hook" % self._hook_server,
                "wwwaladdin_gssda": "%s/gssda_post_hook" % self._hook_server,
                "wwwaladdin_ae": '%s/post_hook' % self._hook_server,
                }



    def pre_hook(self, params):
        """ 阿拉丁机器维修前置 hook """
        return self.__post_data(self._pre_hook, params)
        logger.info("fake_operate host pre_hook, return True, params=[%s]" % (params))
        return True

    def post_hook(self, params):
        """ 阿拉丁机器维修后置 hook """
        return self.__post_data(self._post_hook, params)
        logger.info("fake_operate host post_hook, return True, params=[%s]" % (params))
        return True

    def __post_data(self, api, params):
        result = False
        try:
            allowed_apps = conf.get_option_values("beehive", "wwwaladdin_app_prefixs")
            host = params['host']
            cluster = params['cluster']
            tags = beehive_wrapper.get_tags_by_host(cluster, host)
            tag = None
            for t in tags:
                if t in allowed_apps:
                    tag = t
                    break
            if not tag:
                logger.error("host=[%s] has no tags in allowed_apps=[%s], return False." % (
                    host, allowed_apps))
                return False
                 
            post_data = {"ip": host, "app": tag}
            res = requests.post(api, data = json.dumps(post_data)).json()  
            logger.info("alading request=[%s], params=[%s], resonse=[%s]" % (
                api, post_data, res))
            if 'suc' in res and res['suc'] == 'true':
                result = True
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error("request=[%s], error=[%s]" % (api, e))
        return result


class FrozenHost(object):
    """ freeze 机器数计数器"""

    def __init__(self):
        """ __init__ """
        data, created = JsonData.objects.get_or_create(key='FrozenHost')
        if created:
            data.json_data = []
            data.save()
        self.hosts_data = data

    def add(self, host):
        """ add """
        self.hosts_data.json_data.append(host)
        self.hosts_data.save()

    def remove(self, host):
        """ remove """
        if host in self.hosts_data.json_data:
            self.hosts_data.json_data.remove(host)
            self.hosts_data.save()

    def length(self):
        """ length """
        return len(self.hosts_data.json_data)
        
        
