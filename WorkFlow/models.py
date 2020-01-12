# -*- coding: utf-8 -*-

import sys
import time
import copy
import json
import traceback
import threading
import importlib
import subprocess

from retry import retry
from datetime import datetime

import django

from django.db import models
from django.db.models import Q
from jsonfield import JSONField
from django.db import connection

from WorkFlow import msgs
from WorkFlow import exceptions
from django.db import transaction
from django.utils import timezone
from WorkFlow.states import JobStatus
from django.contrib.auth.models import User
from WorkFlow.states import on_job_state_change
from WorkFlow.states import on_task_state_change
from WorkFlow.states import on_action_state_change

from picklefield.fields import PickledObjectField

from . import global_setttings

logger = global_setttings.get_logger("models.log")


# Create your models here.
class WorkFlowBaseModel(models.Model):
    params = JSONField(default={})
    extra_data = JSONField(default={})
    errors = JSONField(default={})

    def update_data(self, data=None):
        """ 更新任务数据"""
        try:
            _extra_data = self.extra_data
            _extra_data.update(data)
            self.extra_data = _extra_data
            self.save()
            return True
        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    def replace_data(self, data=None):
        """ 更新任务数据"""
        try:
            self.extra_data = data
            self.save()
            return True
        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    class Meta:
        abstract = True


class StatData(models.Model):
    name = models.CharField(max_length=128)
    stats = JSONField(default={})
    stat_time = models.CharField(max_length=128)
    create_at = models.DateTimeField(auto_now_add=True)


class Runtime(models.Model):
    data = JSONField(default={})
    create_at = models.DateTimeField(auto_now_add=True)


