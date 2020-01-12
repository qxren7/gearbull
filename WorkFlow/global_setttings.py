# -*- coding: utf-8 -*-

import os
import sys
import time
import logging
import datetime
import traceback
import subprocess
import configparser

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT_DIR = "%s/../" % CUR_DIR
LOG_DIR = "%s/%s" % (PROJECT_ROOT_DIR, "logs")
VAR_DIR = "%s/%s" % (PROJECT_ROOT_DIR, "var")
CONF_DIR = "%s/%s" % (PROJECT_ROOT_DIR, "conf")
DATA_DIR = "%s/%s" % (PROJECT_ROOT_DIR, "data")
TREES_DIR = "%s/%s" % (DATA_DIR, "action_trees")
PLUGINS_DIR = "%s/%s" % (DATA_DIR, "plugins")
SCRIPTS_DIR = "%s/%s" % (DATA_DIR, "scripts")
#MISC_DIR = "%s/%s" % (PROJECT_ROOT_DIR, "misc")
#ACTIONS_DIR = "%s/%s" % (MISC_DIR, "actions")
sys.path.append("%s/../" % CUR_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gearbull.settings")

WORKFLOW_CONF_FILE = "%s/%s" % (CONF_DIR, "workflow.conf")


def __init_dirs():
    for d in [LOG_DIR, VAR_DIR, CONF_DIR, TREES_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)


__init_dirs()


def get_option_values(self, section_name, option_name, sep=",", chars=None):
    option_str = self.get(section_name, option_name)
    return [item.strip(chars) for item in option_str.split(sep)]


setattr(configparser.ConfigParser, "get_option_values", get_option_values)

WORKFLOW_CONF = configparser.ConfigParser()
WORKFLOW_CONF.read(WORKFLOW_CONF_FILE)


def get_logger(name):
    logger = logging.getLogger(name)
    hdlr = logging.FileHandler("%s/%s" % (LOG_DIR, name))
    formatter = logging.Formatter(
        "%(asctime)s p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s"
    )
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.INFO)
    return logger


_, LOCAL_SERVER = subprocess.getstatusoutput("hostname")

def init_users():
    from django.contrib.auth.models import User
    users =  User.objects.filter(username='u1')
    if len(users) <= 0:
        User.objects.create_superuser('u1', '', 'u1')

