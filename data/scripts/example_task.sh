
LOG_DIR="/tmp/exec_logs/"
mkdir -p $LOG_DIR
EXEC_LOG="/$LOG_DIR/$$.exe.log"
ERROR_LOG="/$LOG_DIR/$$.exe.error"


ret_result(){
    is_succ=$1
    result=$2
    ret="{\"is_succ\": $is_succ, \"result\": \"$result\"}"
    echo $ret
}


action1(){
    params=$1
    previous_action_result=$2
    ret_result true " action1:  true "
}  

action2(){
    params=$1
    previous_action_result=$2
    ret_result true " action2:  true"
}  

action3(){
    params=$1
    previous_action_result=$2
    ret_result false " action3:  false "
}  


action4(){
    params=$1
    previous_action_result=$2
    ret_result true " action4:  true"
}  