class Entity(models.Model):
    name = models.CharField(max_length=128, unique=True)
    etype = models.CharField(max_length=128, null=False)
    operate_logs = JSONField(default=[])

    def add_log(self, log):
        logs = self.operate_logs
        log["save_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs.append(log)
        self.operate_logs = logs
        self.save()

    def stat(self):
        result = {}
        result["operate_cnt_in_two_days"] = 0
        result["name"] = self.name
        result["operate_logs"] = self.operate_logs
        for log in self.operate_logs:
            operate_type = log["operate_type"]
            count = result.get(operate_type, 0)
            result[operate_type] = count + 1

            save_time = datetime.strptime(log["save_time"],
                                          "%Y-%m-%d %H:%M:%S")
            now_time = datetime.now()
            dt = now_time - save_time
            seconds_for_days = 60 * 60 * 24 * 2  #  2 days' seconds
            if dt.seconds <= seconds_for_days:
                result["operate_cnt_in_two_days"] += 1
        return result


class Job(WorkFlowBaseModel):
    juuid = models.CharField(max_length=128, null=False, default=None)
    priority = models.CharField(max_length=10)
    threshold = models.CharField(max_length=5)
    progress = models.CharField(max_length=5)
    create_time = models.DateTimeField(auto_now_add=True)
    schedule_time = models.DateTimeField(null=True)
    finish_time = models.DateTimeField(null=True)
    pause_time = models.DateTimeField(null=True)
    state_update_time = models.DateTimeField(null=True)
    latest_heartbeat = models.CharField(max_length=32)
    timeout = models.CharField(max_length=10)
    control_action = models.CharField(max_length=32)
    user = models.CharField(max_length=32)
    server_ip = models.CharField(max_length=128)
    state = models.CharField(max_length=64)
    is_manual = models.BooleanField(default=False)
    is_idempotency = models.BooleanField(default=False)
    task_type = models.CharField(max_length=128, default="")
    tasks_plan = JSONField(default={})
    fail_rate = models.IntegerField(default=0)
    fail_count = models.IntegerField(default=0)
    concurrency = models.IntegerField(default=1)
    continue_after_stage_finish = models.BooleanField(default=False)
    confirms = JSONField(default={})
    executor = models.CharField(max_length=128, default=None)

    owner = models.ForeignKey("auth.User",
                              related_name="jobs",
                              on_delete=models.CASCADE)

    class Meta(WorkFlowBaseModel.Meta):
        db_table = "gearbull_job"

    def is_finish(self):
        """判断job是否处于完成状态"""
        if self.state in JobStatus.FINISH_STATES:
            return True
        else:
            return False

    def has_task_unfinished(self):
        """ 检查job是否有未完成的tasks"""
        unfinish_states = [JobStatus]
        tasks = FuxiTaskRuntime.objects.filter(job_id=self.job_id)
        for t in tasks:
            if t.state in JobStatus.UNFINISH_STATES:
                return True
        return False

    @classmethod
    def create_job(cls, job_info):
        try:
            u = User.objects.get(username=job_info.get("user", "u1"))
            job_runtime = Job(
                owner=u,
                juuid=job_info["juuid"],
                server_ip=job_info["server_ip"],
                task_type=job_info["task_type"],
                state=job_info["state"],
                params=job_info["params"],
                priority=job_info.get("priority", 0),
                threshold=job_info.get("threshold", 100),
                timeout=job_info.get("timeout", 259200), # 3天
                user=job_info.get("user", "u1"),
                fail_rate=job_info.get("fail_rate", 10),
                concurrency=job_info.get("concurrency", 1),
                confirms=job_info.get("confirms", {}),
                continue_after_stage_finish=job_info.get(
                    "continue_after_stage_finish", True),
                is_idempotency=job_info.get("is_idempotency", True),
                executor=job_info.get("executor", "WorkFlowExecutor"),
            )
            job_runtime.save()
        except KeyError as e:
            logger.error(traceback.format_exc())
            raise exceptions.WFFailedRequest(msgs.miss_params % str(e))
        except Exception as e:
            logger.error(traceback.format_exc())
            raise exceptions.WFFailedRequest(msgs.save_job_error %
                                             (str(e), str(job_info)))
        finally:
            connection.close()
        logger.info(msgs.create_job_succ % job_runtime.id)
        return job_runtime


    @classmethod
    def redo(cls, job_id, redo_tasks_states=[JobStatus.FAILED]):
        """
        重做job, 可以指定重做task的状态，默认重做 fail的tasks
        """
        try:
            (status, ip_addr) = subprocess.getstatusoutput("hostname -i")
            _job = Job.objects.get(id=job_id)
            _job_params = copy.deepcopy(_job.params)
            _entities = []
            for t in _job.task_set.filter(
                    Q(state=JobStatus.FAILED) | Q(state=JobStatus.ERROR)):
                _entities.append(t.entity_name)

            _job_params["entities"] = {1: _entities}

            job_runtime = Job(
                priority=_job.priority,
                threshold=_job.threshold,
                timeout=_job.timeout,
                user=_job.user,
                server_ip=ip_addr,
                params=_job_params,
                task_type=_job.task_type,
                fail_rate=_job.fail_rate,
                concurrency=_job.concurrency,
                continue_after_stage_finish=_job.continue_after_stage_finish,
                state=JobStatus.NEW,
            )
            job_runtime.save()
        except KeyError as e:
            raise exceptions.WFFailedRequest(msgs.miss_params % str(e))
        except Exception as e:
            logger.error(traceback.format_exc())
            raise exceptions.WFFailedRequest(msgs.save_job_error %
                                             (str(e), str(_job_params)))
        finally:
            connection.close()
        logger.info(msgs.create_job_succ % job_runtime.id)
        return job_runtime

    def update_job_info(self, info):
        """
        更新job_runtime表的信息
    
        :param info: dict类型，key为job的属性，value为要更新到的值
        :return:
        """
        is_state_change = False
        if "state" in info:
            job_state = Job.objects.get(id=self.id).state
            if job_state != info["state"]:
                is_state_change = True

        for k, v in list(info.items()):
            if hasattr(self, k):
                setattr(self, k, v)
        self.save()
        connection.close()

        if is_state_change:
            on_job_state_change(self, info["state"])

    def pause(self):
        if self.state == JobStatus.CANCELLED:
            return
        self.state = JobStatus.PAUSED
        self.pause_time = timezone.now()
        self.save()

    def resume(self):
        if self.state == JobStatus.CANCELLED:
            return
        self.state = JobStatus.RUNNING
        self.save()

    def cancel(self):
        self.state = JobStatus.CANCELLED
        self.save()

    def confirm(self):
        self.state = JobStatus.NEW
        self.save()

    @property
    def is_paused(self):
        j = Job.objects.get(id=self.id)
        return JobStatus.PAUSED == j.state


class Task(WorkFlowBaseModel):
    """
    Task表
    """

    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    priority = models.CharField(max_length=10)
    entity_type = models.CharField(max_length=64)
    entity_name = models.CharField(max_length=64)
    threshold = models.CharField(max_length=5)
    progress = models.CharField(max_length=5)
    create_time = models.DateTimeField(null=True)
    start_time = models.DateTimeField(null=True)
    finish_time = models.DateTimeField(null=True)
    timeout = models.CharField(max_length=10)
    state = models.CharField(max_length=64)
    task_type = models.CharField(max_length=128, default="")

    class Meta(WorkFlowBaseModel.Meta):
        """
        meta
        """

        db_table = "gearbull_task"

    @classmethod
    def can_next_stage(cls, task_ids):
        can_next = True
        to_run_ids = []
        not_finish_ids = []
        tasks = Task.objects.filter(id__in=task_ids)
        for t in tasks:
            if t.state not in JobStatus.FINISH_STATES:
                can_next = False
                not_finish_ids.append(t.id)
            if t.state == "NEW":
                to_run_ids.append(t.id)

        return (can_next, to_run_ids, not_finish_ids)

    @classmethod
    def create_task(cls, job, task_info):
        """
        创建task，在task的runtime表中插入记录
    
        :param task_info: 待创建的task字段信息
        :return task_runtime: 创建之后的task对象
        :raise util.EFailedRequest: 创建失败异常
        """
        option_params = ["entity_type", "entity_name"]
        for param in option_params:
            if param not in task_info:
                task_info[param] = ""

        try:
            task_runtime = Task(
                priority=task_info["priority"],
                threshold=task_info["threshold"],
                entity_type=task_info["entity_type"],
                entity_name=task_info["entity_name"],
                timeout=task_info["timeout"],
                state=task_info["state"],
            )
            task_runtime.job = job
            task_runtime.save()
        except KeyError as e:
            raise exceptions.WFTypeMismatch(msgs.miss_params % str(e))
        except Exception as e:
            logger.error(traceback.format_exc())
            raise exceptions.WFFailedRequest(msgs.save_task_error %
                                             (str(e), str(task_info)))
        finally:
            connection.close()
        return task_runtime

    def update_task_info(self, info):
        """
        更新task_runtime表的信息
    
        :param info: dict类型，key为task的属性，value为要更新到的值
        :return:
        """
        logger.info(msgs.update_task_info % (self.id, info))
        is_state_change = False
        if "state" in info:
            task_state = Task.objects.get(id=self.id).state
            if task_state != info["state"]:
                is_state_change = True

        for k, v in list(info.items()):
            if hasattr(self, k):
                setattr(self, k, v)
        self.save()
        connection.close()

        if is_state_change:
            on_task_state_change(self, info["state"])

    def skip(self):
        # only can skip  running or paused tasks
        if self.state not in [JobStatus.RUNNING, JobStatus.PAUSED]:
            return
        self.state = JobStatus.SKIPPED
        self.save()


class Action(WorkFlowBaseModel):
    """
    Action表
    """

    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    action_content = models.TextField()
    seq_id = models.IntegerField()
    tree_name = models.CharField(max_length=128, default="")
    method_name = models.CharField(max_length=128, default="")
    create_time = models.DateTimeField(null=True)
    start_time = models.DateTimeField(null=True)
    finish_time = models.DateTimeField(null=True)
    timeout = models.CharField(max_length=10)
    state = models.CharField(max_length=64)
    result = models.TextField(default="")
    error = models.TextField(default="")
    is_executed = models.BooleanField(default=False)

    class Meta(WorkFlowBaseModel.Meta):
        """
        meta
        """

        db_table = "gearbull_action"

    @classmethod
    def create_action(cls, task, index, action_declaration, timeout):
        """
        创建action，在action的runtime表中插入记录
    
        :param action_info: 待创建的action字段信息
        :return action_runtime: 创建之后的action对象
        :raise util.EFailedRequest: 创建失败异常
        """
        try:
            action_runtime = Action(
                action_content=json.dumps(action_declaration),
                seq_id=index,
                timeout=timeout,
                state="NEW",
            )
            action_runtime.task = task
            action_runtime.save()
        except KeyError as e:
            raise exceptions.WFTypeMismatch(msgs.miss_params % str(e))
        except Exception as e:
            logger.error(traceback.format_exc())
            raise exceptions.WFFailedRequest(msgs.save_action_error % e)
        finally:
            connection.close()
        return action_runtime

    def previous_result(self):
        result = None
        if self.seq_id != 0:
            previous_action = self.task.action_set.get(
                tree_name=self.tree_name, seq_id=(self.seq_id - 1))
            result = previous_action.result
        return result

    def update_action_info(self, info):
        """
        更新action_runtime表的信息
    
        :param info: dict类型，key为action的属性，value为要更新到的值
        :return:
        """
        logger.info("update action info, action_id=[%s], info=[%s]" %
                    (self.id, info))
        is_state_change = False
        if "state" in info:
            action_state = Action.objects.get(id=self.id).state
            if action_state != info["state"]:
                is_state_change = True

        for k, v in list(info.items()):
            if hasattr(self, k):
                setattr(self, k, v)
        self.save()
        connection.close()

        if is_state_change:
            logger.info(msgs.action_state_change % self.id)
            on_action_state_change(self, info["state"])


class FlowMap(WorkFlowBaseModel):
    task_type = models.CharField(max_length=255, unique=True)


class Threshold(models.Model):

    static_thresholds = {
        "reboot_num_once_threshold": 5,
        "repair_num_once_threshold": 5,
        "running_reboot_tasks_threshold": 30,
        "running_repair_tasks_threshold": 20,
    }
    dynamic_thresholds_data = {
        "reboot_num_daily_threshold": 10,
    }

    dynamic_thresholds = JSONField(default={})
    create_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    @transaction.atomic
    def singleton(cls):
        thresholds = Threshold.objects.all()
        if len(thresholds) == 0:
            t = Threshold(dynamic_thresholds=cls.dynamic_thresholds_data)
            t.save()
            return t
        elif len(thresholds) == 1:
            t = thresholds[0]
            return t
        elif len(thresholds) > 1:
            raise Exception(msgs.thresholds_exception % len(thresholds))

    @transaction.atomic
    def _set(self, threshold_name, value):
        _thresholds = self.dynamic_thresholds
        _thresholds[threshold_name] = value
        self.dynamic_thresholds = _thresholds
        self.save()

    @transaction.atomic
    def decrease(self, threshold_name, value=1):
        self._set(threshold_name, self.dynamic_thresholds[threshold_name] - 1)

    @transaction.atomic
    def increase(self, threshold_name, value=1):
        self._set(threshold_name, self.dynamic_thresholds[threshold_name] + 1)


class Lock(models.Model):
    target = models.CharField(max_length=255, unique=True)
    cur_number = models.IntegerField(default=0)
    max_number = models.IntegerField(default=0)

    @classmethod
    def get_max_num(cls, *args):
        return 1

    @classmethod
    def get(cls, _target):
        if Lock.objects.filter(target=_target).exists():
            return Lock.objects.get(target=_target)
        else:
            _max_number = Lock.get_max_num()
            l, created = Lock.objects.get_or_create(target=_target,
                                                    max_number=_max_number)
            return l

    @classmethod
    def acquire(cls, _target, num):
        """ 
            申请获得 num 把锁 
            先判断cur_number 是否足够，足够的话，先减去 num，然后返回
            不够的话，直接返回失败
        """
        result = {"target": _target, "is_succ": False, "acquire_num": 0}
        mutex = threading.Lock()
        mutex.acquire()

        _lock = Lock.get(_target)
        if _lock.cur_number >= num:
            _lock.cur_number -= num
            _lock.save()
            result["is_succ"] = True
            result["acquire_num"] = num
            result["cur_number"] = _lock.cur_number

        mutex.release()

        return result

    @classmethod
    def release(cls, _target, num):
        """ 
            申请释放 num 把锁  
            先判断cur_number 是否足够，足够的话，先减去 num，然后返回
            不够的话，直接返回失败
        """
        result = {"target": _target, "is_succ": False, "release_num": 0}
        mutex = threading.Lock()
        mutex.acquire()

        _lock = Lock.get(_target)
        if _lock.cur_number + num <= _lock.max_number:
            _lock.cur_number += num
            _lock.save()
            result["is_succ"] = True
            result["release_num"] = num
            result["cur_number"] = _lock.cur_number

        mutex.release()

        return result


class ActionTree(models.Model):

    NEW = "NEW"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    SUCCESS = "SUCCESS"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, default=None)

    root = PickledObjectField()
    trees = PickledObjectField()
    state = models.CharField(
        max_length=64,
        default="NEW")  # default = 'NEW',  RUNNING, FAILED, SUCCESS


