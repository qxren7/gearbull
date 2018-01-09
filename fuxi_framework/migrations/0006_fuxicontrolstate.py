# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-09-20 17:01
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fuxi_framework', '0005_fuxicontrolinfo'),
    ]

    operations = [
        migrations.CreateModel(
            name='FuxiControlState',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('job_type', models.CharField(max_length=64)),
                ('new_job_state', models.IntegerField()),
                ('running_job_state', models.IntegerField()),
            ],
            options={
                'db_table': 'fuxi_control_state',
            },
        ),
    ]
