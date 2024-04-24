# Avoid long running upload delay and fail out to subsequent invocations
FROM dsu:latest

RUN git clone -b "XVG-8595-avoid-5-hours-delay" https://github.com/dnanexus-rnd/dx-streaming-upload.git
RUN mkdir -p /opt/data
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180732_inprogress_novaseq/output.dat bs=100MB count=20
COPY ./playbooks/XVG-8595.yml /opt/playbook.yml
COPY ./run.sh .
ENTRYPOINT ["bash", "/opt/run.sh"]