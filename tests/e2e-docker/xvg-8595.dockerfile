# Avoid long running upload delay and gracefully exit and let the subsequent cron invocation handles
# This docker file create a 3 8MB files and expect the container to 
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

RUN git clone -b "XVG-8595-avoid-5-hours-delay" https://github.com/dnanexus-rnd/dx-streaming-upload.git
RUN mkdir -p /opt/data
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180732_inprogress_novaseq/output1.dat bs=8MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180732_inprogress_novaseq/output2.dat bs=8MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180732_inprogress_novaseq/output3.dat bs=8MB count=1
COPY ./playbooks/XVG-8595.yml /opt/playbook.yml
COPY ./run.sh .
ENTRYPOINT ["bash", "/opt/run.sh"]