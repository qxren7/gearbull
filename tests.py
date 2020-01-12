#!/usr/bin/env python
import os
import sys
import json
import time
import random
import logging
import requests
import datetime
import traceback
import subprocess


CUR_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT_DIR = "%s/../" % CUR_DIR
LOG_DIR = "%s/%s" % (PROJECT_ROOT_DIR, "logs")
CONF_DIR = "%s/%s" % (CUR_DIR, "conf")
sys.path.append("%s/../" % CUR_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gearbull.settings")

import django

django.setup()

from WorkFlow.models import Job
from WorkFlow.models import Task
from WorkFlow.models import Action

from rest_framework.renderers import JSONRenderer

import unittest


def create_job_work_flow(
    hosts,
    task_type,
    job_name='',
    job_desc='',
    concurrency=1,
    threshold=100,
    fail_rate=10,
    timeout=432000,  
    fail_detail=None,
    extra_params={},
    confirms={},
    is_idempotency=False,
    username='default'):

    if len(hosts) <= 0:
        print("empty list, return")
        return (False, -1)

    job_info = {}
    job_info['job_type'] = 'ansible_job'
    job_info['priority'] = '0'
    job_info['threshold'] = '100'  # succ threshold
    job_info['timeout'] = timeout
    job_info['user'] = 'u1'
    job_info['state'] = 'NEW'
    job_info['fail_rate'] = fail_rate
    job_info['concurrency'] = concurrency
    job_info['task_type'] = task_type
    job_info['job_desc'] = job_desc
    job_info['confirms'] = confirms
    job_info['is_idempotency'] = is_idempotency
    job_info['continue_after_stage_finish'] = True

    executors = ['WorkFlowExecutor', 'BashExecutor']
    #job_info['executor'] = executors[random.randint(0,1)]
    job_info['executor'] = 'WorkFlowExecutor'

    modes = ['batch_mode', 'roll_mode']
    mode = modes[random.randint(0, 1)]
    mode = 'roll_mode'
    entities = {1: hosts}
    params = {
        'entities': entities,
        'service_name': task_type,
        'execute_mode': mode,
        'job_name': job_name,
        'job_desc': job_desc,
        'launcher_user': username,
        'fail_detail': fail_detail,
    }
    params.update(extra_params)
    job_info['params'] = params

    api = 'http://localhost:8088/workflow/api/create_job/'

    _data = {'job_info': json.dumps(job_info)}
    r = requests.post(api, data=_data)
    msg = "%s, %s, %s, %s" % (api, _data, json.dumps(job_info), r.text)
    try:
        res = r.json()
        return res
    except Exception as e:
        print(e)
        print(traceback.format_exc())
    return (False, -1)


def setup_test():
    #TODO  for test only
    Job.objects.all().delete()


def tear_down():
    pass


def create_job(task_type, to_deploy_hosts=['h1'], concurrency=100, timeout=360):
    res = create_job_work_flow(to_deploy_hosts,
                               task_type,
                               timeout=timeout,
                               concurrency=concurrency)
    job_id = res['job_id']
    j = Job.objects.get(id=job_id)
    return j


def refresh(job):
    j = Job.objects.get(id=job.id)
    return j


def get_actions(job):
    actions = []
    for t in job.task_set.all():
        for a in t.action_set.all():
            actions.append(a)
    return actions


class TestWorkFlow(unittest.TestCase):
    def test_create_job(self):
        setup_test()

        jobs = Job.objects.all()
        current_count = jobs.count()
        j = create_job('test_clause')

        self.assertEqual(Job.objects.count(), current_count + 1)
        print("test_create_job, jobs count is ok.")

    def test_scheduler_and_monitor(self):
        setup_test()
        j = create_job('test_clause')
        self.assertEqual(j.state, 'NEW')
        print("test_scheduler_and_monitor, jobs is NEW after created, ok")
        time.sleep(10)

        j = refresh(j)
        self.assertEqual(j.state, 'RUNNING')
        print("test_scheduler_and_monitor, jobs is RUNNING, after scheduled, ok")
        for t in j.task_set.all():
            self.assertEqual(t.state, 'RUNNING')
            print("test_scheduler_and_monitor, task=[%s] is RUNNING, after scheduled, ok" % t.id)

        time.sleep(100)

        j = refresh(j)
        self.assertEqual(j.state, 'SUCCESS')
        print( "test_succ_job, jobs is SUCCESS, after finish all tasks and action, ok")
        for t in j.task_set.all():
            self.assertEqual(t.state, 'SUCCESS')
            print( "test_scheduler_and_monitor, task=[%s] is SUCCESS, after scheduled, ok" % t.id)

    def test_succ_job(self):
        setup_test()
        j = create_job('test_clause')
        self.assertEqual(j.state, 'NEW')
        print("test_succ_job, jobs is NEW after created, ok")
        time.sleep(10)

        j = refresh(j)
        self.assertEqual(j.state, 'RUNNING')
        print("test_succ_job, jobs is RUNNING, after scheduled, ok")
        time.sleep(100)

        j = refresh(j)
        self.assertEqual(j.state, 'SUCCESS')
        print(
            "test_succ_job, jobs is SUCCESS, after finish all tasks and action, ok"
        )

    def test_timeout_job(self):
        setup_test()
        j = create_job('longrun_task', timeout=1)
        self.assertEqual(j.state, 'NEW')
        print("test_timeout_job, jobs is NEW after created, ok")
        time.sleep(60)

        j = refresh(j)
        self.assertEqual(j.state, 'TIMEOUT')
        print("test_timeout_job, jobs is TIMEOUT, since timeout is 3s, ok")
        for t in j.task_set.all():
            self.assertEqual(t.state, 'TIMEOUT')
            print("test_timeout_job, task=[%s] is TIMEOUT, since job is TIMEOUT, ok" % t.id)


    def test_fail_job(self):
        setup_test()
        j = create_job('test_fail')
        self.assertEqual(j.state, 'NEW')
        print("test_fail_job, jobs is NEW after created, ok")
        time.sleep(80)

        j = refresh(j)
        self.assertEqual(j.state, 'FAILED')
        print(
            "test_fail_job, jobs is FAILED, after execute  action, return failed result, ok"
        )

    def test_task_execute_clause_1(self):
        setup_test()
        j = create_job('test_clause_1_trees')
        self.assertEqual(j.state, 'NEW')
        print("test_task_execute_clause, jobs is NEW after created, ok")
        time.sleep(100)

        j = refresh(j)
        self.assertEqual(j.state, 'SUCCESS')
        print("test_clause_1_trees, jobs is SUCCESS, ok")

        actions = []
        for t in j.task_set.all():
            for a in t.action_set.all():
                actions.append(a)
        states = [a.state for a in actions]
        states = list(set(states))
        self.assertEqual(len(states), 2)
        print("test_clause_1_trees, all action state is SUCCESS or NEW, ok")

    def test_task_execute_clause_2(self):
        setup_test()
        j = create_job('test_clause_2_trees')
        self.assertEqual(j.state, 'NEW')
        print("test_task_execute_clause, jobs is NEW after created, ok")
        time.sleep(100)

        j = refresh(j)
        self.assertEqual(j.state, 'SUCCESS')
        print("test_clause_2_trees, jobs is SUCCESS, ok")

        failed_action = Action.objects.get(method_name="a5")
        self.assertEqual(failed_action.state, 'FAILED')
        print("test_clause_2_trees, the 'a5' method is fail, ok")

        actions = get_actions(j)
        states = [a.state for a in actions]
        states = list(set(states))
        self.assertEqual(len(states), 3)
        self.assertEqual("SUCCESS" in states, True)
        self.assertEqual("FAILED" in states, True)
        print(
            "test_clause_2_trees, job is SUCCESS, all actions state is SUCCESS or NEW or FAILED , ok"
        )

    def test_job_pause_resume(self):
        setup_test()
        j = create_job('test_fail')
        self.assertEqual(j.state, 'NEW')
        print("test_job_pause_resume, jobs is NEW after created, ok")

        j.pause()
        j = refresh(j)
        self.assertEqual(j.state, 'PAUSED')
        print("test_job_pause_resume, jobs is PAUSED after pause(), ok")

        time.sleep(15)
        j = refresh(j)
        self.assertEqual(j.state, 'PAUSED')
        print(
            "test_job_pause_resume, jobs is still  PAUSED after sleep 15s, ok")

        j.resume()
        time.sleep(70)
        j = refresh(j)
        self.assertEqual(j.state, 'SUCCESS')
        print("test_job_pause_resume, jobs is SUCCESS after resume(), ok")

    def test_job_cancel(self):
        setup_test()
        j = create_job('test_fail')
        self.assertEqual(j.state, 'NEW')
        print("test_job_cancel, jobs is NEW after created, ok")

        j.cancel()
        j = refresh(j)
        self.assertEqual(j.state, 'CANCELLED')
        print("test_job_cancel, jobs is CANCELLED after cancel(), ok")

        time.sleep(15)
        j = refresh(j)
        self.assertEqual(j.state, 'CANCELLED')
        print(
            "test_job_cancel, jobs is still  PAUSED after sleep 15s, ok")

    def test_task_skip(self):
        setup_test()
        j = create_job('test_fail')
        self.assertEqual(j.state, 'NEW')
        print("test_task_skip, jobs is NEW after created, ok")

        time.sleep(10)
        j = refresh(j)
        for t in j.task_set.all():
            t.skip()
            self.assertEqual(t.state, 'SKIPPED')
            print("test_task_skip, task=[%s] is SKIPPED , after skip(), ok" % t.id) 


    def test_task_execute_and_or_logic(self):
        setup_test()
        j = create_job('test_clause')
        self.assertEqual(j.state, 'NEW')
        print("test_task_execute_and_or_logic, jobs is NEW after created, ok")

        time.sleep(90)

        j = refresh(j)
        actions = get_actions(j)
        results = [a.result for a in actions]
        results_str = " ".join(results)
        self.assertEqual('a2' in results_str, True)
        self.assertEqual('b1' in results_str, True)
        self.assertEqual('b2' in results_str, True)
        self.assertEqual('a3' in results_str, True)
        self.assertEqual('b2' in results_str, True)
        self.assertEqual('b3' in results_str, True)
        self.assertEqual('b4' in results_str, True)
        print(
            "test_task_execute_and_or_logic, action a2 b1 b2 a3 b2 b3 b4 is executed, ok"
        )
        self.assertEqual(j.state, 'SUCCESS')
        print("test_task_execute_and_or_logic, jobs is SUCCESS, ok")

    def test_action_save_result(self):
        setup_test()
        j = create_job('test_clause')
        self.assertEqual(j.state, 'NEW')
        print("test_action_save_result, jobs is NEW after created, ok")

        time.sleep(90)

        j = refresh(j)
        actions = get_actions(j)
        results = [a.result for a in actions]
        results_str = " ".join(results)
        self.assertEqual('a2' in results_str, True)
        self.assertEqual('b1' in results_str, True)
        self.assertEqual('b2' in results_str, True)
        self.assertEqual('a3' in results_str, True)
        self.assertEqual('b2' in results_str, True)
        self.assertEqual('b3' in results_str, True)
        self.assertEqual('b4' in results_str, True)
        print(
            "test_action_save_result, action a2 b1 b2 a3 b2 b3 b4 has action result, ok"
        )
        self.assertEqual(j.state, 'SUCCESS')
        print("test_action_save_result, jobs is SUCCESS, ok")

    def test_job_task_action_for_flow(self):
        setup_test()
        j = create_job('example_task')
        self.assertEqual(j.state, 'NEW')
        print("test_job_task_action_for_flow, jobs is NEW after created, ok")
        time.sleep(10)

        j = refresh(j)
        self.assertEqual(j.state, 'RUNNING')
        print("test_job_task_action_for_flow, jobs is RUNNING, after scheduled, ok")

        tasks_count = j.task_set.count()
        self.assertEqual(tasks_count, 1)
        print("test_job_task_action_for_flow, task count is match, ok")
        for t in j.task_set.all():
            actions_count = t.action_set.count()
            self.assertEqual(actions_count, 3)
            print("test_job_task_action_for_flow, action count is match, ok")
      
    def test_concurrency(self):
        setup_test()
        to_deploy_hosts= ["h_%s" % i for i in range(1,2)]
        j = create_job('test_clause', to_deploy_hosts=to_deploy_hosts, concurrency=len(to_deploy_hosts))
        self.assertEqual(j.state, 'NEW')
        print("test_concurrency, jobs is NEW after created, ok")
        time.sleep(10)

        j = refresh(j)
        self.assertEqual(j.state, 'RUNNING')
        print("test_concurrency, jobs is RUNNING, after scheduled, ok")
        
        self.assertEqual(j.task_set.count(), len(to_deploy_hosts))
        print("test_concurrency, task_set count is equals to to_deploy_hosts' len, ok")
    
        for t in j.task_set.all():
            self.assertEqual(t.state, 'RUNNING')
            print("test_concurrency, task=[%s] is RUNNING, ok" % t.id)

        time.sleep(60)

        j = refresh(j)
        self.assertEqual(j.state, 'SUCCESS')
        print( "test_concurrency, jobs is SUCCESS, after finish all tasks and action, ok")
        for t in j.task_set.all():
            self.assertEqual(t.state, 'SUCCESS')
            print( "test_concurrency, task=[%s] is SUCCESS, after scheduled, ok" % t.id)

    def test_continue_after_stage_finish(self):
        setup_test()
        to_deploy_hosts= ["h_%s" % i for i in range(1,2)]
        j = create_job('test_clause', to_deploy_hosts=to_deploy_hosts, concurrency=len(to_deploy_hosts))
        self.assertEqual(j.state, 'NEW')
        print("test_continue_after_stage_finish, jobs is NEW after created, ok")
        time.sleep(10)

        j = refresh(j)
        self.assertEqual(j.state, 'RUNNING')
        print("test_continue_after_stage_finish, jobs is RUNNING, after scheduled, ok")
        
        self.assertEqual(j.task_set.count(), len(to_deploy_hosts))
        print("test_continue_after_stage_finish, task_set count is equals to to_deploy_hosts' len, ok")
    
        for t in j.task_set.all():
            self.assertEqual(t.state, 'RUNNING')
            print("test_continue_after_stage_finish, task=[%s] is RUNNING, ok" % t.id)

        time.sleep(60)

        j = refresh(j)
        self.assertEqual(j.state, 'SUCCESS')
        print( "test_continue_after_stage_finish, jobs is SUCCESS, after finish all tasks and action, ok")
        for t in j.task_set.all():
            self.assertEqual(t.state, 'SUCCESS')
            print( "test_continue_after_stage_finish, task=[%s] is SUCCESS, after scheduled, ok" % t.id)

    def test_real_do_work_action(self):
        setup_test()
        j = create_job('real_do_work_action')
        self.assertEqual(j.state, 'NEW')
        print("test_real_do_work_action, jobs is NEW after created, ok")
        time.sleep(10)

        j = refresh(j)
        self.assertEqual(j.state, 'RUNNING')
        print("test_real_do_work_action, jobs is RUNNING, after scheduled, ok")

        time.sleep(10)
        check_work_cmd = 'cat /tmp/test_real_do_work_action.log'
        (status, outout) = subprocess.getstatusoutput(check_work_cmd)
        self.assertEqual('test' in outout, True)

        time.sleep(100)

        j = refresh(j)
        self.assertEqual(j.state, 'SUCCESS')
        print(
            "test_real_do_work_action, jobs is SUCCESS, after finish all tasks and action, ok"
        )



def test():
    setup_test()

    twf = TestWorkFlow()

    twf.test_job_task_action_for_flow()
    twf.test_create_job()
    twf.test_succ_job()
    twf.test_fail_job()
    twf.test_task_execute_clause_1()
    twf.test_task_execute_clause_2()
    twf.test_task_execute_and_or_logic()
    twf.test_action_save_result()
    twf.test_scheduler_and_monitor()
    twf.test_job_pause_resume()
    twf.test_job_cancel()
    twf.test_timeout_job()
    twf.test_concurrency()
    twf.test_continue_after_stage_finish()
    twf.test_real_do_work_action()

    #twf.test_task_skip()

    tear_down()


if __name__ == "__main__":
    test()