class Node:
    def __init__(self, name, action_id):
        self._name = name
        self._action_id = action_id


class ClauseTree:
    def __init__(self, nodes, task_id):
        self._task_id = task_id
        self._nodes = nodes
        self._true_clause = None
        self._false_clause = None
        self._iterate_index = 0

    @property
    def leaf(self):
        if len(self._nodes) > 0:
            return self._nodes[-1]
        else:
            return None

    @property
    def action_tree(self):
        return Task.objects.get(id=self._task_id).actiontree_set.first()

    def set_tree_state(self, s):
        tree = self.action_tree
        tree.state = s
        tree.save()

    def reset_index(self):
        self._iterate_index = 0

    def set_index(self, idx):
        self._iterate_index = idx

    def on_true(self, tree):
        self._true_clause = tree

    def on_false(self, tree):
        self._false_clause = tree

    def simple_iterate(self, clause):
        for n in self._nodes:
            self._iterate_index += 1
            print("%s: %s %s" % (self._iterate_index, n._name, n._action_id))

        if clause == True and self._true_clause:  # true_clause
            self._true_clause.set_index(self._iterate_index)
            self._true_clause.iterate(True)
        elif clause == False and self._false_clause:
            self._false_clause.set_index(self._iterate_index)
            self._false_clause.iterate(False)

    def iterate_execute(self):
        result = False
        for index, node in enumerate(self._nodes):
            self._iterate_index += 1
            logger.info("%s: %s %s" %
                        (self._iterate_index, node._name, node._action_id))
            action = Action.objects.get(id=node._action_id)
            result = do_action(action)
            # 如果没进行到最后一个action 且 result 为false，那么就认为本次迭代失败了，直接返回false
            # 因为当前错误分支，只支持最后一个node 有分支功能, ['n1','n2','n3'], 只有n3有分支
            logger.info(
                "clause: action=[%s] method_name %s,  _false_clause %s, _true_clause %s, result %s, index %s node len %s"
                % (action.id, action.method_name, self._false_clause,
                   self._true_clause, result, index, len(self._nodes)))
            if not result and index < len(self._nodes) - 1:
                self.set_tree_state(ActionTree.FAILED)
                return False

        if result == True:
            # 如果 result == True，同时 _true_clause 为空，那么action_tree 为 success
            if self._true_clause:
                result = self._true_clause.iterate_execute()
            else:
                self.set_tree_state(ActionTree.SUCCESS)
        elif result == False:
            # 如果 result == False，同时 _false_clause 为空，那么action_tree 为 fail
            if self._false_clause:
                result = self._false_clause.iterate_execute()
            else:
                self.set_tree_state(ActionTree.FAILED)

        # 如果 _true_clause _false_clause 都为空，说明是叶子结点，在此判断tree 的状态
        if not self._true_clause and not self._false_clause:
            s = ActionTree.SUCCESS if result else ActionTree.FAILED
            self.set_tree_state(s)

        c = msgs.action_detail % (
            self.action_tree.id,
            self._true_clause,
            self._false_clause,
            self.action_tree.state,
        )
        logger.info(c)

        return result


