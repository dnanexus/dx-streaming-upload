#!/bin/bash
# soft restart (see the assumption line below)
# goal: restart streaming service
# assumption: no re-configuations of the streaming upload
#
# Author: DNAneuxus ; Support: support@dnanexus.com
set +x -o pipefail
echo -e "\n"
# Stop the CRON service
service cron stop > /dev/null 2> /dev/null
echo "Step 1 Stop CRON Service ...COMPLETED"

# Remove the Cron Lock File
rm /var/lock/dnanexus* || true
echo "Step 2 Remove the Cron Lock File ...COMPLETED"

# Identify the User Account
wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
chmod a+x /usr/local/bin/yq
export username=$(yq '.[].vars.[].[].username' /opt/dx-upload-play.yml)
echo "Step 3 Identify the User Account ...COMPLETED"

# Remove the Logs
rm /home/$username/dx-stream_cron* || true
rm /home/$username/monitor_*  || true
rm -fr /home/$username/dnanexus/upload || true
echo "Step 4 Remove the Logs ...COMPLETED"

# List and Kill All Running Sessions of the streaming upload
session_array=()
readarray session_array < <(ps -o sess --no-headers -U $username)
for i in ${session_array[@]}; do pkill -9 -s $i ; done
echo "Step 5 List and Kill All Running Sessions of the streaming upload ...COMPLETED"

# Restart the CRON Service
service cron start > /dev/null 2> /dev/null
echo "Step 6 Restart the CRON Service ...COMPLETED"
echo -e "\n"
echo "The Streaming Upload tool has been restarted. Expect the monitor log file to appear under /home/$username/ shortly."
echo -e "\n"
