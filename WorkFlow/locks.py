# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from WorkFlow.models import Job
from WorkFlow.models import Lock


def refresh():
    jobs = Job.objects.all()
    task_types = list(set([j.task_type for j in jobs]))
    for tt in task_types:
        task_type_lock = "%s_%s" % (tt, "lock")
        l = Lock.get(task_type_lock)
