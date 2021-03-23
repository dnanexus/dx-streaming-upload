dx-streaming-upload
=========

[![Build Status](https://travis-ci.org/dnanexus-rnd/dx-streaming-upload.svg?branch=master)](https://travis-ci.org/dnanexus-rnd/dx-streaming-upload)

The dx-streaming-upload Ansible role packages the streaming upload module for increamentally uploading a RUN directory from an Illumina sequencer onto the DNAnexus platform.

Instruments that this module support include the Illumina MiSeq, NextSeq, HiSeq-2500, HiSeq-4000 and HiSeq-X.

Role Variables
--------------
- `mode`: `{deploy, debug}` In the *debug* mode, monitoring cron job is triggered every minute; in *deploy mode*, monitoring cron job is triggered every hour.
- `upload_project`: ID of the DNAnexus project that the RUN folders should be uploaded to. The ID is of the form `project-BpyQyjj0Y7V0Gbg7g52Pqf8q`
- `dx_token`: API token for the DNAnexus user to be used for data upload. The API token should give minimally UPLOAD access to the `{{ upload project }}`, or CONTRIBUTE access if `downstream_applet` is specified. Instructions for generating a API token can be found on the DNAnexus documentation [Authentication Tokens](https://documentation.dnanexus.com/user/login-and-logout#generating-an-authentication-token) page. This value is overriden by `dx_user_token` in `monitored_users`.
- `monitored_users`: This is a list of objects, each representing a remote user, with its set of incremental upload parameters. For each `monitored_user`, the following values are accepted
  - `username`: (Required) username of the remote user
  - `monitored_directories`: (Required)  Path to the local directory that should be monitored for RUN folders. Multiple directories can be listed. Suppose that the folder `20160101_M000001_0001_000000000-ABCDE` is the RUN directory, then the folder structure assumed is `{{monitored_dir}}/20160101_M000001_0001_000000000-ABCDE`
  - `local_tar_directory`: (Optional) Path to a local folder where tarballs of RUN directory is temporarily stored. User specified in `username` need to have **WRITE** access to this folder. There should be sufficient disk space to accomodate a RUN directory in this location. This overwrites the default found in `templates/monitor_run_config.template`.
  - `local_log_directory`: (Optional) Path to a local folder where logs of streaming upload is stored, persistently. User specified in `username` need to have **WRITE** access to this folder. User should not manually manipulate files found in this folder, as the streaming upload code make assumptions that the files in this folder are not manually manipulated. This overwites the default found in `templates/monitor_run_config.template`.
  - `exclude_patterns`: (Optional) A list of regex patterns to exclude.  If 1 or more regex patterns are given, the files matching the pattern will be skipped (not tarred nor uploaded). The pattern will be matched against the full file path.
  - `delay_sample_sheet_upload`: (Optional) Specify whether the samplesheet for each run should be uploaded before (False) or after (True) the run data is uploaded. Useful if any manipulations are performed on the samplesheet during runtime. Default=False
  - `novaseq`: (Optional) Specify whether streaming from Novaseq instrument to determine sequencing completion. (False) RTAComplete.txt/xml file triggers sequencing completion; (True) CopyComplete.txt file triggers sequencing completion. Default=False
  - `min_size`: (Optional) The minimum size of the TAR file before it will be uploaded (in MB). Default=500
  - `max_size`: (Optional) The maximum size of the TAR file to be uploaded (in MB). Default=10000
  - `run_length`: (Optional) Expected duration of a sequencing run, corresponds to the -D paramter in incremental upload (For example, 24h). Acceptable suffix: s, m, h, d, w, M, y.
  - `n_seq_intervals`: (Optional) Number of intervals to wait for run to complete. If the sequencing run has not completed within `n_seq_intervals` * `run_length`, it will be deemed as aborted and the program will not attempt to upload it. Corresponds to the -I parameter in incremental uploiad.
  - `n_upload_threads`: (Optional) Number of upload threads used by Upload Agent. For sites with severe upload bandwidth limitations (<100kb/s), it is advised to reduce this to 1, to increase robustness of upload in face of possible network disruptions. Default=8.
  - `script`: (Optional) File path to an executable script to be triggered after successful upload for the RUN directory. The script must be executable by the user specified by `username`. The script will be triggered in the with a single command line argument, correpsonding to the filepath of the RUN directory (see section *Example Script*). **If the file path to the script given does not point to a file, or if the file is not executable by the user, then the upload process will not commence.**
  - `dx_user_token`: (Optional) API token associated with the specific `monitored_user`. This overrides the value `dx_token`. If `dx_user_token` is not specified, defaults to `dx_token`.
  - `applet`: (Optional) ID of a DNAnexus applet to be triggered after successful upload of the RUN directory. This applet's I/O contract should accept a DNAnexus record with the  name `upload_sentinel_record` as input. This applet will be triggered with only the `upload_sentinel_record` input. Additional input can be specified using the variable `downstream_input`. **Note that if the specified applet is not located, the upload process will not commence. Mutually exclusive with `workflow`. The role will raise an error and fail if both are specified.**
  - `workflow`: (Optional) ID of a DNAnexus workflow to be triggered after successful upload of the RUN directory. This workflow's I/O contract should accept a DNAnexus record with the  name `upload_sentinel_record` in the 1st stage (stage 0) of the workflow as input. Additional input can be specified using the variable `downstream_input`. **Note that if the specified workflow is not located, the upload process will not commence. Mutually exclusive with `applet`. The role will raise an error and fail if both are specified.**
  - `downstream_input`: (Optional) A JSON string, parsable as a python `dict` of `str`:``str`, where the **key** is the input_name recognized by a DNAnexus applet/workflow and the **value** is the corresponding input. For examples and detailed explanation, see section titled `Downstream analysis`. **Note that the role will raise an error and fail if this string is not JSON-parsable as a dict of the expected format**

**Note** DNAnexus login is persistent and the login environment is stored on disk in the the Ansible user's home directory. User of this playbook responsibility to make sure that every Ansible user (`monitored_user`) with a streaming upload job assigned has been logged into DNAnexus by either specifying a `dx_token` or `dx_user_token`.

Dependencies
------------
Python 2.7 is needed. This program is not compatible with Python 3.X.

Minimal Ansible version: 2.0.

This program is intended for Ubuntu 14.04 (Trusty) and has been tested on the 15.10 (Wily) release. Most features should work on a Ubuntu 12.04 (Precise) system, but this has not been tested to date.


Requirements
------------
Users of this module needs a DNAnexus account and its accompanying authentication. To register for a trial account, visit the [DNAnexus homepage](https://dnanexus.com).

More information and tutorials about the DNAnexus platform can be found in the [DNAnexus documentation](https://documentation.dnanexus.com/).

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
        local_tar_directory: ~/new_location/upload/TMP
        local_log_directory: ~/another_location/upload/LOG
        exclude_patterns: Analysis
        monitored_directories:
          - ~/runs
        applet: applet-Bq2Kkgj08FqbjV3J8xJ0K3gG
        downstream_input: '{"sequencing_center": "CENTER_A"}'
        min_size: 250
        max_size: 1000
        novaseq: True
      - username: root
        monitored_directories:
          - ~/home/root/runs
        workflow: workflow-BvFz31j0Y7V5QPf09x9y91pF
        downstream_input: '{"0.sequencing_center: "CENTER_A"}'
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

Recall that the script will be triggered with a single command line parameter, where `$1` is the path to the local RUN directory  that has been successfully streamed to DNAnexus.

```
#!/bin/bash

set -e -x -o pipefail

rundir="$1"
echo "Completed streaming run directory: $rundir" > "$rundir/COMPLETE.txt"
```

Actions performed by Role
-------------------------
The dx-streaming-upload role perform, broadly, the following:

1. Installs the DNAnexus tools [dx-toolkit](https://documentation.dnanexus.com/downloads) and [upload agent](https://documentation.dnanexus.com/downloads#upload-agent) on the remote machine.
2. Set up a CRON job that monitors a given directory for RUN directories periodically, and streams the RUN directory into a DNAnexus project, triggering an app(let)/workflow upon successful upload of the directory and a local script (when specified by user)

Downstream analysis
-------------------
The dx-streaming-upload role can optionally trigger a DNAnexus applet/workflow upon completion of incremental upload. The desired DNAnexus applet or workflow can be specified (at a per `monitored_user` basis) using the Ansible variables `applet` or `workflow` respectively (mutually exclusive, see explanantion of variables for general explanations).

More information about running DNAnexus analyses can be found on the DNAnexus documentation [Running Analyses](https://documentation.dnanexus.com/developer/api/running-analyses) page.

### Authorization
The downstream analysis (applet or workflow) will be launched in the project into which the RUN directory is uploaded to (`project`). The DNAnexus user / associated `dx_token` or `dx_user_token` must have at least `CONTRIBUTE` access to the aforementioned project for the analysis to be launched successfully. Computational resources are billable and will be billed to the bill-to of the corresponding project.

### Input and Options
The specified applet/workflow will be triggered using the `run` [API](http://autodoc.dnanexus.com/bindings/python/current/dxpy_apps.html?highlight=applet%20run#dxpy.bindings.dxapplet.DXExecutable.run) in the dxpy tool suite.

For an applet, the `executable_input` hash to the `run` command will be prepopulated with the key-value pair {"`upload_sentinel_record`": `$record_id`} where `$record_id` is the DNAnexus file-id of the sentinel record generated for the uploaded RUN directory (see section titled **Files generated**).

For a workflow the `executable_input` hash will be prepoluated with the key-value pair {"`0.upload_sentinel_record`": `$record_id`} where `$record_id` is the DNAnexus file-id of the sentinel record generated for the uploaded RUN directory (see section titled **Files generated**).

**It is the user's responsibility to ensure that the specified applet/workflow has an appropriate input contract which accepts a DNAnexus record with the input name of `upload_sentinel_record`**

Additional input/options can be specified, statically using the Ansible variable `downstream_input`. This should be provided as a JSON string, parsable, at the top level, as a Python dict of `str` to `str`.

Example of a properly formatted `downstream_input` for an `applet`
- ```{"input_name1": "value1", "input_name2": "value2"}```

Example of a properly formatted `downstream_input` for a `workflow`
- ```{"0.step0_input": "value1", "1.step2_input": "value2"})```

*Note the numerical index prefix necessary when specifying input for an `workflow`, which disambiguates which step in the workflow an input is targeted to*

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
       └───reads (or analyses)
            │  output files from downstream applet (e.g. demx)
            │   "reads" folder will be created if an applet is triggered
            │   "analyses" folder will be created if a workflow is triggered
            │  ...
```

The `reads` folder (and subfolders) will only be created if `applet` is specified.
The `analyses` folder (and subfolder) will only be created if `workflow` is specified.

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
