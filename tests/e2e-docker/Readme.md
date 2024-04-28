# Prerequisites
- Docker must be installed
- Build base image
```bash
cd tests/e2e-docker
make base
```

# How to build and run e2e docker
1. Build your wanted image
```bash
make build name=<your docker file name>
# example
# make build name=xvg-8595
```
2. Run your docker image
```bash
make run name=<your docker file name> dx_token=<your dx token>
```
3. Access to your docker container
```bash
docker exec -it <docker-container-id> bash
```

# How to prepare your e2e test docker
1. Create your target dockerfile in `tests/e2e-docker/` and name it to your ticket number such as `xvg-xxxx.dockerfile` (must be in lowercase)
2. Your target dockerfile must follow:
    - Always place `COPY .build-context ./dx-streaming-upload` after `FROM` in order to copy the source code to the working dir
    - Base image must be `dsu:latest`
    - Only 1 entrypoint specified at the end of the dockerfile as `ENTRYPOINT ["bash", "/opt/run.sh"]` consistently
    - The test playbook file must be copied to `/opt/playbook.yml`
    Example:
    ```dockerfile
    FROM dsu:latest

    COPY .build-context ./dx-streaming-upload
    # Your custom logic
    RUN mkdir -p /opt/data
    RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180732_inprogress_novaseq/output.dat bs=100MB count=20
    COPY ./playbooks/XVG-8595.yml /opt/playbook.yml
    # ------------------
    ENTRYPOINT ["bash", "/opt/run.sh"]
    ```
3. [Build and Run the image](#how-to-build-and-run-e2e-docker)

# How to validate your test manually
## View Monitor Log File
Once you access to the container, you need to wait for the `monitor_run.py` to spawn `incremental_upload.py` processes on the `htop` dashboard. Once the processes are spawned, the file `~/monitor_run-XXXX.log` presents.

Next, you can read the log file from the very first line and still follow for the upcoming logs by running this command:

```
Usage: viewlogs PATH TEXT

View logs of monitor_runs.py in with highlight text.
To be noted, the script always highlights with case-insensitive matched strings.

Arguments:

    PATH            Local Path to Monitor Log File
                    For example, ~/monitor_run-folder-X.log

    TEXT            Highlight Text. Suggested Options:
                      - "dx_sync_directory.py"
                      - "incremental_upload.py"
                      - "monitor_run.py"
                      - "all"
                    When "all" is set, it highlights the other 3 options.
                    When another value is set, it highlights the value only.
                    NOTE: You can also use regex syntax for your highlight text.
```

For example:
```
viewlogs ~/monitor_XXXX.log all

// OR

viewlogs ~/monitor_XXXX.log dx_sync_directory.py
```



## View Upload State Log File made by the `dx_sync_directory.py`
To pretty read the json log file
```bash
# with color
jq --color-output < ~/dnanexus/upload/LOGS/run.XXXX.lane.YYYY.log | less -R

# without color
jq < ~/dnanexus/upload/LOGS/run.XXXX.lane.YYYY.log | less
```
In this command, `less -R` handles rendering the color from the stdout of `jq`

To search in `less` command, type `/<search-text>`. There will be multiple match string in the content of the file:
- To move to the next matched `<search-text>`, press `n` in the keyboard
- To move back to the previous match `<search-text>`, press `SHIFT + n` in the keyboard
- Go to first line in file, press `g` in the keyboard
- Go to last line in file, press `SHIFT + g`


# Some docker utility commands
1. To list out running containers
```bash
docker container ls
```
2. To access to the container
```bash
docker container exec -it <container-id> bash
```
3. To remove the container
```bash
docker container rm -f <container-id>
```

