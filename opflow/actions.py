# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: actions.py
Date: 2017/04/18 
"""

import json
from enum import Enum
from fuxi_framework.job_engine import runtime_manager
from fuxi_framework.job_engine import id_generator


class TaskTypes(Enum):
    """仲景支持的任务类型"""
    repair_common_host = "ultron_repair_common_host"
    repair_beehive_host = "ultron_repair_beehive_host"
    freeze_beehive_host = "freeze_beehive_host"
    repair_fake_dead_beehive_host = "ultron_repair_fake_dead_beehive_host"
    reinstall_beehive_host = "ultron_reinstall_beehive_host"
    init_host = "ultron_reinit_host"
    deploy_beehive_agent = "archer_deploy_beehive_agent"
    fake_operate = "fake_operate"
    mount_to_beehive_node = "bns_mount_host_to_beehive_agent_node"
    repair_alading_host = "repair_alading_host"
    reinstall_alading_host = "reinstall_alading_host"
    reinstall_galaxy_host = "reinstall_galaxy_host"

        
TASK_TYPES_ZH = {
        TaskTypes.repair_common_host: "repair_common_host",
        TaskTypes.repair_beehive_host: "Beehive机器维修",
        TaskTypes.repair_fake_dead_beehive_host: "假死机器维修",
        TaskTypes.reinstall_beehive_host: "机器重装",
        TaskTypes.init_host: "机器初始化",
        TaskTypes.deploy_beehive_agent: "部署Agent",
        TaskTypes.fake_operate: "fake_operate",
        TaskTypes.mount_to_beehive_node: "挂载节点",
        TaskTypes.repair_alading_host: "阿拉丁机器维修",
        TaskTypes.reinstall_alading_host: "阿拉丁机器重装",
        TaskTypes.reinstall_galaxy_host: "galaxy机器重装",
        TaskTypes.freeze_beehive_host: "freeze beehive 机器"
        }

def __create_action(task, index, action_declaration, timeout):
    """ alading机器维修前置hook"""
    runtime_info = {}
    runtime_info['action_id'] = id_generator.gen_action_id(task) 
    runtime_info['task_id']  = task.task_id
    runtime_info['action_content'] = json.dumps(action_declaration)
    runtime_info['seq_id']  = index
    runtime_info['timeout']  = timeout
    runtime_info['state'] = "NEW"
    action = runtime_manager.create_action(runtime_info)

       
def create_ultron_repair_beehive_host_action(task, index, action_params=None):
    """ 创建 奥创维修beehive机器action"""
    declaration ={
            "module": "zhongjing.host",
            "class": "PhysicalHost",
            "method": "repair_beehive_host",
            "params": action_params,
            }
    timeout  = 3600 * 48
    __create_action(task, index, declaration, timeout)


def create_ultron_reinstall_galaxy_host_action(task, index, action_params=None):
    """ 创建 奥创维修beehive机器action"""
    declaration ={
            "module": "zhongjing.host",
            "class": "PhysicalHost",
            "method": "reinstall_galaxy_host",
            "params": action_params,
            }
    timeout  = 3600 * 48
    __create_action(task, index, declaration, timeout)




def create_ultron_repair_fake_dead_beehive_host_action(task, index, action_params=None):
    """ 创建 奥创维修beehive机器action"""
    declaration ={
            "module": "zhongjing.host",
            "class": "PhysicalHost",
            "method": "repair_beehive_host",
            "params": action_params,
            }
    timeout  = 3600 * 12 
    __create_action(task, index, declaration, timeout)


def create_ultron_reinstall_beehive_host_action(task, index, action_params=None):
    """ 创建 奥创维修beehive机器action"""
    declaration ={
            "module": "zhongjing.host",
            "class": "PhysicalHost",
            "method": "reinstall_beehive_host",
            "params": action_params,
            }
    timeout  = 3600 * 12 
    __create_action(task, index, declaration, timeout)



def create_deploy_single_beehive_agent_action(task, index, action_params=None):
    """ 创建部署beehive agent机器action"""
    declaration ={
            "module": "zhongjing.host",
            "class": "PhysicalHost",
            "method": "deploy_single_beehive_agent",
            "params": action_params,
            }
    timeout  = action_params['timeout']
    __create_action(task, index, declaration, timeout)


def create_chown_work_action(task, index, action_params=None):
    """ 创建部署beehive agent机器action"""
    declaration ={
            "module": "zhongjing.host",
            "class": "PhysicalHost",
            "method": "chownwork",
            "params": action_params,
            }
    timeout  = action_params['timeout']
    __create_action(task, index, declaration, timeout)


def create_fake_operate_action(task, index, action_params=None):
    """ 创建空action，用于测试"""
    declaration ={
            "module": "zhongjing.host",
            "class": "PhysicalHost",
            "method": "fake_operate",
            "params": action_params,
            }
    timeout = action_params['timeout']
    __create_action(task, index, declaration, timeout)


def create_mount_to_beehive_node_action(task, index, action_params=None):
    """ 将其他产品线机器挂载到beehive节点下"""
    declaration ={
            "module": "zhongjing.host",
            "class": "PhysicalHost",
            "method": "mount_to_beehive_node",
            "params": action_params,
            }
    timeout = 300  # 5 mins
    __create_action(task, index, declaration, timeout)


def create_repair_alading_pre_hook_action(task, index, action_params=None):
    """ alading机器维修前置hook"""
    declaration ={
            "module": "zhongjing.host",
            "class": "Alading",
            "method": "pre_hook",
            "params": action_params,
            }
    timeout = 60
    __create_action(task, index, declaration, timeout)


def create_repair_alading_post_hook_action(task, index, action_params=None):
    """ alading机器维修后置hook"""
    declaration ={
            "module": "zhongjing.host",
            "class": "Alading",
            "method": "post_hook",
            "params": action_params,
            }
    timeout = 60
    __create_action(task, index, declaration, timeout)


def create_freeze_beehive_host_action(task, index, action_params=None):
    """ 将其他产品线机器挂载到beehive节点下"""
    declaration ={
            "module": "zhongjing.host",
            "class": "PhysicalHost",
            "method": "freeze",
            "params": action_params,
            }
    timeout = 600  # 1 mins
    __create_action(task, index, declaration, timeout)


TASK_ACTIONS_DICT = {
        # 重装beehive机器，并且部署beehive agent
        TaskTypes.reinstall_beehive_host: [
            create_ultron_reinstall_beehive_host_action, create_deploy_single_beehive_agent_action],

        # 重装 galaxy机器
        TaskTypes.reinstall_galaxy_host: [create_ultron_reinstall_galaxy_host_action],

        # 维修beehive机器，并且部署beehive agent
        TaskTypes.repair_beehive_host: [
            create_ultron_repair_beehive_host_action, create_deploy_single_beehive_agent_action],

        TaskTypes.repair_fake_dead_beehive_host: [
            create_ultron_repair_fake_dead_beehive_host_action, 
            create_deploy_single_beehive_agent_action],

        # 单独部署beehive agent
        TaskTypes.deploy_beehive_agent: [create_deploy_single_beehive_agent_action],

        # 测试用的 fake 操作，快速完成一个“什么都不做的action”, 用于快速调试
        TaskTypes.fake_operate: [
            create_fake_operate_action,
            create_fake_operate_action,
            create_fake_operate_action,
            ],

        # 挂载机器到beehive对应的noah节点
        TaskTypes.mount_to_beehive_node: [create_mount_to_beehive_node_action],

        # 阿拉丁机器维修由4个动作组成，前置hook、执行维修、后置hook、拉起agent
        TaskTypes.repair_alading_host: [
            create_repair_alading_pre_hook_action, 
            create_ultron_repair_beehive_host_action, 
            create_repair_alading_post_hook_action,
            create_deploy_single_beehive_agent_action,
            ],

        # 阿拉丁机器重装由4个动作组成，前置hook、执行重装、后置hook、拉起agent
        TaskTypes.reinstall_alading_host: [
            create_repair_alading_pre_hook_action, 
            create_ultron_reinstall_beehive_host_action, 
            create_repair_alading_post_hook_action,
            create_deploy_single_beehive_agent_action,
            ],

        # freeze beehive 机器
        TaskTypes.freeze_beehive_host: [create_freeze_beehive_host_action],

        }



def create_actions_for_task(task_type, task, action_params):
    """ create_actions_for_task """
    action_methods = TASK_ACTIONS_DICT[task_type]
    for index, create_action in enumerate(action_methods):
        create_action(task, index, action_params)
 
