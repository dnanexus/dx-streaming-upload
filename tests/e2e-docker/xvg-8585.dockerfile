# Requirements: 
#   When a completed run folder is deleted from DNAnexus platform, dx-streaming-upload will not reprocess the local existing Run-folder.
# ----
# Idea: Mark this information into the log file for tracking purpose
# ----
# This test include further manual action(s) to reproduce the behavior of the Requirements correctly
# 1. Trigger the test
# 2. Periodically check on the platform to see if any run folder has no files left to be tarred.
# 3. After finding out one, run a command to inject the termination file to the run folder
#    ```bash
#       docker exec -i <container-id> /bin/bash -c 'echo "hello" > /path/to/file.xyz'
#    ``` 
# 4. Wait for the dx record of the run folder to close
# 5. Manually delete the run folder from the platform
# 6. Wait for 2-5 min to see if subsequent invocations reupload the run folder or NOT.
# 7. To further verify it, lets do:
#       Step 1: Exec to the container
#           ```bash
#               docker exec -it <container-id> bash
#           ```
#       Step 2: Delete crontab by doing:
#           ```bash
#               crontab -r
#           ```
#       Step 3: Retrigger the playbook
#           ```bash
#               ansible-playbook /opt/playbook.yml
#           ```
# 8. Wait for a while (~5mins) and comeback to check on the platform whether the run folder will be reuploaded for not.

FROM dsu:latest

COPY .build-context ./dx-streaming-upload

RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180731_complete_novaseq/output1.dat bs=12MB count=1

RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180733_complete_novaseq/output1.dat bs=12MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180733_complete_novaseq/output2.dat bs=12MB count=1

RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180734_complete_novaseq/output1.dat bs=12MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180734_complete_novaseq/output2.dat bs=12MB count=1
RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180734_complete_novaseq/output3.dat bs=12MB count=1

RUN rm -rf /opt/dx-streaming-upload/tests/run-folder-a/180732_inprogress_novaseq

COPY ./playbooks/XVG-8585.yml /opt/playbook.yml
ENTRYPOINT ["bash", "/opt/run.sh"]