## scheduler messages
cur_queue_size = "scheduler one cycle over, current job queue size: %s, working job queue size %s, current task queue size: %s, working task queue size: %s "
schedule_exception = "scheduler exception, error=[%s]"
still_running = "job=[%s] there is still running tasks, ids=[%s]"
get_task = "task work process=[%s] get task to work, task_id=[%s]"

## analyzer messages
plan_done = "job_id=[%s], generate tasks plan done, update state=[%s]"

update_job_error = "job_id=[%s], update job state error in analyze, error=[%s]"

url_res = "url=[%s], response=[%s]"

duplicate_host = "host=[%s] is duplicate, remove"

split_groups = "__split_hosts_into_groups, job_params=[%s], host_infos_list=[%s], host_infos_groups=[%s]"

## executor messages

executor_start = "start QueueExecutor, working for job=[%s]"

worker_start = "start worker=[%s], working for job=[%s]"

stage_finish = "stage=[%s] execute finish, pause job=[%s], wait for user resume."

executor_exception = "QueueExecutor exception, error=[%s]"

worker_stop = "stop worker=[%s], working for job=[%s]"

executor_finish = "QueueExecutor finish, working for job=[%s]"

worker_paused = "worker=[%s], job=[%s],job is paused, wait."

empty_queue = "worker=[%s], job=[%s],empty queue, wait."

worker_end = "worker:%s  end"

reentry_job = "this task=[%s] has already start, reentry this task, job=[%s]"

## task messages
task_start = "get task and exec task, task_id=[%s]"

task_fail = "exec task failed, worker=[%s], job=[%s] error=[%s]"

task_ignore = "task=[%s] has started, ignore it."

task_not_finish = "task thread not finish, wait, task_id=[%s]"

task_finish = "task thread finish, quit, task_id=[%s]"

task_fail2 = "exec task failed, task_id=[%s] error=[%s]"

## actions messages
action_succ = (
    "exec action succ, task_id=[%s], action=[%s], entity_name=[%s], result=[%s]"
)

action_skip = "exec action not succ, but can skip, task_id=[%s], action=[%s], entity_name=[%s], result=[%s]"

action_fail = "exec action=[%s] fail, task=[%s] break off now, action=[%s], entity_name=[%s], result=[%s]"

## models messages
action_detail = "iterate_execute: action_tree=[%s], self._true_clause=[%s], self._false_clause=[%s], state=[%s]"

miss_params = "missing params, error=[%s]"

save_job_error = "save job runtime info error, error=[%s], job_info=[%s]"

create_job_succ = "create job succ, job=[%s]"

save_task_error = "save task runtime info error, error=[%s], task_info=[%s]"

update_task_info = "update task info, task_id=[%s], info=[%s]"

save_action_error = "save action runtime info error, error=[%s]"

action_state_change = "action state change, exec post action, action=[%s]"

thresholds_exception = "today_thresholds num greater than 1, num=[%s]"

no_check_list = "there is no check list templates for task_type=[%s]."

try_execute_method = (
    "try execute_method %s times, method=[%s], params=[%s], is_succ=[%s], result=[%s]"
)

try_execute_fail = "try execute_method %s times, failed, method=[%s], params=[%s]"

execute_actions = "exec actions, job_id=[%s], task_id=[%s], actions_id=[%s], python path=[%s], action_content=[%s]"

method_info = "method name: %s, params: %s"

not_reentry = "job=[%s] is not idempotency, action=[%s] is executed, cannot reexcute."

reentry = "job=[%s] is idempotency, action=[%s] is executed, return result base on state=[%s]."

method_result = "action=[%s], method name: %s, params: %s"
