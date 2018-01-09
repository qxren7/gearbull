#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: serializers.py
Date: 2017/03/29 13:51:00
"""

from rest_framework import serializers
from models import FuxiJobRuntime
from models import FuxiTaskRuntime
from models import FuxiActionRuntime

class FuxiJobRuntimeSerializer(serializers.ModelSerializer):
    """
    job
    """
    class Meta(object):
        """
        meta
        """
        model = FuxiJobRuntime
        fields = '__all__'


class FuxiTaskRuntimeSerializer(serializers.ModelSerializer):
    """
    task
    """
    class Meta(object):
        """
        meta
        """
        model = FuxiTaskRuntime
        fields = '__all__'


class FuxiActionRuntimeSerializer(serializers.ModelSerializer):
    """
    action
    """
    class Meta(object):
        """
        meta
        """
        model = FuxiActionRuntime
        fields = '__all__'


