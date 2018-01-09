# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: stat_host_online_rate.py
Date: 2017/06/20
"""


import os
import sys
import django  
import requests
import json

from django.shortcuts import render_to_response

reload(sys)
sys.setdefaultencoding('utf-8')

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, '%s/../../' % CUR_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fuxi.settings")
django.setup()


from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.models import FuxiActionRuntime

from zhongjing.stat.sli import SliStat
from zhongjing.lib import  util
from zhongjing import views
from zhongjing.models import JsonData
from zhongjing.views import get_data_from_dashboard 
from zhongjing.views import get_service_rate_data_from_dashboard
from zhongjing.views import WWW_FRONT_END_HOST_TAGS 
from zhongjing.views import WWW_BACK_END_HOST_TAGS
from zhongjing.views import WWW_FRONT_END_SERVICE_TAGS
from zhongjing.views import WWW_BACK_END_SERVICE_TAGS
from zhongjing.views import WWW_PE_HOST_TAGS
from zhongjing.views import WWW_PE_SEVICE_TAGS

from zhongjing.monitor import FAIL_TASK_KEY

def stat_sli_saas():

    context = views.__dashboard_data(['wwwaladdin'])
    data = views.fmt_online_rate_data(context)
    context = {"success": True, "message": "", "data": data }
    data, created = JsonData.objects.get_or_create(key='www_aladin_host_online_rate')
    data.json_data = context
    data.save()

    context = get_data_from_dashboard(WWW_FRONT_END_HOST_TAGS)
    data, created = JsonData.objects.get_or_create(key='www_frontend_host_online_rate')
    data.json_data = context
    data.save()

    context = get_data_from_dashboard(WWW_FRONT_END_HOST_TAGS)
    data, created = JsonData.objects.get_or_create(key='www_frontend_host_online_rate')
    data.json_data = context
    data.save()

    context = get_data_from_dashboard(WWW_BACK_END_HOST_TAGS)
    data, created = JsonData.objects.get_or_create(key='www_backend_host_online_rate')
    data.json_data = context
    data.save()

    context = get_service_rate_data_from_dashboard(WWW_FRONT_END_SERVICE_TAGS)
    data, created = JsonData.objects.get_or_create(key='www_frontend_service_online_rate')
    data.json_data = context
    data.save()

    context = get_service_rate_data_from_dashboard(WWW_BACK_END_SERVICE_TAGS)
    data, created = JsonData.objects.get_or_create(key='www_backend_service_online_rate')
    data.json_data = context
    data.save()

    context = get_data_from_dashboard(WWW_PE_HOST_TAGS)
    data, created = JsonData.objects.get_or_create(key='www_pe_host_online_rate')
    data.json_data = context
    data.save()

    context = get_service_rate_data_from_dashboard(WWW_PE_SEVICE_TAGS)
    data, created = JsonData.objects.get_or_create(key='www_pe_service_online_rate')
    data.json_data = context
    data.save()


def stat_sli():
    """ 统计 服务关键指标 """

    stat_host_online_rate()
    stat_service_alive_rate()

    context = views.__dashboard_data(views.HOST_TAGS)
    r = render_to_response('zhongjing/dashboard.html', context)
    html_dict = {'dashboard_html': r.content}
    data, created = JsonData.objects.get_or_create(key='dashboard_data')
    data.json_data = html_dict
    data.save()
    print 'save html  data done'

    data, created = JsonData.objects.get_or_create(key='host_online_rate_data')
    data.json_data = views.fmt_online_rate_data(context)
    data.save()

    data, created = JsonData.objects.get_or_create(key='service_alive_rate_data')
    data.json_data = views.fmt_service_alive_rate(context)
    data.save()
    print 'save json data done'




def stat_host_online_rate():
    """ 统计个模块机器online率 """
    tags = views.BEEHIVE_HOST_TAGS
    for t in tags:
        SliStat().stat_host_online_rate(t)


def stat_service_alive_rate():
    """ 服务存活率 """
    tags = views.BEEHIVE_SERVICE_TAGS
    for t in tags:
        SliStat().stat_service_alive_rate_by_selector(t)


def dead_hosts_auto_repair():
    """ dead_hosts_auto_repair """
    api = '%s/trigger/dead_hosts_auto_repair/' % views.ZHONGJING_API_SERVER
    my_cred = util.get_baas_cred()
    _headers = {'cred': my_cred}
    msg = requests.get(api, headers=_headers).text


def auto_freeze_beehive_hosts():
    """ auto_freeze_beehive_hosts """
    api = '%s/trigger/auto_freeze_beehive_hosts/' % views.ZHONGJING_API_SERVER
    my_cred = util.get_baas_cred()
    _headers = {'cred': my_cred}
    msg = requests.get(api, headers=_headers).text


def set_longtail_tasks_timeout():
    """ auto_freeze_beehive_hosts """
    api = '%s/trigger/set_longtail_tasks_timeout/' % views.ZHONGJING_API_SERVER
    my_cred = util.get_baas_cred()
    _headers = {'cred': my_cred}
    msg = requests.get(api, headers=_headers).text


def monitor_fail_tasks():
    """ monitor_fail_tasks """
    fail_tasks, _ =JsonData.objects.get_or_create(key=FAIL_TASK_KEY)
    print "fail_tasks_num:%s" % len(fail_tasks.json_data)
    

def check_fake_dead_hosts():
    """ check_fake_dead_hosts """
    api = '%s/trigger/check_fake_dead_hosts/' % views.ZHONGJING_SERVER
    my_cred = util.get_baas_cred()
    _headers = {'cred': my_cred}
    for c in ["hna", "hnb", "hangzhou", "beijing", "nanjing", "tucheng", "shanghai"]:
        _params = {"app": "wwwbs", "cluster": c}
        #_api = "%s?cluster=%s&app=wwwbs" % (api, c)
        msg = requests.get(api, headers=_headers, params = _params).text
        #print api, _params, msg 


def call(task):
    cur_module = sys.modules[__name__]
    if hasattr(cur_module, task):
        method = getattr(cur_module, task)
        method()
    else:
        print "task=[%s] not supported." % task
 
   

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print """
python tasks.py [method_name]
        """
    else:
        task = sys.argv[1]
        call(task)

