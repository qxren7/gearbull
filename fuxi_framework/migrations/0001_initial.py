# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-14 09:00
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='FuxiActionRuntime',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('action_id', models.CharField(db_index=True, max_length=64, unique=True)),
                ('task_id', models.CharField(db_index=True, max_length=64)),
                ('action_content', models.CharField(max_length=1024)),
                ('seq_id', models.IntegerField()),
                ('start_time', models.CharField(max_length=32)),
                ('finish_time', models.CharField(max_length=32)),
                ('timeout', models.CharField(max_length=10)),
                ('state', models.CharField(max_length=64)),
            ],
            options={
                'db_table': 'fuxi_action_runtime',
            },
        ),
        migrations.CreateModel(
            name='FuxiJobRuntime',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('job_id', models.CharField(db_index=True, max_length=64, unique=True)),
                ('job_type', models.CharField(max_length=64)),
                ('job_priority', models.CharField(max_length=10)),
                ('threshold', models.CharField(max_length=5)),
                ('progress', models.CharField(max_length=5)),
                ('create_time', models.CharField(max_length=32)),
                ('schedule_time', models.CharField(max_length=32)),
                ('finish_time', models.CharField(max_length=32)),
                ('latest_heartbeat', models.CharField(max_length=32)),
                ('timeout', models.CharField(max_length=10)),
                ('control_action', models.CharField(max_length=32)),
                ('user', models.CharField(max_length=32)),
                ('state', models.CharField(max_length=64)),
            ],
            options={
                'db_table': 'fuxi_job_runtime',
            },
        ),
        migrations.CreateModel(
            name='FuxiTaskRuntime',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('task_id', models.CharField(db_index=True, max_length=64, unique=True)),
                ('job_id', models.CharField(db_index=True, max_length=64)),
                ('task_priority', models.CharField(max_length=10)),
                ('entity_type', models.CharField(max_length=64)),
                ('entity_name', models.CharField(max_length=64)),
                ('threshold', models.CharField(max_length=5)),
                ('progress', models.CharField(max_length=5)),
                ('create_time', models.CharField(max_length=32)),
                ('start_time', models.CharField(max_length=32)),
                ('finish_time', models.CharField(max_length=32)),
                ('timeout', models.CharField(max_length=10)),
                ('state', models.CharField(max_length=64)),
            ],
            options={
                'db_table': 'fuxi_task_runtime',
            },
        ),
    ]
