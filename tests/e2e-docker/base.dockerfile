FROM ubuntu:20.04

USER root

RUN apt update  
RUN apt-get update && apt-get clean
RUN apt install less -y && apt install htop -y && apt install jq -y
RUN apt-get install -y python3-pip cron
RUN apt-get install ansible git nano sudo -y
RUN apt-get install -qq vim nano sudo

WORKDIR /opt

COPY ./viewlogs.sh .
COPY ./run.sh .
RUN echo 'alias viewlogs="bash /opt/viewlogs.sh"' >> ~/.bashrc
