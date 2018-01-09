"""
test_analyzer.py
"""

import os
import time

from django.test import TestCase

from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.models import FuxiActionRuntime
from fuxi_framework.job_engine import runtime_manager
from fuxi_framework.common_lib import config_parser_wrapper

from zhongjing import views
from zhongjing.security_strategy import SecurityStrategy
from zhongjing.analyzer import Analyzer
from zhongjing.models import JobInfo
from zhongjing.actions import TaskTypes

class TestSecurityStrategy(TestCase):
    """ TestSecurityStrategy"""

    def setUp(self):
        """ setUp """
        self.test_job_params =  {
                "hosts": { 
                    "beijing": [
                        {"host": "h1", "reason": "ssh.fail"},
                        {"host": "h2", "reason": "ssh.fail"},
                        #{"host": "h8", "reason": "ssh.fail"},
                        #{"host": "h9", "reason": "ssh.fail"},
                        ], 
                    "nanjing": [
                        {"host": "h3", "reason": "ssh.fail"},
                        {"host": "h4", "reason": "ssh.fail"},
                        ],
                    },  
                "task_type": TaskTypes.reinstall_beehive_host,
                } 

        self.analyzer = Analyzer()
        self.job_info = self.generate_test_job(self.test_job_params)
        self.analyzer.generate_plan(self.job_info.job, self.job_info, self.job_info.host_infos)

    def generate_test_job(self, job_params):
        """ generate_test_job """
        #time.sleep(0.5)
        default_params = views.get_machine_job_params('')
        default_params['user'] = 'test'
        default_params['timeout'] = '10000'
        job_runtime = runtime_manager.create_job(default_params)
        job_info = JobInfo(
                job = job_runtime, 
                job_params = job_params)
        job_info.save()
        return job_info

    def test_save_job_and_tasks_and_actions(self):
        """ test_save_job_and_tasks """
        job_num = FuxiJobRuntime.objects.count()
        tasks_num = FuxiTaskRuntime.objects.count()
        actions_num = FuxiActionRuntime.objects.count()
        self.assertEqual(job_num, 1) # 1 job
        self.assertEqual(tasks_num, 4) # h1, h2, h3, h4; 4 hosts
        self.assertEqual(actions_num, 8) # 4 * 2 = 8 actions

    def test_filter_duplicate(self):
        """ test_filter_duplicate """

        new_job_params =  {
                "hosts": { 
                    "beijing": [
                        {"host": "h1", "reason": "ssh.fail"},
                        {"host": "h5", "reason": "ssh.fail"},
                        ], 
                    "nanjing": [
                        {"host": "h3", "reason": "ssh.fail"},
                        {"host": "h6", "reason": "ssh.fail"},
                        ],
                    },  
                "task_type": TaskTypes.reinstall_beehive_host,
                } 

        #time.sleep(1) # TODO to delete
        job_info = self.generate_test_job(new_job_params)
        security_strategy = SecurityStrategy(job_info, TaskTypes.repair_beehive_host)
        hosts_info = security_strategy.filter_targets()
        beijing_hosts = [host_info.host for host_info in hosts_info['beijing']]
        expected_hosts = ["h5"]
        self.assertEqual(expected_hosts, beijing_hosts)
        nanjing_hosts = [host_info.host for host_info in hosts_info['nanjing']]
        expected_hosts = ["h6"]
        self.assertEqual(expected_hosts, nanjing_hosts)

        self.analyzer.generate_plan(job_info.job, job_info, hosts_info)
        job_num = FuxiJobRuntime.objects.count()
        tasks_num = FuxiTaskRuntime.objects.count()
        self.assertEqual(job_num, 2)
        self.assertEqual(tasks_num, 6) # h1, h2, h3, h4; 4 hosts, + h5, h6

    def test_filter_tags(self):
        """ test_filter_tags """

        beijing_hosts = [{"host": "10.44.166.53", "reason": "ssh.fail"}] 
        nanjing_hosts = [{"host": "10.194.74.49", "reason": "ssh.fail"}]
        new_job_params =  {
                "hosts": { 
                    "beijing": beijing_hosts, 
                    "nanjing": nanjing_hosts
                    },  
                "task_type": TaskTypes.repair_beehive_host,
                } 

        #time.sleep(1) # TODO to delete
        job_info = self.generate_test_job(new_job_params)
        security_strategy = SecurityStrategy(job_info, TaskTypes.repair_beehive_host)
        hosts_info = security_strategy.filter_targets()
        beijing_hosts_after_filter = hosts_info['beijing']
        #self.assertEqual(beijing_hosts_after_filter, beijing_hosts)
        self.assertEqual(beijing_hosts_after_filter, [])
        nanjing_hosts_after_filter = hosts_info['nanjing']
        self.assertEqual(nanjing_hosts_after_filter, [])

    def test_filter_threshold(self):
        """ test_filter_threshold """

        beijing_hosts = [{"host": "10.128.101.27", "reason": "ssh.fail"}] 
        nanjing_hosts = [{"host": "10.193.103.16", "reason": "ssh.fail"}]
        new_job_params =  {
                "hosts": { 
                    "beijing": beijing_hosts, 
                    "nanjing": nanjing_hosts
                    },  
                "task_type": TaskTypes.reinstall_beehive_host,
                } 

        #time.sleep(1) # TODO to delete
        job_info = self.generate_test_job(new_job_params)
        security_strategy = SecurityStrategy(job_info, 'filter_threshold')
        hosts_info = security_strategy.filter_targets()
        beijing_hosts_after_filter = hosts_info['beijing']
        self.assertEqual(beijing_hosts_after_filter, [])
        #self.assertEqual(beijing_hosts_after_filter, beijing_hosts)
        nanjing_hosts_after_filter = hosts_info['nanjing']
        self.assertEqual(nanjing_hosts_after_filter, [])
        #self.assertEqual(nanjing_hosts_after_filter, nanjing_hosts)

    def test_filter_in_service_hosts(self):
        """ test_filter_threshold """
        bj_h = "10.44.132.25"
        bj_h2 = '10.57.66.74'
        nj_h = "10.58.116.76"
        beijing_hosts = [{"host": bj_h, "reason": "alive.host"},
                        {"host": bj_h2, "reason": "dead.host"},
                ] 
        nanjing_hosts = [{"host": nj_h, "reason": "dead.host"}]
        new_job_params =  {
                "hosts": { 
                    "beijing": beijing_hosts, 
                    "nanjing": nanjing_hosts
                    },  
                "task_type": TaskTypes.reinstall_beehive_host,
                } 

        #time.sleep(1) # TODO to delete
        job_info = self.generate_test_job(new_job_params)
        security_strategy = SecurityStrategy(job_info, "filter_in_service_hosts")
        hosts_info = security_strategy.filter_targets()
        beijing_hosts_after_filter = [host_info.host for host_info in hosts_info['beijing']]
        expected_hosts = [bj_h2]
        self.assertEqual(beijing_hosts_after_filter, expected_hosts)
        #self.assertEqual(beijing_hosts_after_filter, beijing_hosts)
        nanjing_hosts_after_filter = [host_info.host for host_info in hosts_info['nanjing']]
        expected_hosts = [nj_h]
        self.assertEqual(nanjing_hosts_after_filter, expected_hosts)
        #self.assertEqual(nanjing_hosts_after_filter, nanjing_hosts)

    def test_filter_not_safe_for_deploy_agent(self):
        """ test_filter_threshold """
        bj_h = "10.44.132.25"
        bj_h2 = '10.57.66.74'
        nj_h = "10.144.129.20"
        beijing_hosts = [{"host": bj_h, "reason": "alive.host"},
                        {"host": bj_h2, "reason": "dead.host"},
                ] 
        nanjing_hosts = [{"host": nj_h, "reason": "dead.host"}]
        new_job_params =  {
                "hosts": { 
                    "hangzhou": beijing_hosts,  # give wrong clsuter, security_strategy should remove these hosts
                    "nanjing": nanjing_hosts    # give hosts has running instances, security_strategy should remove these hosts
                    },  
                "task_type": TaskTypes.reinstall_beehive_host,
                } 

        #time.sleep(1) # TODO to delete
        job_info = self.generate_test_job(new_job_params)
        security_strategy = SecurityStrategy(job_info, "filter_not_safe_for_deploy_agent")
        hosts_info = security_strategy.filter_targets()
        beijing_hosts_after_filter = [host_info.host for host_info in hosts_info['hangzhou']]
        expected_hosts = []
        self.assertEqual(beijing_hosts_after_filter, expected_hosts)
        #self.assertEqual(beijing_hosts_after_filter, beijing_hosts)
        nanjing_hosts_after_filter = [host_info.host for host_info in hosts_info['nanjing']]
        expected_hosts = []
        self.assertEqual(nanjing_hosts_after_filter, expected_hosts)
        #self.assertEqual(nanjing_hosts_after_filter, nanjing_hosts)

    def test_filter_by_date(self):
        """ test_filter_by_date """
        today_cluster_should_not_filter_by_date =  'nanjing'
        today_cluster_should_filter_by_date =  'beijing'
        today_should_not_filter_host = "10.194.74.49"
        today_should_filter_host = "10.44.166.53"
        should_filter_hosts = [{"host": today_should_filter_host, "reason": "ssh.fail"}] 
        should_not_filter_hosts = [{"host": today_should_not_filter_host, "reason": "ssh.fail"}]
        new_job_params =  {
                "hosts": { 
                    today_cluster_should_filter_by_date: should_filter_hosts, 
                    today_cluster_should_not_filter_by_date: should_not_filter_hosts
                    },  
                "task_type": TaskTypes.deploy_beehive_agent,
                } 

        job_info = self.generate_test_job(new_job_params)
        security_strategy = SecurityStrategy(job_info, "filter_by_date")
        hosts_info = security_strategy.filter_targets()

        beijing_hosts_after_filter = [host_info.host 
                for host_info in hosts_info[today_cluster_should_not_filter_by_date]]
        self.assertEqual(beijing_hosts_after_filter, [today_should_not_filter_host])
        nanjing_hosts_after_filter = [host_info.host 
                for host_info in hosts_info[today_cluster_should_filter_by_date]] 
        self.assertEqual(nanjing_hosts_after_filter, [])