@retry(tries=3, delay=3)
def myimport(_modlue, _class):
    mod = importlib.import_module(_modlue)
    klass = getattr(mod, _class)
    return klass


def execute_method(method, params):
    retries = 1
    try_interval = 3  # 30 s
    if "execute_retries" in params["extra_params"]:
        max_try = params["extra_params"]["execute_retries"]
    else:
        max_try = 1

    while True:
        is_succ, result = method(params)
        if is_succ:
            return is_succ, result
        else:
            if retries < max_try:
                retries += 1
                time.sleep(try_interval)
            else:
                _params = copy.deepcopy(params)
                _params["extra_params"] = "{..}"
                logger.error(msgs.try_execute_fail %
                             (retries, method.__name__, _params))
                return is_succ, result


def bash_do_action(action, declaration, result_key):
    job_path = declaration["src_path"]
    module = declaration["module"]
    method = declaration["method"]
    params = declaration["params"]

    info = {"state": "RUNNING", "start_time": timezone.now()}
    action.update_action_info(info)
    action.is_executed = True
    action.save()

    p = params['extra_params']
    deploy_params = "%s %s %s %s %s" % (params['host'], p['name'],
                                        p['version'], p['product_path'],
                                        p['deploy_path'])
    cmd = " cd %s && source ./%s &&  %s '%s' '%s' " % (
        job_path, module, method, deploy_params, action.previous_result())
    (status, result) = subprocess.getstatusoutput(cmd)
    logger.info("cmd: %s, status: %s, result: %s" % (cmd, status, result))
    if status == 0:
        cmd_result = json.loads(result)
        is_succ = cmd_result['is_succ']
    else:
        is_succ = False

    action.result = str(result)
    action.save()
    #TASKS_RESULT_REDIS.set(result_key, action.result)

    return is_succ, result


