# Prerequisites
- Docker must be installed
- Docker disk must have at least 150gb size
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
    - Base image must be `dsu:latest`
    - Only 1 entrypoint specified at the end of the dockerfile as `ENTRYPOINT ["bash", "/opt/run.sh"]` consistently
    - The test playbook file must be copied to `/opt/playbook.yml`

    Example:
    ```dockerfile
    FROM dsu:latest

    RUN git clone -b "XVG-8595-avoid-5-hours-delay" https://github.com/dnanexus-rnd/dx-streaming-upload.git
    RUN mkdir -p /opt/data
    RUN dd if=/dev/zero of=/opt/dx-streaming-upload/tests/run-folder-a/180732_inprogress_novaseq/output.dat bs=100MB count=20
    COPY ./playbooks/XVG-8595.yml /opt/playbook.yml
    COPY ./run.sh .

    ENTRYPOINT ["bash", "/opt/run.sh"]
    ```
3. [Build and Run the image](#how-to-build-and-run-e2e-docker)