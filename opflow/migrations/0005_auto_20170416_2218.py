# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-16 14:18
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zhongjing', '0004_auto_20170416_2203'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='jobinfo',
            name='job_params',
        ),
        migrations.RemoveField(
            model_name='jobinfo',
            name='tasks_plan',
        ),
    ]