def get_instance(declaration):
    job_path = declaration["src_path"]
    if job_path not in sys.path:
        sys.path.insert(0, job_path)
    time.sleep(1)

    klass = myimport(declaration["module"], declaration["class"])
    instance = klass()
    return instance


def __python_do_sub_actions(sperator, method_name, declaration, instance):
    sub_method_names = method_name.replace(' ', '').split(sperator)
    is_succs = []
    results = []
    for sm in sub_method_names:
        method = getattr(instance, sm)
        is_succ, result = execute_method(method, declaration["params"])
        is_succs.append(is_succ)
        results.append("action:%s, result:%s" % (sm, result))
    method_result = " ".join(results)
    return is_succs, method_result


def python_do_sub_actions(declaration):
    instance = get_instance(declaration)
    method_name = declaration["method"]
    is_succs = False
    result = None
    if "|" in method_name:
        is_succs, result = __python_do_sub_actions('|', method_name,
                                                   declaration, instance)
        is_succ = True in is_succs  # 如果有任意的 True, 可以认为这个action是True
        return is_succ, result
    elif "&" in method_name:
        is_succs, result = __python_do_sub_actions('&', method_name,
                                                   declaration, instance)
        is_succ = False not in is_succs  #当一个False 都没有, 才可以认为这个action是True
        return is_succ, result
    else:
        method = getattr(instance, declaration["method"])
        is_succ, result = execute_method(method, declaration["params"])
    return is_succ, result


