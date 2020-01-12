GearBull:  齿轮公牛

Featres:

1、树形任务结构，通过json编排任务，支持任务分支，与、或、非关系

2、精细的执行控制，并发控制、批量执行、滚动执行、暂停点、恢复执行、失败比例、重做…

3、直接支持 python、shell作为业务逻辑语言，适用于部署、运维任务操作、环境管理、故障自愈等常见运维场景

4、失败任务Failover、任务可重入、全局任务控制

5、支持Restful API



如何安装？

1、安装 python36、 pip3

2、将GearBull 项目 clone 到本地, 假设clone到 /home/work/gearbull

3、安装依赖,  cd /home/work/gearbull &&  pip3  install -r requirements.txt

4、初始化数据库 python3  manage.py migrate

5、修改 supervisor/supervisord.conf里  [program:scheduler]、[program:monitor]、[program:webserver] 的 directory 参数，默认为 /home/work/gearbull， 类似这样：

[program:scheduler]

command=python3  WorkFlow/scheduler.py 

directory=/home/work/gearbull              

...


[program:monitor]

command=python3  WorkFlow/monitor.py 

directory=/home/work/gearbull              

...


[program:webserver]

command=python3 manage.py runserver 127.0.0.1:8088 

directory=/home/work/gearbull  



6、启动 supervisord,   supervisord -c supervisor/supervisord.conf 

7、/usr/local/python36/bin/supervisorctl -c supervisor/supervisord.conf  status 查看状态

supervisorctl -c supervisor/supervisord.conf  status

monitor                          RUNNING   pid 4143, uptime 0:00:06

scheduler                        RUNNING   pid 4144, uptime 0:00:06

webserver                        RUNNING   pid 4145, uptime 0:00:06





如何使用？
0. 查看当前有哪些任务工作流
curl 'http://127.0.0.1:8088/workflow/api/flows/' 

2. 查看工作流定义
curl 'http://127.0.0.1:8088/workflow/api/flow/?name=example_task'  

1. 创建job , 其中 targets是要操作的对象，task_type是flow 类型
curl -H 'Content-type: application/json' -X POST -d '{"targets":["h1", "h2"], "task_type": "test_clause"}' http://localhost:8088/workflow/api/create_job/

2. 查看job列表
curl 'http://127.0.0.1:8088/workflow/jobs/' 

3. 查看指定job详情
curl 'http://127.0.0.1:8088/workflow/jobs/1/' 

4. 同理, task, action
curl 'http://127.0.0.1:8088/workflow/tasks/'  
curl 'http://127.0.0.1:8088/workflow/tasks/16/'  
curl 'http://127.0.0.1:8088/workflow/actions/'  
curl 'http://127.0.0.1:8088/workflow/actions/89/'  

5. 查看任务工作流关系
curl 'http://127.0.0.1:8088/workflow/api/show_flow/?job_id=1'   

6.定义自己的工作流
     a、cd /home/work/gearbull 
    b、在 data/plugins 下，cp example_tasks.py  your_tasks.py 

    c、编辑 conf/task_trees.py, 增加 trees定义:

example_task_trees = {

    "trees": {

        "tree1": {

            "nodes": ["action1", "action2", "action3"],

        },

    },

    "name": "example_tasks",

    "src_path": PLUGINS_DIR,

    "module": "example_tasks",

    "class": "ExampleTask",

}


    d、在trees_dict 加上新的tree定义: "example_task": example_task_trees,

   e、重启 server: supervisorctl -c supervisor/supervisord.conf  restart all
