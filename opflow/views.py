#!encoding=utf-8
########################################################################
# 
# 
########################################################################
 
"""
File: views.py
Date: 2017/04/12 
"""

import os
import sys
import json
import time
import logging
import traceback
import requests
import itertools
import pprint
from time import mktime
from datetime import datetime
from datetime import timedelta
from collections import defaultdict

from django.utils import timezone
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.core import serializers
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from django.shortcuts import render_to_response
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.db.models import Q


from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.models import FuxiActionRuntime

from fuxi_framework.common_lib import beehive_wrapper
from fuxi_framework.common_lib import config_parser_wrapper
from fuxi_framework.job_engine import id_generator
from fuxi_framework.job_engine import runtime_manager
from fuxi_framework.common_lib import log
from fuxi_framework.job_engine.runtime_manager import JobStatus

from zhongjing.lib.thread_task import ThreadTask
from zhongjing.models import JobInfo
from zhongjing.models import TaskInfo
from zhongjing.models import Sli
from zhongjing.actions import TaskTypes
from zhongjing.actions import TASK_TYPES_ZH
from zhongjing.host import Ultron
from zhongjing.security_strategy import  SECURITY_CHECK_STATES
from zhongjing.lib import  util
from zhongjing.host import Ultron
from zhongjing.stat.sli import SliStat
from zhongjing.models import JsonData
from zhongjing.host import CheckHostDeadTask
from zhongjing.host import CheckHostFakeDeadTask
from zhongjing.cal_alive_ration import cal_bs_alive_ration
from zhongjing.cal_alive_ration import constancy_master
from zhongjing.models import FailLog
from .forms import HostOperateForm

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
conf = config_parser_wrapper.ConfigParserWrapper("%s/conf/zhongjing.conf" % CUR_DIR)

log.init_log("%s/log/view" % CUR_DIR)
logger = logging.getLogger("view")


ZHONGJING_SERVER = '%s/zhongjing' % SERVER_HOST
ZHONGJING_API_SERVER = '%s/api/zhongjing' % SERVER_HOST

ZHONGJING_USERS_KEY = 'zhongjing_users_dict'

CLUSTER_ORDER = {
        "beijing": 0,
        "tucheng": 1,
        "hna": 2,
        "hnb": 3,
        "nanjing": 4,
        "hangzhou": 5,
        "shanghai": 6,
        "yangquan": 7,
        }

ORDER_CLUSTERS = [
        "beijing",
        "tucheng",
        "hna",
        "hnb",
        "nanjing",
        "hangzhou",
        "shanghai",
        "yangquan",
        ]


class CalcJobTask(ThreadTask):
    """ CalcJobTask """
    def task(self, _job_id):
        job_detail = {}
        tasks = FuxiTaskRuntime.objects.filter(job_id = _job_id)
        all_tasks_count = tasks.count()
        succ_tasks_count = tasks.filter(state="SUCCESS").count()
        job_detail['color'] =  'red'
        if succ_tasks_count > 0:
            succ_rate = "%d" % (1.0 * succ_tasks_count / all_tasks_count * 100) + '%'
            if (succ_tasks_count / all_tasks_count == 1): job_detail['color'] =  'green'
        else:
            succ_rate = '0%'
        
        job_detail['tasks_count'] = "%s/%s" % (succ_tasks_count, all_tasks_count) 
        self._result_queue.put((_job_id, job_detail))

    def collect(self):
        """ collect """
        results = {}
        while not self._result_queue.empty():  
            job_id, job_detail = self._result_queue.get()
            results[job_id] = job_detail
        return results



def simple_auth(f):
    """ 简易权限验证方法 """
    def wrap(request, *args, **kwargs):
        """ 固定写法 """
        _request_params = json.loads(request.body)
        _user = _request_params['user']
        ZHONGJING_USERS, created = JsonData.objects.get_or_create(key=ZHONGJING_USERS_KEY)
        users = ZHONGJING_USERS.json_data
        print users
        if _user not in users:
            msg = {
                    "data": {
                        }, 
                    "message": "Authentication Failed, user=[%s]" % (_user),  
                    "success": False
                    }
            return HttpResponse(json.dumps(msg)) 
        return f(request, *args, **kwargs)
    wrap.__doc__=f.__doc__
    wrap.__name__=f.__name__
    return wrap


def trigger_tasks(request, task):
    """ 触发式任务入口 """
    cur_module = sys.modules[__name__]
    if hasattr(cur_module, task):
        method = getattr(cur_module, task)
        return method(request)
    else:
        msg = {
            "code": -1,
            "message": "task=[%s] not supported." % task,
            "url": ""
        }
        return HttpResponse(json.dumps(msg)) 