def python_do_action(action, declaration, result_key):
    info = {"state": "RUNNING", "start_time": timezone.now()}
    action.update_action_info(info)
    action.is_executed = True
    action.save()
    is_succ, result = python_do_sub_actions(declaration)
    action.result = str(result)
    action.save()
    #TASKS_RESULT_REDIS.set(result_key, action.result)
    return is_succ, result


def do_action(action):
    """
    一个task内部具体的actions执行逻辑
    :param task: task对象
    :return:
    :raise:
    """
    try:

        task = action.task
        job = task.job

        result_key = "%s-%s-%s-%s" % (job.juuid, job.id, task.id, action.id)

        if action.is_executed and not job.is_idempotency:
            logger.warn(msgs.not_reentry % (job.id, action.id))
            return False  # if job is not idempotency, action can not re-execute

        if action.is_executed and job.is_idempotency:
            # 只有以下两种情况才直接返回，否则就让action 重新执行
            if action.result:
                if action.state == "SUCCESS":
                    logger.warn(msgs.reentry %
                                (job.id, action.id, action.state))
                    return True
                elif action.state in ["FAILED", "SKIPPED"]:
                    logger.warn(msgs.reentry %
                                (job.id, action.id, action.state))
                    return False

        declaration = json.loads(action.action_content)

        if 'exe_type' in declaration and declaration['exe_type'] == 'Bash':
            is_succ, result = bash_do_action(action, declaration, result_key)
        else:
            is_succ, result = python_do_action(action, declaration, result_key)

        if is_succ:
            if "SKIP" in result:
                logger.info(msgs.action_skip %
                            (task.id, action.id, task.entity_name, result))
                info = {"state": "SKIPPED", "finish_time": timezone.now()}
                action.update_action_info(info)
                return True
            else:
                logger.info(msgs.action_succ %
                            (task.id, action.id, task.entity_name, result))
                info = {"state": "SUCCESS", "finish_time": timezone.now()}
                action.update_action_info(info)
        else:
            _declaration = copy.deepcopy(declaration)
            _declaration["params"]["extra_params"] = "{..}"
            logger.error(
                msgs.action_fail %
                (_declaration, task.id, action.id, task.entity_name, result))
            info = {"state": "FAILED", "finish_time": timezone.now()}
            action.update_action_info(info)
            return False
    except Exception as e:
        logger.error(traceback.format_exc())
        info = {"state": "ERROR", "start_time": timezone.now()}
        action.update_action_info(info)
        task.update_task_info(info)
        connection.close()
        return False
    finally:
        connection.close()
    return True
