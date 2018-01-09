#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: entity.py
Date: 2017/03/30 20:34:36
"""

import json
import os
import sys

from common_lib import util

ENTITY_TYPE_APP = 'app'
ENTITY_TYPE_INSTANCE = 'instance'
ENTITY_TYPE_HOST = 'host'
ENTITY_TYPES = [ENTITY_TYPE_APP, ENTITY_TYPE_INSTANCE, ENTITY_TYPE_HOST]

_IS_MOCK = False

def set_mode(mode):
    """
    设置是否为mock模式

    :param mode: 启动模式 mock | online
    """
    global _IS_MOCK
    if mode == 'mock':
        _IS_MOCK = True
        log.tinfo('set opal mode: mock')
    else:
        log.tinfo('set opal mode: online')
        _IS_MOCK = False


class BaseEntity(object):
    """
    运维实体基类
    """

    def __init__(self):
        self.entity_name = None
        self.entity_type = None

    def __str__(self):
        return json.dumps(self.__dict__)


class App(BaseEntity):
    """
    应用
    """
    def __init__(self):
        """
        """
        pass


class Instance(BaseEntity):
    """
    实例
    """
    def __init__(self):
        """
        """
        pass

    def update_tags(self, tags, extra):
        """
        更新实例tag

        :param tags: tag列表
        :param extra: 附加信息，dict类型
        """
        raise util.ENotImplement()

    def disable(self):
        """
        屏蔽实例, 从连接关系中去除
        """
        raise util.ENotImplement()

    def enable(self):
        """
        启用实例, 接入连接关系
        """
        raise util.ENotImplement()

    def restart(self):
        """
        按照可用度重启实例进程
        """
        raise util.ENotImplement()

    def stop(self):
        """
        停止实例进程
        """
        raise util.ENotImplement()

    def start(self):
        """
        启动实例进程
        """
        raise util.ENotImplement()

    def reload(self):
        """
        重载实例进程
        """
        raise util.ENotImplement()

    def deploy(self):
        """
        部署实例
        """
        raise util.ENotImplement()


class Host(BaseEntity):
    """
    机器
    """
    def __init__(self):
        """
        """
        pass

    def reboot(self):
        """
        服务器重启
        """
        raise util.ENotImplement()

    def reinstall(self):
        """
        重装
        """
        raise util.ENotImplement()

    def __getattr__(self, item):
        return object.__getattribute__(self, item)


