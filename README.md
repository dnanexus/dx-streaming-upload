dx-streaming-upload
=========

The dx-streaming-upload role packages the streaming upload module for increamentally uploading a RUN directory from an Illumina sequencer onto the DNAnexus platform. Instruments that this module support include the Illumina MiSeq, NextSeq, HiSeq-2500, HiSeq-4000 and HiSeq-X.

Requirements
------------

Users of this module needs a DNAnexus account and its accompanying authentication. To register for a trial account, visit the [DNAnexus homepage](https://dnanexus.com). More information and tutorials about the DNAnexus platform can be found at the [DNAnexus wiki page](https://wiki.dnanexus.com).

Role Variables
--------------
- `mode`: `{deploy, debug}` In the *deploy* mode, monitoring cron job is triggered every minute; in *deploy mode*, monitoring cron job is triggered every hour.
- `monitored_dir`: Path to the local directory that should be monitored for RUN folders. Suppose that the folder `20160101_M000001_0001_000000000-ABCDE` is the RUN directory, then the folder structure assumed is `{{monitored_dir}}/20160101_M000001_0001_000000000-ABCDE`
- `upload_project`: ID of the DNAnexus project that the RUN folders should be uploaded to. The ID is of the form `project-BpyQyjj0Y7V0Gbg7g52Pqf8q` 
- `dx_token`: API token for the DNAnexus user to be used for data upload. The API token should give minimally CONTRIBUTE access to the `{{ upload project }}`.

Dependencies
------------

Python 2.7 is needed. This program is not compatible with Python 3.X.

Minimal Ansible version: 2.0.

This program is intended for Ubuntu 14.04 (Trusty) and has been tested on the 15.10 (Wily) release. Most features should work on a Ubuntu 12.04 (Precise) system, but this has not been tested to date.


Example Playbook
----------------

To be added.

License
-------

Apache

Author Information
------------------

DNAnexus (email: info@dnanexus.com)
