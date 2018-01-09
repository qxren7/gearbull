# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: thread_task.py
Date: 2017/06/29
"""

import Queue  
import threading  


class ThreadTask(object):
    """多线程任务，收集结果集合返回"""

    def __init__(self):
        self._result_queue = Queue.Queue()  

    def run(self, items, *args, **kwargs):
        """ 启动多线程任务 """
        threads = []
        for idx, item in enumerate(items):
            t = threading.Thread(target=self.task, args=(item,)+args, kwargs=kwargs)  
            t.daemon = True
            t.start()  
            threads.append(t)
        for t in threads:
            t.join(20)  
        results = self.collect()
        return results

    def task(self, *args, **kwargs):
        """ 虚任务方法，由继承者实现具体逻辑"""
        raise NotImplementedError('task should be implemented')

    def collect(self):
        """ 收集结果方法，继承者可实现具体逻辑来覆盖默认逻辑"""
        results = []
        while not self._result_queue.empty():  
            results.append(self._result_queue.get())  
        return results
 

class DemoTask(ThreadTask):
    """Docstring for DemoTask """

    def task(self, host):  
        """ demo task """
        result = str(host) + " result"
        self._result_queue.put((host, result)) 

    def collect(self):
        """ collect """
        results = []
        while not self._result_queue.empty():  
            results.append(str(self._result_queue.get()) + " more result")  
        return results

       
