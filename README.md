dx-streaming-upload
=========

[![Build Status](https://travis-ci.org/dnanexus-rnd/dx-streaming-upload.svg?branch=master)](https://travis-ci.org/dnanexus-rnd/dx-streaming-upload)

The dx-streaming-upload Ansible role packages the streaming upload module for increamentally uploading a RUN directory from an Illumina sequencer onto the DNAnexus platform.

Instruments that this module support include the Illumina MiSeq, NextSeq, HiSeq-2500, HiSeq-4000 and HiSeq-X.

Role Variables
--------------
- `mode`: `{deploy, debug}` In the *deploy* mode, monitoring cron job is triggered every minute; in *deploy mode*, monitoring cron job is triggered every hour.
- `upload_project`: ID of the DNAnexus project that the RUN folders should be uploaded to. The ID is of the form `project-BpyQyjj0Y7V0Gbg7g52Pqf8q`
- `dx_token`: API token for the DNAnexus user to be used for data upload. The API token should give minimally UPLOAD access to the `{{ upload project }}`, or CONTRIBUTE access if `downstream_applet` is specified. Instructions for generating a API token can be found at [DNAnexus wiki](https://wiki.dnanexus.com/UI/API-Tokens). This value is overriden by `dx_user_token` in `monitored_users`.
- `monitored_users`: This is a list of objects, each representing a remote user, with its set of incremental upload parameters. For each `monitored_user`, the following values are accepted
  - `username`: (Required) username of the remote user
  - `monitored_directories`: (Required)  Path to the local directory that should be monitored for RUN folders. Multiple directories can be listed. Suppose that the folder `20160101_M000001_0001_000000000-ABCDE` is the RUN directory, then the folder structure assumed is `{{monitored_dir}}/20160101_M000001_0001_000000000-ABCDE`
  - `local_tar_directory`: (Optional) Path to a local folder where tarballs of RUN directory is temporarily stored. User specified in `username` need to have **WRITE** access to this folder. There should be sufficient disk space to accomodate a RUN directory in this location. This overwrites the default found in `templates/monitor_run_config.template`.
  - `local_log_directory`: (Optional) Path to a local folder where logs of streaming upload is stored, persistently. User specified in `username` need to have **WRITE** access to this folder. User should not manually manipulate files found in this folder, as the streaming upload code make assumptions that the files in this folder are not manually manipulated. This overwites the default found in `templates/monitor_run_config.template`.
  - `applet`: (Optional) ID of a DNAnexus applet to be triggered after successful upload of the RUN directory. This applet's I/O contract should accept a DNAnexus record with the input name `upload_sentinel_record` as the input name. This applet will be triggered with only the `upload_sentinel_record` input. Future work will allow command line customization of other input parameters. Note that if the specified applet is not located, the upload process will not commence.
  - `script`: (Optional) File path to an executable script to be triggered after successful upload for the RUN directory. The script must be executable by the user specified by `username`. The script will be triggered in the with a single command line argument, correpsonding to the filepath of the RUN directory (see section *Example Script*). If the file path to the script given does not point to a file, or if the file is not executable by the user, then the upload process will not commence.
  - `dx_user_token`: (Optional) API token associated with the specific `monitored_user`. This overrides the value `dx_token`. If `dx_user_token` is not specified, defaults to `dx_token`.

**Note** DNAnexus login is persistent and the login environment is stored on disk in the the Ansible user's home directory. User of this playbook responsibility to make sure that every Ansible user (`monitored_user`) with a streaming upload job assigned has been logged into DNAnexus by either specifying a `dx_token` or `dx_user_token`.

Dependencies
------------
Python 2.7 is needed. This program is not compatible with Python 3.X.

Minimal Ansible version: 2.0.

This program is intended for Ubuntu 14.04 (Trusty) and has been tested on the 15.10 (Wily) release. Most features should work on a Ubuntu 12.04 (Precise) system, but this has not been tested to date.


Requirements
------------
Users of this module needs a DNAnexus account and its accompanying authentication. To register for a trial account, visit the [DNAnexus homepage](https://dnanexus.com).

More information and tutorials about the DNAnexus platform can be found at the [DNAnexus wiki page](https://wiki.dnanexus.com).

The `remote-user` that the role is run against must possess **READ** access to `monitored_folder` and **WRITE** access to disk for logging and temporary storage of tar files. These are typically stored under the `remote-user's` home directory, and is specified in the file `monitor_run_config.template` or as given explicitly by the variables `local_tar_directory` and `local_log_directory`.

The machine that this role is deployed to should have at least 500Mb of free RAM available for allocation by the upload module during the time of upload.

Example Playbook
----------------
`dx-upload-play.yml`
```YAML
---
- hosts: localhost
  vars:
    monitored_users:
      - username: travis
        applet: applet-Bq2Kkgj08FqbjV3J8xJ0K3gG
        local_tar_directory: ~/new_location/upload/TMP
        local_log_directory: ~/another_location/upload/LOG
        monitored_directories:
          - ~/runs
      - username: root
        monitored_directories:
          - ~/home/root/runs
    mode: debug
    upload_project: project-BpyQyjj0Y7V0Gbg7g52Pqf8q

  roles:
    - dx-streaming-upload

```

**Note**: For security reasons, you should refrain from storing the DNAnexus authentication token in a playbook that is open-access. One might trigger the playbook on the command line with extra-vars to supply the necessary authentication token, or store them in a closed-source yaml variable file.

ie. `ansible-playbook dx-upload-play.yml -i inventory --extra-vars "dx_token=<SECRET_TOKEN>"`

We recommend that the token given is limited in scope to the upload project, and has no higher than **CONTRIBUTE** privileges.


Example Script
--------------
The following is an example script that writes a flat file to the RUN directory once a RUN directory has been successfully streamed.

``
#!/bin/bash

set -e -x -o pipefail

rundir="$1"
echo "Completed streaming run directory: $rundir" > "$rundir/COMPLETE.txt"
```

Actions performed by Role
-------------------------
The dx-streaming-upload role perform, broadly, the following:

1. Installs the DNAnexus tools [dx-toolkit](https://wiki.dnanexus.com/Downloads#DNAnexus-Platform-SDK) and [upload agent](https://wiki.dnanexus.com/Downloads#Upload-Agent) on the remote machine.
2. Set up a CRON job that monitors a given directory for RUN directories periodically, and streams the RUN directory into a DNAnexus project, triggering an app(let) upon successful upload of the directory and a local script (when specified by user)

Files generated
----------------
We use a hypothetical example of a local RUN folder named `20160101_M000001_0001_000000000-ABCDE`, that was placed into the `monitored_directory`, after the `dx-streaming-upload` role has been set up.

**Local Files Generated**
```
path/to/LOG/directory
(specified in monitor_run_config.template file)
- 20160101_M000001_0001_000000000-ABCDE.lane.all.log

path/to/TMP/directory
(specified in monitor_run_config.template file)
- no persistent files (tar files stored transiently, deleted upon successful upload to DNAnexus)
```

**Files Streamed to DNAnexus project**
```
project
   └───20160101_M000001_0001_000000000-ABCDE
       │───runs
       │    │  RunInfo.xml
       │    │  SampleSheet.csv
       │    │  run.20160101_M000001_0001_000000000-ABCDE.lane.all.log
       │    │  run.20160101_M000001_0001_000000000-ABCDE.lane.all.upload_sentinel
       │    │  run.20160101_M000001_0001_000000000-ABCDE.lane.all_000.tar.gz
       │    │  run.20160101_M000001_0001_000000000-ABCDE.lane.all_001.tar.gz
       │    │  ...
       │
       └───reads
            │  output files from downstream applet (e.g. demx)
            │  ...
```

The `reads` folder (and subfolders) will only be created if `downstream_applet` is specified.
`RunInfo.xml` and `SampleSheet.csv` will only be upladed if they can be located within the root of the local RUN directory.

Logging, Notification and Error Handling
------------------------------------------
**Uploading**

A log of the CRON command (executed with `bash -e`) is written to the user's home folder `~/dx-stream_cron.log` and can be used to check the top level command triggered.

The verbose log of the upload process (generated by the top-level `monitor_runs.py`) is written to the user's home folder `~/monitor.log`.

These logs can be used to diagnose failures of upload from the local machine to DNAnexus.

**Downstream applet**

The downstream applet will be run in the project that the RUN directory is uploaded to (as specified in role variable `upload_project`). Users can log in to their DNAnexus account (corresponding to the `dx_token` or `dx_user_token`) and navigate to the upload project to monitor the progress of the applet triggered. Typically, on failure of a DNAnexus job, the user will receive a notification email, which will direct the user to check the log of the failed job for further diagnosis and debugging.

License
-------

Apache

Author Information
------------------

DNAnexus (email: support@dnanexus.com)
