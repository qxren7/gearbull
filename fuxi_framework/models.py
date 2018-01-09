#! encoding=utf-8
from __future__ import unicode_literals

from django.db import models


# Create your models here.


class FuxiJobRuntime(models.Model):
    """
    Job表
    """
    id = models.AutoField(primary_key=True)
    job_id = models.CharField(db_index=True, unique=True, max_length=64)
    job_type = models.CharField(max_length=64)
    job_priority = models.CharField(max_length=10)
    threshold = models.CharField(max_length=5)
    progress = models.CharField(max_length=5)
    create_time = models.DateTimeField(auto_now_add=True)
    schedule_time = models.DateTimeField(null=True)
    finish_time = models.DateTimeField(null=True)
    latest_heartbeat = models.CharField(max_length=32)
    timeout = models.CharField(max_length=10)
    control_action = models.CharField(max_length=32)
    user = models.CharField(max_length=32)
    server_ip = models.CharField(max_length=32)
    state = models.CharField(max_length=64)

    class Meta(object):
        """
        meta
        """
        db_table = "fuxi_job_runtime"
        app_label = "fuxi_framework"

    def is_finish(self):
        """判断job是否处于完成状态"""
        from fuxi_framework.job_engine.runtime_manager import JobStatus
        if self.state in JobStatus.FINISH_STATES:
            return True
        else:
            return False

    def has_task_unfinished(self):
        """ 检查job是否有未完成的tasks"""
        from fuxi_framework.job_engine.runtime_manager import JobStatus
        unfinish_states = [JobStatus]
        tasks = FuxiTaskRuntime.objects.filter(job_id = self.job_id)
        for t in tasks:
            if t.state in JobStatus.UNFINISH_STATES:
                return True
        return False


class FuxiTaskRuntime(models.Model):
    """
    Task表
    """
    id = models.AutoField(primary_key=True)
    task_id = models.CharField(db_index=True, unique=True, max_length=64)
    job_id = models.CharField(db_index=True, max_length=64)
    task_priority = models.CharField(max_length=10)
    entity_type = models.CharField(max_length=64)
    entity_name = models.CharField(max_length=64)
    threshold = models.CharField(max_length=5)
    progress = models.CharField(max_length=5)
    create_time = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField(null=True)
    finish_time = models.DateTimeField(null=True)
    timeout = models.CharField(max_length=10)
    state = models.CharField(max_length=64)

    class Meta(object):
        """
        meta
        """
        db_table = "fuxi_task_runtime"
        app_label = "fuxi_framework"


class FuxiActionRuntime(models.Model):
    """
    Action表
    """
    id = models.AutoField(primary_key=True)
    action_id = models.CharField(db_index=True, unique=True, max_length=64)
    task_id = models.CharField(db_index=True, max_length=64)
    action_content = models.TextField()
    seq_id = models.IntegerField()
    create_time = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField(null=True)
    finish_time = models.DateTimeField(null=True)
    timeout = models.CharField(max_length=10)
    state = models.CharField(max_length=64)

    class Meta(object):
        """
        meta
        """
        db_table = "fuxi_action_runtime"
        app_label = "fuxi_framework"


class FuxiPermissionInfo(models.Model):
    """
    伏羲平台权限信息
    """
    id = models.AutoField(primary_key=True)
    permission = models.CharField(max_length=32, unique=True)

    class Meta(object):
        """
        meta
        """
        db_table = "fuxi_permission_info"
        app_label = "fuxi_framework"


class FuxiRoleInfo(models.Model):
    """
    伏羲平台角色信息
    """
    id = models.AutoField(primary_key=True)
    role = models.CharField(max_length=64)
    permission = models.ForeignKey(FuxiPermissionInfo, null=True, 
            to_field="permission", on_delete=models.SET_NULL)

    class Meta(object):
        """
        meta
        """
        db_table = "fuxi_role_info"
        app_label = "fuxi_framework"


class FuxiUserInfo(models.Model):
    """
    伏羲平台用户信息
    """
    id = models.AutoField(primary_key=True)
    user = models.CharField(max_length=32)
    user_type = models.IntegerField()
    role = models.CharField(max_length=64)
    product = models.CharField(max_length=64)
    module = models.CharField(max_length=64)
    fuxi_app = models.CharField(max_length=64)

    class Meta(object):
        """
        meta
        """
        db_table = "fuxi_user_info"
        app_label = "fuxi_framework"


class FuxiControlInfo(models.Model):
    """
    伏羲平台的人工干预历史信息
    """
    id = models.AutoField(primary_key=True)
    action = models.CharField(max_length=16)
    user = models.CharField(max_length=32)
    trigger_time = models.DateTimeField(null=True)
    finish_time = models.DateTimeField(null=True)
    result = models.CharField(max_length=32)
    conditions = models.CharField(max_length=1024)
    detail = models.CharField(max_length=1024)

    class Meta(object):
        """
        meta
        """
        db_table = "fuxi_control_info"
        app_label = "fuxi_framework"


class FuxiControlState(models.Model):
    """
    伏羲平台的人工干预状态,用于对一键暂停等全局控制的细粒度干预
    0: ok
    1: pause
    """
    id = models.AutoField(primary_key=True)
    job_type = models.CharField(max_length=64)
    new_job_state = models.IntegerField()
    running_job_state = models.IntegerField()

    class Meta(object):
        """
        meta
        """
        db_table = "fuxi_control_state"
        app_label = "fuxi_framework"
