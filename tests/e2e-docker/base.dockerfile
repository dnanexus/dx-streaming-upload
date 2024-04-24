FROM ubuntu:20.04

USER root

RUN apt update  
RUN apt-get update && apt-get clean
RUN apt install less -y && apt install htop -y && apt install jq -y
RUN apt-get install -y python3-pip python3-dev cron
RUN apt-get remove --purge ansible

# We have to run the below command before installing software-properties-common because it could be stuck at Region Selection
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata
RUN apt-get install software-properties-common -y

RUN apt-add-repository ppa:ansible/ansible -y
RUN apt-get install ansible git nano sudo -y

WORKDIR /opt
