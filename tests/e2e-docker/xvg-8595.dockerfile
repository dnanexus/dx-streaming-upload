# Avoid long running upload delay and gracefully exit and let the subsequent cron invocation handles
# This docker file create a 2GB file and expect the container to consume more than 60 seconds to upload tar file(s) in 1 iteration
# IF it exceeds 60 seconds, log out WARNING message and gracefully exit the script
FROM dsu:latest

RUN git clone -b "XVG-8595-avoid-5-hours-delay" https://github.com/dnanexus-rnd/dx-streaming-upload.git
RUN mkdir -p /opt/data
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180732_inprogress_novaseq/output1.dat bs=8MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180732_inprogress_novaseq/output2.dat bs=8MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180732_inprogress_novaseq/output3.dat bs=8MB count=1
COPY ./playbooks/XVG-8595.yml /opt/playbook.yml
COPY ./run.sh .
ENTRYPOINT ["bash", "/opt/run.sh"]