# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
import sys
import json
import uuid
import requests
import traceback

from django.shortcuts import render
from django.http import HttpResponse
from django.core import serializers
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions
from rest_framework import generics
from rest_framework import viewsets

from conf import task_trees as TaskTrees
from WorkFlow.models import Job
from WorkFlow.models import Task
from WorkFlow.models import Action
from WorkFlow.models import FlowMap
from WorkFlow.states import JobStatus
from WorkFlow.models import Threshold
from WorkFlow.permissions import IsOwnerOrReadOnly
from WorkFlow.global_setttings import LOCAL_SERVER

from WorkFlow.serializers import JobSerializer
from WorkFlow.serializers import TaskSerializer
from WorkFlow.serializers import ActionSerializer
from WorkFlow.serializers import UserSerializer

import random

############################################
# RESTFUL API START


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This viewset automatically provides `list` and `detail` actions.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer


class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly
    ]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer


class ActionViewSet(viewsets.ModelViewSet):
    queryset = Action.objects.all()
    serializer_class = ActionSerializer


# RESTFUL API END
############################################


def gen_response_msg(code=0, message="ok", extra=None):
    msg = {"code": code, "message": message, "extra": extra}
    return msg


def json_response(code=0, message="ok", extra=None):
    msg = gen_response_msg(code, message, extra)
    return HttpResponse(json.dumps(msg))


@csrf_exempt
def api(request, task):
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


def get_job_info(request):
    if len(request.POST.dict()) > 0:
        data = request.POST.dict()
        job_info = json.loads(data['job_info'])
    elif len(request.body) > 0:
        data = request.body
        job_info = json.loads(data)
    else:
        job_info = {}
    return job_info


def gen_params(job_info):
    if 'params' in job_info: return job_info['params']
    params = {
        'entities': {1: job_info['targets']},
        'service_name': job_info['task_type'],
        'execute_mode': job_info.get('execute_mode','batch_mode'),
        'job_name': job_info.get('job_name', ''),
        'job_desc': job_info.get('job_desc', ''),
        'launcher_user': job_info.get("user", "u1"),
    }
    return params


def create_job(request):
    job_info = get_job_info(request)
    if len(job_info) == 0: return HttpResponse("POST data is empty, please check.")
    job_info["juuid"] = str(uuid.uuid4())
    job_info["server_ip"] = LOCAL_SERVER
    job_info["owner"] = "master"
    job_info["state"] = "NEW"
    job_info["params"] = gen_params(job_info)
    job = Job.create_job(job_info)
    response = {}
    response["result"] = True
    response["msg"] = "Create Job success."
    response["job_id"] = job.id
    return HttpResponse(json.dumps(response))


def pause_job(request):
    job_id = request.GET["job_id"]
    job = Job.objects.get(id=job_id)
    job.pause()
    return HttpResponse("ok")


def resume_job(request):
    job_id = request.GET["job_id"]
    job = Job.objects.get(id=job_id)
    job.resume()
    return HttpResponse("ok")


def cancel_job(request):
    job_id = request.GET["job_id"]
    job = Job.objects.get(id=job_id)
    job.cancel()
    return HttpResponse("ok")


def skip_task(request):
    task_id = request.GET["task_id"]
    task = Task.objects.get(id=task_id)
    task.skip()
    return HttpResponse("ok")


def confirm_job(request):
    job_id = request.GET["job_id"]
    job = Job.objects.get(id=job_id)
    if job.state == "WAIT_CONFIRM":
        job.confirm()
        msg = "confirm ok."
    else:
        msg = "confirm fail, job=[%s] is not in WAIT_CONFIRM state." % job.id
    return HttpResponse(msg)


def redo_job(request):
    job_id = request.GET["job_id"]

    job = Job.objects.get(id=job_id)

    if job.state not in [
            JobStatus.SUCCESS,
            JobStatus.FAILED,
            JobStatus.TIMEOUT,
            JobStatus.ERROR,
            JobStatus.SKIPPED,
            JobStatus.CANCELLED,
    ]:
        return HttpResponse("job is still running, can not redo")

    job = Job.redo(job_id)
    msg = {"job_id": job.id}
    return HttpResponse(json.dumps(msg))


