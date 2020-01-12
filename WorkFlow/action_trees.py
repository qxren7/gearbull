#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import copy
import json
import datetime
import logging
import traceback
import requests

from django.db import connection

from . import global_setttings

from WorkFlow import exceptions
from WorkFlow.models import Job
from WorkFlow.models import Task
from WorkFlow.models import Action
from WorkFlow.models import ClauseTree
from WorkFlow.models import ActionTree
from WorkFlow.models import Node
from conf import task_trees

logger = global_setttings.get_logger("action_trees.log")

#TREE_NAMES = [
#    "auto_reboot_host",
#]


def create_trees(task_type, task, action_params):
    """ create_actions_for_task """

    trees_definition = task_trees.trees_dict[task_type]

    trees = {}
    for tree_name, tree_data in trees_definition["trees"].items():
        nodes = create_actions(task, tree_data["nodes"], trees_definition,
                               action_params)
        t = ClauseTree(nodes, task.id)
        trees[tree_name] = t

    for tree_name, tree_data in trees_definition["trees"].items():
        tree = trees[tree_name]
        if "on_true" in tree_data and tree_data["on_true"]:
            t = trees[tree_data["on_true"]]
            tree.on_true(t)

        if "on_false" in tree_data and tree_data["on_false"]:
            t = trees[tree_data["on_false"]]
            tree.on_false(t)

    at = ActionTree(root=trees["tree1"], trees=trees, task=task)
    at.save()


def create_actions(task, action_names, action_definition, action_params):
    nodes = []
    for index, name in enumerate(action_names):
        declaration = copy.deepcopy(action_definition)
        declaration["method"] = name
        declaration["params"] = action_params
        timeout = 3600 * 48
        action = Action.create_action(task, index, declaration, timeout)
        node = Node(name, action.id)
        nodes.append(node)

    return nodes


def bulk_create_trees(task_type, tasks_actionparams_dict):
    ###### inner method
    def _create_actions(task, action_names, action_definition, action_params,
                        tree_name, create_time):
        actions = []
        for index, method_name in enumerate(action_names):
            declaration = copy.deepcopy(action_definition)
            declaration["method"] = method_name
            declaration["params"] = action_params
            timeout = 3600 * 48

            action = Action(
                action_content=json.dumps(declaration),
                seq_id=index,
                timeout=timeout,
                state="NEW",
                task=task,
                tree_name=tree_name,
                method_name=method_name,
                create_time=create_time,
            )
            actions.append(action)

        return actions

    def _create_nodes(task, action_names, action_definition, action_params):
        nodes = []
        for index, name in enumerate(action_names):
            declaration = copy.deepcopy(action_definition)
            declaration["method"] = name
            declaration["params"] = action_params
            timeout = 3600 * 48
            action = Action.create_action(task, index, declaration, timeout)
            node = Node(name, action.id)
            nodes.append(node)

        return nodes

    ###### inner method

    trees_definition = task_trees.trees_dict[task_type]

    tasks_actions_dicts = {}
    _all_actions = []
    now = datetime.datetime.now()

    for task, action_params in tasks_actionparams_dict.items():
        for tree_name, tree_data in trees_definition["trees"].items():
            actions = _create_actions(
                task,
                tree_data["nodes"],
                trees_definition,
                action_params,
                tree_name,
                now,
            )
            _all_actions += actions

            data_item = {"actions": actions, "tree_name": tree_name}
            if task in tasks_actions_dicts:
                tasks_actions_dicts[task].append(data_item)
            else:
                tasks_actions_dicts[task] = [data_item]

    tasks_ids = tasks_actionparams_dict.keys()
    Action.objects.bulk_create(_all_actions)
    new_actions = list(
        Action.objects.filter(create_time=now, task_id__in=tasks_ids))

    tasks_actiontrees_dict = {}

    for task, action_params in tasks_actionparams_dict.items():
        trees = {}
        for data_item in tasks_actions_dicts[task]:
            action_tree_name = data_item["tree_name"]
            _actions = data_item["actions"]
            nodes = []

            for _a in _actions:
                for saved_action in new_actions:
                    if (saved_action.task_id == task.id
                            and saved_action.seq_id == _a.seq_id):
                        node = Node(saved_action.method_name, saved_action.id)
                        nodes.append(node)
                        new_actions.remove(
                            saved_action)  # 没创建一个就从 new_actions 里去掉，不然回重复创建
                        break

            t = ClauseTree(nodes, task.id)
            trees[action_tree_name] = t

        for tree_name, tree_data in trees_definition["trees"].items():
            tree = trees[tree_name]
            if "on_true" in tree_data and tree_data["on_true"]:
                t = trees[tree_data["on_true"]]
                tree.on_true(t)

            if "on_false" in tree_data and tree_data["on_false"]:
                t = trees[tree_data["on_false"]]
                tree.on_false(t)

        at = ActionTree(root=trees["tree1"], trees=trees, task=task)
        tasks_actiontrees_dict[task] = at

    action_trees = list(tasks_actiontrees_dict.values())
    ActionTree.objects.bulk_create(action_trees)
