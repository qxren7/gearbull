import os

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT_DIR = "%s/../" % CUR_DIR
DATA_DIR = "%s/%s" % (PROJECT_ROOT_DIR, "data")
PLUGINS_DIR = "%s/%s" % (DATA_DIR, "plugins")
SCRIPTS_DIR = "%s/%s" % (DATA_DIR, "scripts")

# on_true on_false 表示任务分支子树，如果不设置，表示没有分支

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


etasks_trees = {
    "trees": {
        "tree1": {
            "nodes": ["action1", "action2"],
        },
    },
    "name": "etasks",
    "src_path": PLUGINS_DIR,
    "module": "etasks",
    "class": "ExampleTask",
}




shell_example_trees = {
    "trees": {
        "tree1": {
            "nodes": ["action1", "action2", "action4"],
        },
    },
    "name": "shell_example",
    "src_path": SCRIPTS_DIR,
    "module": "example_task.sh",
    "class": "None",
    "exe_type": "Bash",
}




test_clause_trees = {
    "trees": {
        "tree1": {
            "nodes": ["a1", "a2 | b1 | b2 ", "a3 & b2 & b3 & b4 "],
            "on_true": "tree2",
            "on_false": "tree3"
        },
        "tree2": {
            "nodes": ["a6", "a7"]
        },
        "tree3": {
            "nodes": ["a4", "a5"],
            "on_true": "tree2",
            "on_false": "tree4"
        },
        "tree4": {
            "nodes": ["a8", "a9"]
        },
    },
    "name": "test_clause",
    "src_path": PLUGINS_DIR,
    "module": "tasks",
    "class": "TestTask",
}

test_fail_trees = {
    "trees": {
        "tree1": {
            "nodes": ["fail"],
        },
    },
    "name": "test_fail",
    "src_path": PLUGINS_DIR,
    "module": "tasks",
    "class": "TestTask",
}

test_clause_1_trees = {
    "trees": {
        "tree1": {
            "nodes": ["a1", "a3"],
            "on_true": "tree2",
            "on_false": "tree3"
        },
        "tree2": {
            "nodes": ["a6"]
        },
        "tree3": {
            "nodes": ["a7"]
        },
    },
    "name": "test_clause_1",
    "src_path": PLUGINS_DIR,
    "module": "tasks",
    "class": "TestTask",
}

test_clause_2_trees = {
    "trees": {
        "tree1": {
            "nodes": ["a1", "a3", "a5"],
            "on_true": "tree2",
            "on_false": "tree3"
        },
        "tree2": {
            "nodes": ["a6"]
        },
        "tree3": {
            "nodes": ["a7"]
        },
    },
    "name": "test_clause_2",
    "src_path": PLUGINS_DIR,
    "module": "tasks",
    "class": "TestTask",
}

shell_deploy_trees = {
    "trees": {
        "tree1": {
            "nodes":
            ["check_env", "deploy_service", "start_service", "check_service"],
            "on_true":
            "tree3",
            "on_false":
            "tree2"
        },
        "tree2": {
            "nodes": ["set_env", "notify"],
        },
        "tree3": {
            "nodes": ["notify"]
        },
    },
    "name": "shell_deploy",
    "src_path": SCRIPTS_DIR,
    "module": "deploy.sh",
    "class": "None",
    "exe_type": "Bash",
}

longrun_task_trees = {
    "trees": {
        "tree1": {
            "nodes": ["long_run_action"],
        },
    },
    "name": "longrun_task",
    "src_path": PLUGINS_DIR,
    "module": "tasks",
    "class": "TestTask",
}

real_do_work_action_trees = {
    "trees": {
        "tree1": {
            "nodes": ["real_do_work_action"],
        },
    },
    "name": "real_do_work_action",
    "src_path": PLUGINS_DIR,
    "module": "tasks",
    "class": "TestTask",
}



trees_dict = {
    "test_clause": test_clause_trees,
    "test_fail": test_fail_trees,
    "test_clause_1_trees": test_clause_1_trees,
    "test_clause_2_trees": test_clause_2_trees,
    "shell_deploy": shell_deploy_trees,
    "shell_example": shell_example_trees,
    "longrun_task": longrun_task_trees,
    "real_do_work_action": real_do_work_action_trees,
    "example_task": example_task_trees,
    "etasks": etasks_trees,
}


