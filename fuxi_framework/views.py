#!encoding=utf-8
########################################################################
# 
# 
########################################################################
 
"""
File: views.py
Date: 2017/05/15 
"""

import os
import sys
import logging
import copy
import json
import traceback
from django.shortcuts import render
from django.shortcuts import render_to_response
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.db import connection
from django.apps import apps
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from fuxi_framework.common_lib import log
from fuxi_framework.common_lib import config_parser_wrapper
from fuxi_framework.models import FuxiJobRuntime
from fuxi_framework.models import FuxiTaskRuntime
from fuxi_framework.models import FuxiActionRuntime
from fuxi_framework.serializers import FuxiJobRuntimeSerializer
from fuxi_framework.serializers import FuxiTaskRuntimeSerializer
from fuxi_framework.serializers import FuxiActionRuntimeSerializer
from fuxi_framework.job_engine.job_controller import JobController
from fuxi_framework import auth as fuxi_auth

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
log.init_log("%s/log/framework_view" % CUR_DIR)
logger = logging.getLogger("framework_view")
conf = config_parser_wrapper.ConfigParserWrapper("%s/conf/api.conf" % CUR_DIR)

def index(request):
    """ 
    首页默认展示job列表

    :param request: http请求对象
    :return: 结果页面
    """
    return render(request, 'fuxi_framework/jobs.html')


def show_jobs(request):
    """
    job列表页

    :param request: http请求对象
    :return: 结果页面
    """
    return render(request, 'fuxi_framework/jobs.html')


def show_tasks(request):
    """
    task列表页

    :param request: http请求对象
    :return: 结果页面
    """
    job_id = ""
    if "job_id" in request.GET:
        job_id = request.GET['job_id']
    return render_to_response('fuxi_framework/tasks.html', {"job_id":job_id})


def show_actions(request):
    """
    action列表页

    :param request: http请求对象
    :return: 结果页面
    """
    job_id = ""
    if "task_id" in request.GET:
        task_id = request.GET['task_id']
    return render_to_response('fuxi_framework/actions.html', {"task_id":task_id})


def get_username(request):
    """
    auth接口
    """
    try:
        username = fuxi_auth.get_username(request)
        logger.info("get auth" + username)
        if "format" in request.GET and request.GET['format'] == "json":
            ret = {"data":{"username":str(username)}, "message":"ok", "success":True}
            return HttpResponse(json.dumps(ret), content_type="text/plain")
        return HttpResponse(str(username), content_type="text/plain")
    except Exception as e:
        username = "AnonymousUser"
        if "format" in request.GET and request.GET['format'] == "json":
            ret = {"data":{"redirect":"/accounts/login/"}, "message":"ok", "success":False}
            return HttpResponse(json.dumps(ret), content_type="text/plain")
        return HttpResponse(str(username), content_type="text/plain")


@api_view(['GET'])
def jobs(request, job_id=""):
    """
    查询job信息

    :param job_id: 可选参数，默认返回所有的job
    :return:
    """
    if request.method != "GET":
        logger.info("query jobs method error, method=[%s]" % request.method)
        return HttpResponseBadRequest(content='{"data":[],msg:"invalid request method"}')

    default_size = conf.get_option_value("query", "default_size")
    max_size = conf.get_option_value("query", "max_size")
    params = copy.deepcopy(request.GET)
    if "size" not in params:
        params['size'] = default_size
    elif params['size'] > max_size:
        params['size'] = max_size
    logger.info("query jobs, params=[%s]" % params)

    if job_id != "":
        fuxi_jobs = FuxiJobRuntime.objects.filter(job_id=job_id)
    else:
        fuxi_jobs = FuxiJobRuntime.objects.all().order_by('-id')[:params['size']]
    connection.close()
    serializer = FuxiJobRuntimeSerializer(fuxi_jobs, many=True)
    logger.info(fuxi_jobs)
    ret_data = {"data":serializer.data}
    return Response(ret_data)


