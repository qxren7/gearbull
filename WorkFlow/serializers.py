from rest_framework import serializers

from WorkFlow.models import Job
from WorkFlow.models import Task
from WorkFlow.models import Action

from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    jobs = serializers.PrimaryKeyRelatedField(many=True,
                                              queryset=Job.objects.all())

    class Meta:
        model = User
        fields = ["id", "username", "jobs"]


class JobSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = Job
        fields = [
            "id",
            "priority",
            "threshold",
            "progress",
            "create_time",
            "schedule_time",
            "finish_time",
            "pause_time",
            "latest_heartbeat",
            "timeout",
            "control_action",
            "user",
            "server_ip",
            "state",
            "is_manual",
            "is_idempotency",
            "task_type",
            "tasks_plan",
            "fail_rate",
            "fail_count",
            "concurrency",
            "continue_after_stage_finish",
            "confirms",
            "owner",
        ]

class TaskSerializer(serializers.ModelSerializer):

    class Meta:
        model = Task
        fields = [
            "id",
            "priority",
            "entity_type",
            "entity_name",
            "threshold",
            "progress",
            "create_time",
            "finish_time",
            "timeout",
            "state",
            "task_type",
        ]

class ActionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Action
        fields = [
            "id",
            "action_content",
            "seq_id",
            "tree_name",
            "method_name",
            "create_time",
            "finish_time",
            "timeout",
            "state",
            "result",
            "error",
            "is_executed",
        ]
