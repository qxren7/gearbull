# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-16 13:50
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('zhongjing', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskPlan',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('plan', jsonfield.fields.JSONField()),
            ],
        ),
    ]
