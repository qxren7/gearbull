# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-09-04 16:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fuxi_framework', '0004_auto_20170620_1506'),
    ]

    operations = [
        migrations.CreateModel(
            name='FuxiControlInfo',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('action', models.CharField(max_length=16)),
                ('user', models.CharField(max_length=32)),
                ('trigger_time', models.DateTimeField(null=True)),
                ('finish_time', models.DateTimeField(null=True)),
                ('result', models.CharField(max_length=32)),
                ('conditions', models.CharField(max_length=1024)),
                ('detail', models.CharField(max_length=1024)),
            ],
            options={
                'db_table': 'fuxi_control_info',
            },
        ),
    ]
