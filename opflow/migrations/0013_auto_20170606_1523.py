# -*- coding: utf-8 -*-
"""
# Generated by Django 1.10.6 on 2017-06-06 15:23
"""
from __future__ import unicode_literals

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    """ Migration """

    dependencies = [
        ('zhongjing', '0012_auto_20170605_2103'),
    ]

    operations = [
        migrations.AddField(
            model_name='sli',
            name='expected_num',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='sli',
            name='total_num',
            field=models.FloatField(default=0),
        ),
    ]
