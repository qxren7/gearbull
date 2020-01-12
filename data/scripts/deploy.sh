
LOG_DIR="/tmp/exec_logs/"
mkdir -p $LOG_DIR
EXEC_LOG="/$LOG_DIR/$$.exe.log"
ERROR_LOG="/$LOG_DIR/$$.exe.error"


SSH="ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=no -o ConnectionAttempts=2 -o ConnectTimeout=2 "
SCP="scp -o StrictHostKeyChecking=no -o PasswordAuthentication=no -o ConnectionAttempts=2 -o ConnectTimeout=2 "

ret_result(){
    is_succ=$1
    result=$2
    ret="{\"is_succ\": $is_succ, \"result\": \"$result\"}"
    echo $ret
}


check_env(){
    params=$1
    previous_action_result=$2
    #echo "params=$params, previous_action_result=$previous_action_result"
    ret_result true " check_env resut:  true "
    #ret_result false " check_env resut:  false "
}  

set_env(){
    params=$1
    previous_action_result=$2
    #echo "params=$params, previous_action_result=$previous_action_result"
    ret_result true " set env resut:  true"
}  

deploy_service(){
    params=$1
    previous_action_result=$2
    read host name  version product_path deploy_path <<< $params
    echo "deploy_service.sh: params='$host $name, $version, $product_path, $deploy_path', previous_action_result=$previous_action_result" >> $EXEC_LOG
    $SSH $host "mkdir -p $deploy_path  "  2>> $ERROR_LOG   1>> $EXEC_LOG
    $SCP $product_path  $host:$deploy_path   2>> $ERROR_LOG   1>> $EXEC_LOG 
    $SSH $host "cd $deploy_path && tar zxvf *tar.gz  ; echo "$name: $version" > version.txt"  2>> $ERROR_LOG   1>> $EXEC_LOG 
    $SSH $host "cd  $deploy_path && date >> deploy.log  " 
    ret_result true " deploy_service.sh:  deploy $name with version:$version SUCCFULL."
}  

start_service(){
    params=$1
    previous_action_result=$2
    #echo "params=$params, previous_action_result=$previous_action_result"
    ret_result true " start_service.sh resut:  true"
}

check_service(){
    params=$1
    previous_action_result=$2
    #echo "params=$params, previous_action_result=$previous_action_result"
    ret_result true " check_service.sh:  true"
    #ret_result false " check_service.sh:  false "
}  

notify(){
    params=$1
    previous_action_result=$2
    #echo "params=$params, previous_action_result=$previous_action_result"
    ret_result true " set notify :  true"
}  