def is_entity_in_flow(request):
    entity = request.GET["entity"]
    tasks = Task.objects.filter(entity_name=entity,
                                state__in=JobStatus.UNFINISH_STATES)
    job_state = tasks[0].job.state
    if job_state in JobStatus.FINISH_STATES:
        result = {entity: False}
    elif tasks.count() > 1:  # 1个表示当前正在运行的任务
        result = {entity: True}
    else:
        result = {entity: False}
    return json_response(extra=result)


def task_stat(request):
    _task_type = request.GET["task_type"]
    jobs = Job.objects.filter(task_type=_task_type,
                              state__in=JobStatus.UNFINISH_STATES)
    cur_running_tasks_cnt = 0
    for j in jobs:
        cnt = j.task_set.filter(state=JobStatus.RUNNING).count()
        cur_running_tasks_cnt += cnt

    t = Threshold.singleton()
    result1 = {
        "cur_running_tasks_cnt":
        cur_running_tasks_cnt,
        "reboot_num_daily_threshold":
        t.dynamic_thresholds["reboot_num_daily_threshold"],
    }
    result = dict(result1, **t.static_thresholds)

    return json_response(extra=result)


def decrease_threshold(request):
    params = request.GET
    threshold_name = params["threshold_name"]
    value = params["value"]

    t = Threshold.singleton()
    t.decrease(threshold_name)

    return json_response()


def get_running_job(request):
    entity_name = request.GET["entity_name"]
    task = Task.objects.filter(entity_name=entity_name).first()
    if task:
        result = {"job_id": task.job.id}
    else:
        result = {"job_id": None}
    return json_response(extra=result)


def job_history(request):
    params = request.GET.dict()
    job_history_data = []
    task_type_name_map = {}
    for j in Job.objects.all().order_by("-create_time"):
        if "job_name" not in j.params or "job_desc" not in j.params:
            continue
        if ("service_name" in j.params
                and params["service_name"] in j.params["service_name"]):
            item = {}
            item["service_name"] = params["service_name"]
            item["job_name"] = j.params["job_name"]
            item["job_desc"] = j.params["job_desc"]
            item["job_user"] = j.user
            item["job_id"] = j.id
            item["job_state"] = j.state
            item["task_type"] = (task_type_name_map[j.task_type]
                                 if j.task_type in task_type_name_map else
                                 j.task_type)
            item["start_time"] = j.create_time.strftime("%Y-%m-%d %H:%M:%S")
            item["succ_task_cnt"] = j.task_set.filter(
                state=JobStatus.SUCCESS).count()
            item["fail_task_cnt"] = j.task_set.filter(
                state=JobStatus.FAILED).count()
            item["all_task_cnt"] = j.task_set.all().count()
            if "version_name" in j.params:
                item["version_name"] = j.params["version_name"]
            job_history_data.append(item)

    return HttpResponse(json.dumps(job_history_data))


def flows(request):
    trees = list(TaskTrees.trees_dict.keys())
    return HttpResponse(json.dumps(trees))


def flow(request):
    tree_name = request.GET["name"]
    tree_def = TaskTrees.trees_dict[tree_name]
    return HttpResponse(json.dumps(tree_def))


def show_flow(request):
    try:
        result = {}
        job_id = request.GET["job_id"]
        j = Job.objects.get(id=job_id)
        tasks = {}
        for t in j.task_set.all():
            actions = []
            for a in t.action_set.all():
                actions.append("action:%s(%s) %s" % (a.method_name, a.id, a.state))
            k = "Task(%s) %s" % (t.id, t.state)
            tasks[k] = actions
        
        k = "Job(%s) %s" % (j.id, j.state)
        result[k] = tasks
        return HttpResponse(json.dumps(result))
    except Exception as e:
        return HttpResponse(str(e))
