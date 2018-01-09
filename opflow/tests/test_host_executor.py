# -*- coding: utf-8 -*-
"""
test_executor.py
"""

import os 
import time
import json
import logging
import requests
import commands
import threading


from django.test import TestCase
from django.test import TransactionTestCase

from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.models import FuxiActionRuntime
#from fuxi_framework.job_engine import job_handler
from fuxi_framework.job_engine import job_executor
from fuxi_framework.common_lib import config_parser_wrapper
from fuxi_framework.job_engine import runtime_manager

from zhongjing import views
from zhongjing.security_strategy import SecurityStrategy
from zhongjing.analyzer import Analyzer
from zhongjing.monitor import Monitor
from zhongjing.models import JobInfo
from zhongjing.actions import TaskTypes


CUR_DIR = os.path.abspath(os.path.dirname(__file__))
conf = config_parser_wrapper.ConfigParserWrapper("%s/../conf/zhongjing.conf.test" % CUR_DIR)


logger = logging.getLogger("zhongjing_analyzer")


#class TestHostExecutor(TestCase):
class TestHostExecutor(TransactionTestCase):
    """ TestZhongjingExecutor """
    def setUp(self):
        """ setUp """

        FuxiJobRuntime.objects.all().delete()
        FuxiTaskRuntime.objects.all().delete()
        FuxiActionRuntime.objects.all().delete()

        self.ultron_host_check_cycle_time =  int(conf.get_option_value("ultron", 
            'host_check_cycle_time'))
    


    def generate_test_job(self, job_params):
        """ generate_test_job """
        default_params = views.get_machine_job_params()
        default_params['user'] = 'test'
        default_params['timeout'] = '10000'
        #handler = job_handler.JobHandler()
        job_runtime = runtime_manager.create_job(default_params)
        job_info = JobInfo(
                job = job_runtime, 
                job_params = job_params)
        job_info.save()
        return job_info

    def test_reinstall_beehive_host(self):
        """ test_repair_beehive_host """
        beijing_hosts = [{"host": "10.128.40.47", "reason": "ssh.fail"}] 
        nanjing_hosts = [{"host": "10.206.103.8", "reason": "ssh.fail"}]
        new_job_params =  {
                "hosts": { 
                    "beijing": beijing_hosts, 
                    "nanjing": nanjing_hosts
                    },  
                "task_type": TaskTypes.reinstall_beehive_host,
                } 


        self.analyzer = Analyzer()
        self.job_info = self.generate_test_job(new_job_params)
        self.analyzer.generate_plan(self.job_info.job, self.job_info, self.job_info.host_infos)

        job_num = FuxiJobRuntime.objects.count()
        tasks_num = FuxiTaskRuntime.objects.count()
        actions_num = FuxiActionRuntime.objects.count()
        self.assertEqual(job_num, 1)
        self.assertEqual(tasks_num, 2) 
        self.assertEqual(actions_num, 4)  # (2 host) * (2 tasks each host)



        ultron_checkin(self.job_info.host_infos['beijing'], "END")
        ultron_checkin(self.job_info.host_infos['nanjing'], "END")
        print 'host state after END'
        for t in FuxiTaskRuntime.objects.all():
            res = get_host_status_in_json(t.entity_name)
            print res



        job = FuxiJobRuntime.objects.get(job_id = self.job_info.job_id)
        ultron_checkin(self.job_info.host_infos['beijing'], "DECOMMIT")
        ultron_checkin(self.job_info.host_infos['nanjing'], "DECOMMIT")

        print 'host state after DECOMMIT'
        for t in FuxiTaskRuntime.objects.all():
            res = get_host_status_in_json(t.entity_name)
            self.assertEqual(res['callback_state'], 'DECOMMITTING')


        job_executor.execute(job)
        time.sleep(self.ultron_host_check_cycle_time + 4)
        for t in FuxiTaskRuntime.objects.filter(job_id = job.job_id):
            res = get_host_status_in_json(t.entity_name)
            print res
            self.assertEqual(res['callback_state'], 'DECOMMITTED')

        time.sleep(self.ultron_host_check_cycle_time + 3 )
        ultron_checkin(self.job_info.host_infos['beijing'], "COMMIT")
        ultron_checkin(self.job_info.host_infos['nanjing'], "COMMIT")
        time.sleep(self.ultron_host_check_cycle_time + 3)

        for t in FuxiTaskRuntime.objects.all():
            res = get_host_status_in_json(t.entity_name)
            print res
            self.assertEqual(res['callback_state'], 'COMMITTED')

        time.sleep(self.ultron_host_check_cycle_time + 3)
        m = Monitor()
        print 'call monitor mannuly in test env'
        for t in FuxiTaskRuntime.objects.filter(job_id = job.job_id):
            m.get_task_info(t.task_id)
            self.assertEqual(t.state, "SUCCESS")
            for a in FuxiActionRuntime.objects.filter(task_id = t.task_id):
                self.assertEqual(a.state, "SUCCESS")


    def test_repair_beehive_host(self):
        """ test_repair_beehive_host """

        beijing_hosts = [{"host": "10.128.40.47", "reason": "ssh.fail"}] 
        nanjing_hosts = [{"host": "10.206.103.8", "reason": "ssh.fail"}]
        new_job_params =  {
                "hosts": { 
                    "beijing": beijing_hosts, 
                    "nanjing": nanjing_hosts
                    },  
                "task_type": TaskTypes.reinstall_beehive_host,
                } 

        self.analyzer = Analyzer()
        self.job_info = self.generate_test_job(new_job_params)
        self.analyzer.generate_plan(self.job_info.job, self.job_info, self.job_info.host_infos)

        job_num = FuxiJobRuntime.objects.count()
        tasks_num = FuxiTaskRuntime.objects.count()
        actions_num = FuxiActionRuntime.objects.count()
        self.assertEqual(job_num, 1)
        self.assertEqual(tasks_num, 2) 
        self.assertEqual(actions_num, 4)  # (2 host) * (2 tasks each host)

        ultron_checkin(self.job_info.host_infos['beijing'], "END")
        ultron_checkin(self.job_info.host_infos['nanjing'], "END")
        print 'host state after END'
        for t in FuxiTaskRuntime.objects.all():
            res = get_host_status_in_json(t.entity_name)
            print res

        job = FuxiJobRuntime.objects.get(job_id = self.job_info.job_id)

        ultron_checkin(self.job_info.host_infos['beijing'], "DECOMMIT")
        ultron_checkin(self.job_info.host_infos['nanjing'], "DECOMMIT")

        print 'host state after DECOMMIT'
        for t in FuxiTaskRuntime.objects.all():
            res = get_host_status_in_json(t.entity_name)
            self.assertEqual(res['callback_state'], 'DECOMMITTING')

        job_executor.execute(job)
        time.sleep(self.ultron_host_check_cycle_time + 2)
        print 'host state after repair'
        for t in FuxiTaskRuntime.objects.all():
            res = get_host_status_in_json(t.entity_name)
            print res
            self.assertEqual(res['callback_state'], 'DECOMMITTED')

        time.sleep(self.ultron_host_check_cycle_time + 3)
        ultron_checkin(self.job_info.host_infos['beijing'], "COMMIT")
        ultron_checkin(self.job_info.host_infos['nanjing'], "COMMIT")
        time.sleep(self.ultron_host_check_cycle_time + 3)

        print 'host state after COMMIT'
        for t in FuxiTaskRuntime.objects.all():
            res = get_host_status_in_json(t.entity_name)
            print res
            self.assertEqual(res['callback_state'], 'COMMITTED')

        threads = threading.enumerate()
        # wait all thread finish, or the test database will be destroy
        for t in threads:
            if t.name != 'MainThread':
                print 'join thread:', t.name
                t.join()


def ultron_checkin(host_infos, action):
    """ ultron_checkin """
    for host_info in host_infos:
        h = host_info.host
        cmd='curl -d "host_ip=%s&action=%s&reason=test" http://dev01.com:8889/callback/checkin' %  (h, action)
        status, output = commands.getstatusoutput(cmd)
        print cmd, status, output, 


def get_host_status_in_json(host):
    """ get_host_status_in_json """
    api = 'http://cp01-cos-dev01.cp01:8889/callback/query?host_ip=%s' % host
    ret = '{}'
    try:
        ret = requests.get(api).json()
    except Exception, e:
        logger.error(" get_host_status_in_json http get %s fail, error: %s" % (api, e) )
    return ret
 

def simple_ultron_checkin(hosts, action):
    """ simple_ultron_checkin """
    for h in hosts:
        cmd='curl -d "host_ip=%s&action=%s&reason=test" \
                http://dev01.cp01.com:8889/callback/checkin' % (h, action)
        status, output = commands.getstatusoutput(cmd)
        print cmd, status, output, 