@api_view(['GET'])
def tasks(request, task_id=""):
    """
    查询task信息

    :param task_id: 可选参数，默认返回所有的task
    :return:
    """
    if request.method != "GET":
        logger.info("query tasks method error, method=[%s]" % request.method)
        return HttpResponseBadRequest(content='{"data":[],msg:"invalid request method"}')

    default_size = conf.get_option_value("query", "default_size")
    max_size = conf.get_option_value("query", "max_size")
    params = copy.deepcopy(request.GET)
    if "size" not in params:
        params['size'] = default_size
    elif params['size'] > max_size:
        params['size'] = max_size
    logger.info("query jobs, params=[%s]" % params)

    if task_id != "":
        fuxi_tasks = FuxiTaskRuntime.objects.filter(task_id=task_id)
    elif "job_id" in params:
        fuxi_tasks = FuxiTaskRuntime.objects.filter(job_id=params['job_id'])
    else:
        fuxi_tasks = FuxiTaskRuntime.objects.all().order_by('-id')[:params['size']]
    connection.close()
    serializer = FuxiTaskRuntimeSerializer(fuxi_tasks, many=True)
    logger.info(fuxi_tasks)
    ret_data = {"data":serializer.data}
    return Response(ret_data)


@api_view(['GET'])
def actions(request, action_id=""):
    """
    查询action信息

    :param action_id: 可选参数，默认返回所有的action
    :return:
    """
    if request.method != "GET":
        logger.info("query actions method error, method=[%s]" % request.method)
        return HttpResponseBadRequest(content='{"data":[],msg:"invalid request method"}')

    default_size = conf.get_option_value("query", "default_size")
    max_size = conf.get_option_value("query", "max_size")
    params = copy.deepcopy(request.GET)
    if "size" not in params:
        params['size'] = default_size
    elif params['size'] > max_size:
        params['size'] = max_size
    logger.info("query jobs, params=[%s]" % params)

    if action_id != "":
        fuxi_actions = FuxiActionRuntime.objects.filter(action_id=action_id)
    elif "task_id" in params:
        fuxi_actions = FuxiActionRuntime.objects.filter(task_id=params['task_id'])
    else:
        fuxi_actions = FuxiActionRuntime.objects.all().order_by('-id')[:params['size']]
    connection.close()
    serializer = FuxiActionRuntimeSerializer(fuxi_actions, many=True)
    logger.info(fuxi_actions)
    ret_data = {"data":serializer.data}
    return Response(ret_data)


@api_view(['POST'])
def control(request):
    """
    对job做人工干预

    :param request:
    :return:
    """
    params = copy.deepcopy(request.data)
    logger.info(params)

    #权限验证
    try:
        username = fuxi_auth.get_username(request)
        if not fuxi_auth.is_authenticated(username, "platform_admin", "", "", ""):
            msg = "%s not authenticated" % username
            return HttpResponseBadRequest(content=msg)
    except Exception as e:
        msg = "auth failed, error=[%s]" % str(e)
        return HttpResponseBadRequest(content=msg)

    #return Response({"success":"true", "data":{"failed":"", "msg":"faked"}})
    if "action" not in params or "job_type" not in params:
        ret_data = {"success":"false", "data":{"msg":"action and job_type are required"}}
        return HttpResponseBadRequest(content=json.dumps(ret_data))

    action = params['action']
    control_type = params['control_type']
    del params['action']
    del params['control_type']
    #用户填写条件的时候，对于非必选条件默认值为空字符串，需要过滤掉
    for k, v in params.items():
        if v == "":
            del params[k]

    try:
        username = fuxi_auth.get_username(request)
        controller = JobController()
        result = controller.control(action, control_type, username, params)
        ret_data = {"success":"true", "data":{"failed":result, "msg":""}}
        return Response(ret_data)
    except Exception as e:
        logger.error(traceback.format_exc())
        ret_data = {"success":"false", "data":{"msg":str(e)}}
        return HttpResponseBadRequest(content=json.dumps(ret_data))
