# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: beehive_wrapper.py
Date: 2017/04/12 
"""

import os
import sys
import commands
import json
import traceback

import logging

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
BHCLI_BIN = 'python %s/bhcli_rpc/bhcli ' % CUR_DIR


logger = logging.getLogger("beehive_wrapper")


def __get_tags_by_host(cluster, host):
    """
    :host: @todo
    :returns: @todo

    """
    cmd = '%s machine  describe --host=%s --cluster=%s ' % (BHCLI_BIN, host, cluster)
    tags = []
    try:
        status, output = commands.getstatusoutput(cmd)
        result = json.loads(output)
        tags = result['hostInfo']['tags']
    except Exception as e:
        print "Warning: can not get tags of [host:%s], return empty tags set." % host, e

    return tags


def __get_apps_by_host(cluster, host):
    """@todo: Docstring for get_app_by_host

    :cluster: @todo
    :host: @todo
    :returns: @todo

    """
    cmd = '%s machine  describe --host=%s --cluster=%s ' % (BHCLI_BIN, host, cluster)
    apps = []
    try:
        status, output = commands.getstatusoutput(cmd)
        result = json.loads(output)
        apps = [group['groupId']['groupName'] for group in result['hostInfo']['containerIds']]
    except Exception as e:
        print "Warning: can not get apps of [host:%s], return empty apps set." % host, e

    return apps


def __freeze_host(host):
    """@todo: Docstring for get_app_by_host

    :cluster: @todo
    :host: @todo
    :returns: @todo

    """
    logger.info("call bhcli to freeze host=[%s]", host)
    return True
    '''
    cmd = '%s machine  describe --host=%s --cluster=%s ' % (BHCLI_BIN, host, cluster)
    try:
        status, output = commands.getstatusoutput(cmd)
        result = json.loads(output)
        apps = [group['groupId']['groupName'] for group in result['hostInfo']['containerIds']]
    except Exception as e:
        print "Warning: can not get apps of [host:%s], return empty apps set." % host, e

    return apps


    ret = False
    cluster = extra_info['cluster']
    params = {"host": ip, "reason": "2", "cluster": cluster  }
    url = LOCAL_API['freeze']
    res = requests.post(url, data = json.dumps(params)).json() 
    if res['status'] == 0:
        ret = True

    return ret
    '''
 

def __unfreeze_host(host):
    """@todo: Docstring for get_app_by_host

    :cluster: @todo
    :host: @todo
    :returns: @todo

    """
    logger.info("call bhcli to unfreeze host=[%s]", host)
    return True
    '''
    cmd = '%s machine  describe --host=%s --cluster=%s ' % (BHCLI_BIN, host, cluster)
    return unfreeze true or false
    try:
        status, output = commands.getstatusoutput(cmd)
        result = json.loads(output)
        apps = [group['groupId']['groupName'] for group in result['hostInfo']['containerIds']]
    except Exception as e:
        print "Warning: can not get apps of [host:%s], return empty apps set." % host, e

    return apps

    ret = False
    if not extra_info:
        return True
    cluster = extra_info['cluster']
    params = {"host": ip, "reason": "2", "cluster": cluster  }
    url = LOCAL_API['unfreeze']
    res = requests.post(url, data = json.dumps(params)).json() 
    if res['status'] == 0:
        ret = True

    return ret
    '''
 
