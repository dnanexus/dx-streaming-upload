#!/bin/bash
# hard restart (including re-deploying the streaming upload tool)
# goal: 
# assumption: 
#
# Author: DNAneuxus ; Support: support@dnanexus.com
set +x -o pipefail

api_token="<insert DNAnexus API token here>"

# Check if input token is provided
if [ -z "$1" ]; then
    input_token=$api_token
else
    input_token="$1"
fi

echo "Input API Token used: $input_token"

echo "Redeploying the dx streaming upload tool to /opt ..."

echo "Warning: All existing streaming upload folders under /opt will be removed."

while true; do
    read -p "Do you wish to continue? " yn
    case $yn in
        [Yy]* ) # Actions to take if user confirms
                break;;
        [Nn]* ) exit;; # Actions to take if user cancels
        * ) echo "Please answer y/yes or n/no.";;
    esac
done

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

# Redeploy dx streaming upload
rm -fr /opt/dnanexus  /opt/dnanexus-upload-agent  /opt/dx-streaming-upload 
echo "Step 6 Removing folders "/opt/dnanexus", "/opt/dnanexus-upload-agent", "dx-streaming-upload" ...COMPLETED"

cd /opt
git clone https://github.com/dnanexus/dx-streaming-upload.git
ansible-playbook ./dx-upload-play.yml --extra-vars "dx_token=$input_token"
echo "Step 7 Redeploying the streaming upload tool ...COMPLETED"

# Restart the CRON Service
service cron start > /dev/null 2> /dev/null
echo "Step 8 Restart the CRON Service ...COMPLETED"
echo -e "\n"
echo "The Streaming upload tool has been restarted. Expect the monitor log file to appear under /home/$username/ shortly."
echo -e "\n"
