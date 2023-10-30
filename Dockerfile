FROM python:3.9-slim-bullseye

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install dxpy
RUN pip install --upgrade pip && pip install pyyaml && pip install dxpy

# install and setup ua(UploadAgent)
RUN apt update && apt install -y curl && curl -s -L https://dnanexus-sdk.s3.amazonaws.com/dnanexus-upload-agent-1.5.33-linux.tar.gz | tar zxf - -O > /root/ua && chmod +x /root/ua
ENV PATH=/root:$PATH

# Install dx-streaming-upload
COPY files /opt/dnanexus/scripts

CMD ["python", "/opt/dnanexus/scripts/monitor_runs.py", "-c", "/root/dnanexus/config/monitor_runs.config", "-v"]