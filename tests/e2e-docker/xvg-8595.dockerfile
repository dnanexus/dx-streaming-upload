# Avoid long running upload delay and gracefully exit and let the subsequent cron invocation handles
# This docker file create a number of 8MB files and expect the container to 
# take more than 60 seconds to upload the tar file(s) during the loop.
# In each iteration of dx_sync_directory, we have a condition check to replicate this behavior on production:
# ---- (provided by Davis Feng)
#   cron wakes up at 12:00
#   12:05
#   We find 10 tar files
#   1st tar takes 15 mins to upload
#   12:20
#   2nd tar takes 15 mins to upload
#   12:35
#   3rd tar takes 15 mins to upload
#   12:50
#   If hour(12:50 + 15mins) > hour(12:50)
#   exit
#   4th tar take 15 mins to upload
#   exit
# ---- 
#
# => In dev mode, if the anticipated time elapse exceeds 60 seconds, 
# log out WARNING message and gracefully exit the script
FROM dsu:latest

COPY .build-context ./dx-streaming-upload
# Create file for run-folder-a/180733_inprogress_novaseq
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180731_complete_novaseq/output1.dat bs=12MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180731_complete_novaseq/output2.dat bs=12MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180731_complete_novaseq/output3.dat bs=8MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180731_complete_novaseq/output4.dat bs=6MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180731_complete_novaseq/output5.dat bs=14MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180731_complete_novaseq/output6.dat bs=15MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180731_complete_novaseq/output7.dat bs=16MB count=1
# Create file for run-folder-a/180734_inprogress_novaseq
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180733_complete_novaseq/output1.dat bs=12MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180733_complete_novaseq/output2.dat bs=12MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180733_complete_novaseq/output3.dat bs=12MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180733_complete_novaseq/output4.dat bs=12MB count=1
# Create file for run-folder-a/180735_inprogress_novaseq
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180734_complete_novaseq/output1.dat bs=12MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180734_complete_novaseq/output2.dat bs=12MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180734_complete_novaseq/output3.dat bs=12MB count=1

RUN rm -rf /opt/dx-streaming-upload/tests/run-folder-a/180732_inprogress_novaseq

COPY ./playbooks/XVG-8595.yml /opt/playbook.yml
ENTRYPOINT ["bash", "/opt/run.sh"]