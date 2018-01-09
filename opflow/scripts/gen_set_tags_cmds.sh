#!/bin/bash

test $# -ne 3 && echo "usage: sh ${0##*/} selector_name app_pattern exclude_pattern" && exit

selector_name="$1"
app_pattern="$2"
exclude_pattern="$3"
for idc in hangzhou nanjing  shanghai  tucheng beijing  hna  hnb
do
    mkdir -p tags
    app_file="tags/$selector_name.$idc"
    bhcli app list --cluster=$idc |egrep "$app_pattern" |egrep -v "$exclude_pattern" > $app_file
    cat $app_file |while read app
    do
        echo bhcli tag add-meta-attr --app_id=$app --tag_id=null --key='app_spec/app_attribute/selectors/service' --value=$selector_name --cluster=$idc
    done
done


