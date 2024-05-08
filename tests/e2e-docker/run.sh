#!/bin/bash
service cron start
nohup ansible-playbook /opt/playbook.yml "$@" &

while true
do
    # Add your tasks or commands here that you want to run repeatedly
    echo "Avoid Container to gracefully exit"
    
    # Pause execution for 5 seconds
    sleep 5
done