def get_tasks(request):
    """ get_tasks """
    app = request.GET['app'] if 'app' in request.GET else 'all'
    if app == 'all':
        _apps = []
    else:
        _apps = [app]

    cache_key = ','.join(_apps)
    if cache.has_key(cache_key):
        msg = cache.get(cache_key)
    else:

        details = get_tasks_by_states(runtime_manager.STATES, 
                runtime_manager.STATES, elapsed_days=14, apps = _apps)
        msg = {"data": details, "message": "ok", "success":True}
        cache.set(cache_key, msg, 60 * 60)
    return HttpResponse(json.dumps(msg))

def host_freeze_log(request):
    """ host_freeze_log """
    host = request.GET['host'] 
    logs = FailLog.objects.filter(entity = host)[::-1]
    models_json = serializers.serialize("json", logs)
    return HttpResponse(models_json)


def get_fail(request):
    """ get_fail"""
    if 'host' not in request.GET: 
        msg = {"data": '', "message": "need 'host' params", "success":False}
        return HttpResponse(json.dumps(msg))

    host = request.GET['host'] 
    u=Ultron()
    data = u.get_fail(host)
    msg = {"data": data, "message": "ok", "success":True}
    return HttpResponse(json.dumps(msg))


def tasks_list(request):
    """ get_tasks by job_id"""
    if 'jobid' not in request.GET: 
        msg = {"data": '', "message": "no job_id in request", "success":False}
        return HttpResponse(json.dumps(msg))

    _job_id = request.GET['jobid'] 

    q = Q(job_id=_job_id)
    if 'state' in request.GET:
        _state = request.GET['state']
        state_q = Q(state=_state)
        q = q & state_q
    
    task_details = []
    for t in FuxiTaskRuntime.objects.filter(q):
        task_detail = _get_task_detail(t)
        if task_detail: task_details.append(task_detail)
    msg = {"data": task_details, "message": "ok", "success":True}
    return HttpResponse(json.dumps(msg))


def fake_dead_hosts(request):
    """ fake_dead_hosts """
    if 'cluster' not in request.GET or 'app' not in request.GET: 
        msg = {"data": '', "message": "need cluster and app in request", "success":False}
        return HttpResponse(json.dumps(msg))

    cluster = request.GET['cluster'] 
    app = request.GET['app']

    fake_dead_hosts_key = "zhongjing_fake_dead_hosts_%s_%s" % (app, cluster)
    data, created = JsonData.objects.get_or_create(key=fake_dead_hosts_key)
    if len(data.json_data.keys()) <= 0:
        message = "no data for app: %s, cluster: %s" % (app, cluster)
        msg = {"data": '', "message": message, "success":False}
        return HttpResponse(json.dumps(msg))

    if 'detail' in request.GET:
        return HttpResponse(json.dumps(data.json_data))
    else:
        return HttpResponse(json.dumps(data.json_data["fake_dead_hosts"]))


def galaxy_tasks_list(request):
    """ get_tasks by job_id"""
    if 'jobid' not in request.GET: 
        msg = {"data": '', "message": "no job_id in request", "success":False}
        return HttpResponse(json.dumps(msg))

    _job_id = request.GET['jobid'] 
    task_details = []
    for t in FuxiTaskRuntime.objects.filter(job_id=_job_id):
        task = {"task_id": t.task_id, "state": t.state}
        task_details.append(task)
    msg = {"data": task_details, "message": "ok", "success":True}
    return HttpResponse(json.dumps(msg))


def host_state(request):
    """ host_state """
    u = Ultron()
    host = request.GET['host'] 
    msg = u.host_state(host)
    return HttpResponse(json.dumps(msg))


def get_tasks_by_states(job_states, task_states, apps=[], elapsed_days=14):
    """ get_tasks_by_states """

    task_details = []
    for j in FuxiJobRuntime.objects.filter(job_type='zhongjing', state__in = job_states, 
            create_time__gte=datetime.now()-timedelta(days=elapsed_days)).order_by('-create_time'):
        for t in FuxiTaskRuntime.objects.filter(job_id=j.job_id, state__in = task_states):
            task_detail = _get_task_detail(t, apps)
            if task_detail: task_details.append(task_detail)
    return task_details
 
 
def galaxy_fails(request):
    """ galaxy_fails """
    u=Ultron()
    fails = u.get_galaxy_fails()
    msg = {"data": fails, "message": "ok", "success":True}
    return HttpResponse(json.dumps(msg)) 

def dead_hosts_auto_repair(request):
    """ 死机自动维修 """
    fail_type = 'ssh.lost'
    auto_repair_pools = conf.get_option_value("auto_repair", "auto_repair_pools").split(",")


