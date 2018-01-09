#!/bin/bash

ps aux | grep job_scheduler | grep -v grep | awk '{print $2}' | xargs -i kill -9 {}
ps aux | grep job_monitor | grep -v grep | awk '{print $2}' | xargs -i kill -9 {}

python2.7 job_scheduler.py > ../log/scheduler_daemon.log 2>&1 &
python2.7 job_monitor.py > ../log/monitor_daemon.log 2>&1 &
