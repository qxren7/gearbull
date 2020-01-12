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


class TestTask(object):
    def a1(self, args):
        return (True, "a1 ok")

    def a2(self, args):
        for i in range(1, 10):
            msg = "do task %s " % i
            task_logger.info(msg)
            #time.sleep(6)
        return (True, "a2 ok")

    def a3(self, args):
        return (True, "a3 ok")

    def a4(self, args):
        return (True, "a4 ok")

    def a5(self, args):
        return (False, "error")
        return (True, "a5 ok")

    def a6(self, args):
        return (True, "a6 ok")

    def a7(self, args):
        return (True, "a7 ok")

    def a8(self, args):
        return (True, "a8 ok")

    def a9(self, args):
        return (True, "a9 ok")

    def b1(self, args):
        return (False, "b1 not ok, fail")

    def b2(self, args):
        return (True, "b2 ok")

    def b3(self, args):
        return (True, "b3 ok")

    def b4(self, args):
        return (True, "b4 ok")

    def fail(self, args):
        return (False, "fail action, error")

    def long_run_action(self, args):
        time.sleep(30)
        return (True, "long run action, run 30s")

    def real_do_work_action(self, args):
        cmd = 'echo "test" > /tmp/test_real_do_work_action.log'
        (status, output) = subprocess.getstatusoutput(cmd)
        return (True, "execute cmd=[%s]" % cmd)