def auto_freeze_beehive_hosts(request):
    """
    freeze_beehive_host 接口，获取Beeehive Dashboard 决策出的需要freeze 的机器，执行freeze
    """
    hosts = beehive_wrapper.to_freeze_hosts()
    params = {
        "user": "",
        "token": "",
    }
    params.update(hosts)
    api = '%s/freeze_beehive_host/' % ZHONGJING_API_SERVER
    my_cred = util.get_baas_cred()
    _headers = {'cred': my_cred}
    msg = requests.post(api, data=json.dumps(params), headers=_headers).text
    return HttpResponse(msg) 


def task_detail(request):
    """ task_detail """
    _task_id = request.GET['taskid'] 
    details = []
    task = FuxiTaskRuntime.objects.get(task_id = _task_id)
    task_detail = _get_task_detail(task)
    if task_detail: details.append(task_detail)
    msg = {"data": details, "message": "ok", "success":True}
    return HttpResponse(json.dumps(msg)) 


@simple_auth
def freeze_host(request):
    _request_params = json.loads(request.body)
    fails = []
    for cluster, hosts in _request_params['hosts'].items():
        for host_item in hosts:
            host = host_item['host']
            if not beehive_wrapper.freeze_host(cluster, host):
                fails.append(host)
    msg = {"data": {"fails": fails}, "message": "", "success":True}
    return HttpResponse(json.dumps(msg))
    

@simple_auth
def unfreeze_host(request):
    _request_params = json.loads(request.body)
    fails = []
    for cluster, hosts in _request_params['hosts'].items():
        for host_item in hosts:
            host = host_item['host']
            if not beehive_wrapper.unfreeze_host(cluster, host):
                fails.append(host)
    msg = {"data": {"fails": fails}, "message": "", "success":True}
    return HttpResponse(json.dumps(msg))
 

def operates(request):
    _infos = JobInfo.objects.filter(is_manual = True)
    infos = []
    for info in _infos:
        job_params = info.job_params
        for cluster, host_info in job_params['hosts'].items():
            for host_item in host_info:
                info.user = job_params['user']
                info.task_type = job_params['task_type']
                info.job_id =  info.job.job_id
                info.state = info.job.state
                info.create_time = info.job.create_time
                info.host = host_item['host']
                infos.append(info)
        
    context = {'infos': infos}
    return render(request, 'zhongjing/operates.html', context)

def host_operate(request, task_type = None):
    """ 机器操作 """
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = HostOperateForm(request.POST)
        msg = {
            "code": 0,
            "message": "ok",
            "url": ""
        }
        # check whether it's valid:
        if form.is_valid():
            return __dispatch_request(request, form)
        else:
            msg['message'] = form.errors
            return HttpResponse(json.dumps(msg)) 

    # if a GET (or any other method) we'll create a blank form
    else:
        form = HostOperateForm()
        form.fields['task_type'].widget.attrs['placeholder'] = task_type
        form.fields['task_type'].widget.attrs['value'] = task_type

    context = {
            'form': form,
            "task_type": task_type,
            }
    return render(request, 'zhongjing/host_operate.html', context)


def index(request):
    """ index """
    return render_to_response('zhongjing/jobs.html')


def service(request, service_name):
    context = __dashboard_data(service_targets=[service_name])
    return render(request, 'zhongjing/service.html', context)
   

def dashboard(request):
    """ index """
    #context = __dashboard_data(HOST_TAGS)
    #print context

    html = JsonData.objects.get(key='dashboard_data').json_data['dashboard_html']
    return HttpResponse(html)


@simple_auth
def freeze_beehive_host(request):
    """
    freeze_beehive_host 接口，获取Beeehive Dashboard 决策出的需要freeze 的机器，执行freeze
    """
    _job_params = get_machine_job_params("freeze_beehive_host")
    _job_params['timeout'] = '300'
    result = __operate_hosts(request, TaskTypes.freeze_beehive_host, _job_params)
    return result


#@csrf_exempt
@simple_auth
def deploy_agent(request):
    """
    reinstall 接口，接受用户主动发起的维修请求
    """
    _job_params = get_machine_job_params("deploy_agent")
    _job_params['timeout'] = conf.get_option_value("ultron", 'deploy_beehive_agent_timeout')
    result = __operate_hosts(request, TaskTypes.deploy_beehive_agent, _job_params)
    return result


