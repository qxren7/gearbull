# -*- coding: utf-8 -*-
import os
import re
import sys
import time
import json
import socket
import logging
import getpass
import requests
import datetime
import traceback
import subprocess

formatter = logging.Formatter(
    "%(asctime)s p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s"
)
# first file logger
pid = os.getpid()
LOG_FILENAME = "/tmp/tasks.%s.log" % pid
task_logger = logging.getLogger("task_logger")
hdlr_1 = logging.FileHandler(LOG_FILENAME)
hdlr_1.setFormatter(formatter)
task_logger.setLevel(logging.DEBUG)
task_logger.addHandler(hdlr_1)


class ExampleTask(object):
    def action1(self, args):
        return (True, "action1 ok")

    def action2(self, args):
        return (True, "action2 ok")

    def action3(self, args):
        return (True, "action3 ok")

    def action4(self, args):
        return (False, "action4 error")
