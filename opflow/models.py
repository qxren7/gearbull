#! encoding=utf-8
"""
models.py
"""
from __future__ import unicode_literals

import os
import logging
import traceback

from django.db import models
from jsonfield import JSONField
from django.utils import timezone

from fuxi_framework.common_lib import log

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
log.init_log("%s/log/models" % CUR_DIR)
logger = logging.getLogger("models")


class HostInfo(object):
    """机器参数信息类"""

    def __init__(self, host, reason, cluster):
        """
        :host: @todo
        :reason: @todo
        :cluster: @todo

        """
        self.host = host
        self.reason = reason
        self.cluster = cluster
        

class JobInfo(models.Model):
    """
    zhongjing job信息表
    """
    id = models.AutoField(primary_key=True)
    job = models.OneToOneField("fuxi_framework.FuxiJobRuntime", to_field="job_id")
    job_params = JSONField(default={})
    tasks_plan = JSONField(default={})
    is_manual = models.BooleanField(default=False)
    errors = JSONField(default={})

    @property
    def host_infos(self):
        """
        :returns: 返回HostInfo 列表, 通过类的方式组织host 的多个属性信息，便于扩展及遍历操作

        """
        result = {}
        for cluster, host_info_dicts_list in self.job_params['hosts'].items():
            host_infos_list = []
            for item in host_info_dicts_list:
                h = item['host'].replace('\r', "").replace('\n', "")
                host_info = HostInfo(h, item['reason'], cluster)
                host_infos_list.append(host_info)
            result[cluster] = host_infos_list
        return result 


class TaskInfo(models.Model):
    """zhongjing task信息表"""
    id = models.AutoField(primary_key=True)
    task = models.OneToOneField("fuxi_framework.FuxiTaskRuntime", to_field="task_id")
    cluster = models.CharField(max_length=64)
    app = models.CharField(max_length=1024)
    task_type = models.CharField(max_length=1024, default='')
    reason = models.CharField(max_length=1024)
    task_data = JSONField(default={})

    def update_task_data(self, data=None):
        """ 更新任务数据"""
        try:
            _task_data = self.task_data
            _task_data.update(data)
            self.task_data = _task_data
            self.save()
        except Exception as e:
            logger.error(traceback.format_exc())
    
class Sli(models.Model):
    """Service Level Indicator, 指标统计信息表"""
    uuid = models.CharField(max_length=400, null=False)
    target = models.CharField(max_length=200, null=False)
    cluster = models.CharField(max_length=64, null=False)
    type = models.CharField(max_length=200, null=False)
    service = models.CharField(max_length=1000, null=False, default='')
    value = models.FloatField(null=False)
    expected_num = models.FloatField(default=0)
    total_num = models.FloatField(default=0)
    calc_time = models.DateTimeField(auto_now_add=True)
    extra_data = JSONField(default={})


class JsonData(models.Model):
    """业务数据存储"""
    key = models.CharField(max_length=255, null=False, unique=True)
    json_data = JSONField(default={})
    save_time = models.DateTimeField(auto_now_add=True)

    # 一个需求，存放一台机器的历史操作记录，比如 freeze, repair, deploy_agent, 这里的表应该如何设计才具备良好的扩展性？ 

    @classmethod
    def save_data(cls, _key, cur_date, _data):
        """ save_data """
        try:
            data, created = JsonData.objects.get_or_create(key=_key)
            data.json_data = {
                    "data": _data,
                    "date": cur_date,
                    }
            data.save()
            return True
        except Exception as e:
            logger.error(traceback.format_exc())
            return False


    

class FailLog(models.Model):
    """失败日志，用于分析长尾原因 """
    task_type = models.CharField(max_length=255, null=False)
    entity = models.CharField(max_length=255, null=False)
    reason = models.TextField(blank=False, null=False)
    save_time = models.DateTimeField(auto_now_add=True)
    job_id = models.CharField(max_length=255, default='')
        