@simple_auth
def repair_fake_dead(request):
    """
    假死机器维修接口，接受用户主动发起的维修请求
    """
    _job_params = get_machine_job_params("repair_fake_dead")
    _job_params['timeout'] = conf.get_option_value("ultron", 'host_repair_timeout')
    result = __operate_hosts(request, TaskTypes.repair_fake_dead_beehive_host, _job_params)
    return result


@simple_auth
def mount_to_beehive_node(request):
    """
    mount_to_beehive_node 接口，将其他产品线的机器，挂载到beehive agent节点下
    """
    _job_params = get_machine_job_params("mount_to_beehive_node")
    _job_params['timeout'] = conf.get_option_value("ultron", 'mount_to_beehive_node_timeout')
    result = __operate_hosts(request, TaskTypes.mount_to_beehive_node, _job_params)
    return result


#@csrf_exempt
@simple_auth
def reinstall(request):
    """
    reinstall 接口，接受用户主动发起的维修请求
    """
    _job_params = get_machine_job_params("reinstall")
    _job_params['timeout'] = conf.get_option_value("ultron", 'host_reinstall_timeout')
    _job_params['threshold'] = "50"
    result = __operate_hosts(request, TaskTypes.reinstall_beehive_host, _job_params)
    return result


#@csrf_exempt
@simple_auth
def repair(request):
    """
    repair 接口，接受决策系统的维修请求, 只有检测出来故障的机器会被执行维修
    """
    _job_params = get_machine_job_params("repair")
    _job_params['timeout'] = conf.get_option_value("ultron", 'host_repair_timeout')
    _job_params['threshold'] = "50"
    result = __operate_hosts(request, TaskTypes.repair_beehive_host, _job_params)
    return result



@csrf_exempt
def query(request, target):
    """ query """
    method_name = "list_%s" % target
    query_method = getattr(sys.modules[__name__], method_name)
    data = query_method()
    return HttpResponse(data)


@csrf_exempt
def query_by_filter(request, target, params):
    """ query_by_filter """
    method_name = "query_%s_by_filter" % target
    query_method = getattr(sys.modules[__name__], method_name)
    data = query_method(params)
    return HttpResponse(data)


def __construct_host_operate_params(request, form):
    request_params = {}
    request_params['user'] = request.user.username
    request_params['is_manual'] = True
    request_params['hosts'] = {}
    request_params['reason'] = form.cleaned_data['reason']

    task_type = form.cleaned_data['task_type']
    cluster = form.cleaned_data['cluster']
    reason = form.cleaned_data['reason']
    hosts = form.cleaned_data['hosts'].split("\n")
    skip_threshould = form.cleaned_data['skip_threshould']
    host_items = []
    for h in hosts:
        host_items.append({"host": h, "reason": reason})
    request_params['hosts'][cluster] = host_items

    optional_params = ['product_line', 'noah_token', 'skip_threshould']
    for param_name in optional_params:
        if param_name in form.cleaned_data:
            request_params[param_name] = form.cleaned_data[param_name]

    return request_params


def __dispatch_request(request, form):

    task_type = form.cleaned_data['task_type']
    request_params = __construct_host_operate_params(request, form)
    request._body = json.dumps(request_params)
    cur_module = sys.modules[__name__]
    if hasattr(cur_module, task_type):
        method = getattr(cur_module, task_type)
        return method(request)
    else:
        msg = {
            "code": -1,
            "message": "task_type=[%s] not supported." % task_type,
            "url": ""
        }
        return HttpResponse(json.dumps(msg)) 


def __operate_hosts(request, task_type, _job_params):
    """
    repair 接口，接受用户或决策系统的维修请求
    """
    cache.clear()    
    _request_params = json.loads(request.body)
    _request_params['task_type'] = task_type

    if 'is_manual' in _request_params:
        _is_manual = _request_params['is_manual']
    else:
        _is_manual = False

    if 'concurrency_by_app' in _job_params:
        _request_params['concurrency_by_app']  = _job_params['concurrency_by_app']

    _job_params['user'] = _request_params['user']
    msg = {"data": {"redirect": ""}, "message": "ok", "success":True}
    print '_job_params', _job_params
    try:
        job_runtime = runtime_manager.create_job(_job_params)
        job_info = JobInfo(
                job=job_runtime, 
                job_params = _request_params,
                is_manual = _is_manual
                )
        job_info.save()
        msg["data"]["redirect"] = url
        msg["data"]["job_id"] = job_runtime.job_id
        msg["message"] = "Create job succ, job_id %s, \
please check jobs list page to see detail." % job_runtime.job_id
    except Exception as e:
        logger.error(traceback.format_exc())
        traceback.print_exc()
        msg['message'] = "create job fail, error=[%s]" % e
    return HttpResponse(json.dumps(msg)) 

