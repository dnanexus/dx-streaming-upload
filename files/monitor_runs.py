#!/usr/bin/env python
from __future__ import print_function
import argparse
import dxpy
import glob
import json
import multiprocessing
import os
import subprocess as sub
import sys
import time
import yaml
import logging
from functools import partial

RUN_INFO_FILENAME = 'RunInfo.xml'
RUN_COMPLETE_SENTINELS = ['RTAComplete.txt', 'RTAComplete.xml']

# If upload is incomplete and local log has not been updated
# for this many intervals, the upload is considered to have failed
# and will be relaunched
N_INTERVALS_TO_WAIT = 5

# Default config values (used when corresponding configs
# are not provided in the config YAML file)
CONFIG_DEFAULT = {
    "log_dir": "/opt/dnanexus/LOGS",
    "tmp_dir": "/opt/dnanexus/TMP",
    "min_age": 1000,
    "min_size": 1024,
    "min_interval": 1800,
    "n_retries": 3,
    "run_length": "24h",
    "n_seq_intervals": 2,
    "n_upload_threads": 8,
    "downstream_input": '',
    "n_streaming_threads":1
}

# Base folder in which the RUN folders are deposited
# In our current setup, we assume the following folder strcuture
# /
#  - <RUN_ID>
#      - runs (RUN folder tarball)
#      - reads (demuxed reads)
#      - etc (further downstream analysis)
RUN_UPLOAD_DEST = "/"

# Name of the sub-folder that corresponds to where the
# run directory tarballs and upload sentinel file are stored
REMOTE_RUN_FOLDER = "runs"

def parse_args():
    """ Parse command line arguments """
    parser = argparse.ArgumentParser(description='Script to monitor a local directory for new Illumina sequencing RUNS and\n' +
                                                  'trigger the incremental upload script when a new RUN directory not net synced\n' +
                                                  'to the DNANexus platform is observed.\n' +
                                                  'It also re-triggers incremental upload if local log file has not been updated\n' +
                                                  'for extended period of time.\n' +
                                                  'This script is intended to be triggered regularly (e.g. as a CRON job)',
                                     formatter_class=argparse.RawTextHelpFormatter)

    requiredNamed = parser.add_argument_group("Required named arguments")

    requiredNamed.add_argument('--config', '-c',
                        help='Path to config YAML file',
                        type=argparse.FileType('r'),
                        required=True)

    requiredNamed.add_argument('--project', '-p',
                        help='DNAnexus project ID to upload to',
                        required=True)

    requiredNamed.add_argument('--directory', '-d',
                        help='Local directory to monitor for new RUN folder(s)',
                        required=True)

    requiredNamed.add_argument('--verbose', '-v',
                        help='Print verbose debugging messages',
                        action='store_true')

    optionalNamed = parser.add_argument_group("Optional named arguemnts")

    optionalNamed.add_argument('--script', '-s',
                        help='Script to execute after successful upload of the RUN folder, ' +
                              'see incremental_upload.py',
                        required=False)
    optionalNamed.add_argument('--downstream-input', '-N',
                        help='Input for DNAnexus applet/workflow, specified as a JSON string',
                        required=False)

    downstreamAnalysis = parser.add_mutually_exclusive_group(required=False)

    downstreamAnalysis.add_argument('--applet', '-A',
                        help='ID of DNAnexus app(let) to execute after successful ' +
                             'upload of the RUN folder, see incremental_upload.py. ' +
                             'Mutually exclusive with --workflow.',
                        required=False)
    downstreamAnalysis.add_argument('--workflow', '-w',
                        help='ID of DNAnexus workflow to execute after successful ' +
                             'upload of the RUN folder, see incremental_upload.py ' +
                             'Mutually exclusive with --applet',
                        required=False)

    args = parser.parse_args()
    # Canonize file paths
    args.directory = os.path.abspath(args.directory)
    if (args.verbose):
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
    return args


def get_dx_auth_token():
    """Parses dx_auth_token from the output of dx env
    Exits with error message if dx env failed to execute
    or the environment is not set with an auth token"""

    try:
        return dxpy.SECURITY_CONTEXT['auth_token']

    except KeyError, e:
        error_msg = ("Could not parse auth_token in dxpy environment, ensure that "
                     "you have logged in using an API token!\n{0}: {1}")
        logging.error(error_msg.format(e.errno, e.strerror))
        sys.exit(1)


def get_streaming_config(config_file, project, applet, workflow, script, token):
    """ Configure settings by reading in the config_file, which
    is assumed to be a YAML file"""
    config = {"project": project, "token": token}
    if applet:
        config["applet"] = applet
    if workflow:
        config["workflow"] = workflow
    if script:
        config["script"] = os.path.abspath(script)
    user_config_dict = yaml.load(config_file)
    for key, default in CONFIG_DEFAULT.items():
        config[key] = user_config_dict.get(key, default)
    return config


def check_config_fields(config):
    """ Validate the given directory fields in config are valid directories"""
    def invalid_config(msg):
        logging.error("Config file is invalid: {0}".format(msg))
        sys.exit(1)

    required_dirs = ['log_dir', 'tmp_dir']

    for r_dir in required_dirs:
        if (r_dir not in config):
            invalid_config("{0} is required, but not specified.".format(r_dir))

        config[r_dir] = os.path.abspath(os.path.expanduser(config[r_dir]))

        if (not os.path.isdir(config[r_dir])):
            try:
                os.makedirs(config[r_dir])
            except OSError, e:
                invalid_config("Specified {0} ({1}) could not be created".format(r_dir, config[r_dir]))

    input_json = config["downstream_input"]
    if input_json:
        try:
            _ = json.loads(input_json)
        except ValueError as e:
            invalid_config("JSON parse error for downstream input: {0}".format(input_json))
    return config


def get_run_folders(base_dir):
    """ Get the local directories within the specified base_dir.
    It does NOT check whether these directories are Illumina directories. This check
    is left to the downstream incremental_upload.py script"""
    if not os.path.isdir(base_dir):
        error_msg = "Specified base directory for monitoring ({0}) is not a valid directory."
        logging.error(error_msg.format(base_dir))
        sys.exit(1)

    # Get all directory names which are not hidden (ie doesn't starts with '.')
    return [dir_name for dir_name in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, dir_name))
            and not dir_name.startswith(".")]


def is_run_folder(folder_path):
    """This function will check if the given folder is an Illumina run folder
    by looking for the presence of an RUN_INFO_FILENAME file"""
    return os.path.isfile(os.path.join(folder_path, RUN_INFO_FILENAME))


def is_complete_run_folder(folder_path):
    """This function will check to see if the given folder is a complete run 
    folder by checking for the presence of RTAComplete.txt or RTAComplete.xml"""
    if not is_run_folder(folder_path):
        return False

    return any((os.path.isfile(os.path.join(folder_path, fn)) for fn in RUN_COMPLETE_SENTINELS))


def is_stale_run_folder(folder_path, run_length, n_intervals):
    """This function will check whether the given folder appears to be 
    a stale run folder by checking how much time has passed between now
    and its creation time."""
    if not is_run_folder(folder_path) or is_complete_run_folder(folder_path):
        return False

    curr_time = time.time()
    created_time = os.path.getmtime(os.path.join(folder_path, RUN_INFO_FILENAME))
    time_to_wait = dxpy.utils.normalize_timedelta(run_length) / 1000 * n_intervals

    if (curr_time - created_time) > time_to_wait:
        warning_message = ("Run folder {0} was created on {1}; "
                           "it is determined to be STALE and will NOT be uploaded.")
        logging.warning(warning_message.format(folder_path, 
            time.strftime("%Z - %Y/%m/%d, %H:%M:%S", time.localtime(created_time))))
        return True
    else:
        return False


def is_sync_incomplete(folder, config):
    """ Check whether the RUN folder sync is incomplete by querying the state
    of the sentinel record (closed = complete, open = incomplete). Returns
    a list of incomplete syncs which have been deemed to be inactive, according
    to the local_upload_has_lapsed function"""
    sentinel_record = find_record(folder, config['project'])
    try:
        if sentinel_record.describe()['state'] == "open" and local_upload_has_lapsed(folder, config):
            return True
        else:
            return False
    except KeyError, e:
        error_msg = "Unknown exception when getting state of record {0}. {1}: {2}"
        logging.error(error_msg.format(sentinel_record, e.errno, e.strerror))
        raise


def get_folders_in_dnax_project(project):
    """Gets a list of folders in the RUN_UPLOAD_DEST folder of the given project. """
    try:
        dx_proj = dxpy.bindings.DXProject(project)
    except dxpy.exceptions.DXError, e:
        logging.error("Invalid project ID ({0}) given. {1}".format(project, str(e)))
        sys.exit(1)

    try:
        dnax_folders = dx_proj.list_folder(RUN_UPLOAD_DEST, only="folders")['folders']
        dnax_folders = {os.path.basename(folder) for folder in dnax_folders}

        return dnax_folders

    # RUN_UPLOAD_DEST is not a valid directory in project
    # ie, incremental upload has never been triggered in this project
    # All RUN folders are considered to be unsynced
    except dxpy.exceptions.ResourceNotFound, e:
        logging.warning("{0} not found in project {1}".format(RUN_UPLOAD_DEST, project))
        logging.warning("Interpreting this as all local RUN folders are unsynced.")
        return set()

    # Dict returned by list_folder did not contian a "folders" key
    # This is an unexpected exception
    except KeyError, e:
        error_msg = "Unknown exception when fetching folders in {0} of {1}. {2}: {3}."
        logging.error(error_msg.format(RUN_UPLOAD_DEST, project, e.errno, e.strerror))
        sys.exit(1)


def find_record(run_name, project):
    """ Wrapper to find the sentinel record for a given run_name in the given
    DNAnexus project"""
    try:
        record = dxpy.find_one_data_object(classname="record", name="*{0}*".format(run_name),
                                       project=project, folder="{0}/{1}/{2}".format(RUN_UPLOAD_DEST.rstrip('/'), run_name, REMOTE_RUN_FOLDER),
                                       name_mode="glob", return_handler=True, more_ok=False, zero_ok=False)

        return record

    # Either zero or multiple records found, in cases where we cannot resolve uniquely
    # the upload sentinel, we exit the program with an error
    except dxpy.exceptions.DXSearchError, e:
        error_msg = "Unexpected result when searching for upload sentinel of run {0}. {1}"
        logging.error(error_msg.format(run_name, e))
        raise


def local_upload_has_lapsed(folder, config):
    """ Determines whether an incomplete RUN directory sync has "lapsed", ie
    it has failed and need to be re-triggered. Local_upload_has_lapsed will return
    True if there has been no update to the local LOG file for N_INTERVALS_TO_WAIT *
    config['min_interval']"""

    local_log_files = glob.glob('{0}/*{1}*'.format(config['log_dir'], folder))
    if not local_log_files:
        # Could not find a local log file for the run-folder for which the upload has been initiated
        # The log file could have been moved or deleted. Treat this as an lapsed upload
        debug_message = "Local log file could not be found for {run} at {folder}"
        logging.debug(debug_message.format(run=folder, 
            folder='{0}'.format(os.path.join(config['log_dir'], folder))))
        debug_message = ("Treating run {0} as a lapsed local upload, "
                         "and will reinitiate streaming upload")
        logging.debug(debug_message.format(folder))

        return True

    if len(local_log_files) > 1:
        # Found multiple log file satisfying the name of the run folder, we will use the latest
        # log as the accurate one. NOTE: This script does not currently support upload by lane
        # so we do *NOT* anticipate multiple records per run folder
        debug_message = ("Found {n} log files for run {run} in folder {folder}. "
                         "Using the latest log. The log files are {files}.")
        logging.debug(debug_message.format(n=len(local_log_files), run=folder,
            folder='{0}/{1}'.format(config['log_dir'], folder), files=local_log_files))
        
    # Get most recently modified file's mod time
    mod_time = max([os.path.getmtime(path) for path in local_log_files])
    elapsed_time = time.time() - mod_time

    return ((elapsed_time / config['min_interval']) > N_INTERVALS_TO_WAIT)


def trigger_streaming_upload(folder, config):
    """ Execute the incremental_upload.py script, assumed to be located
    in the same directory as the executed monitor_runs.py, potentially multiple
    instances of this can be triggered using a thread pool"""
    curr_dir = sys.path[0]
    inc_upload_script_loc = "{0}".format(os.path.join(curr_dir, "incremental_upload.py"))
    command = ["python", inc_upload_script_loc,
               "-a", config['token'],
               "-p", config['project'],
               "-r", folder,
               "-t", config['tmp_dir'],
               "-L", config['log_dir'],
               "-m", config['min_age'],
               "-z", config['min_size'],
               "-i", config['min_interval'],
               "-R", config['n_retries'],
               "-D", config['run_length'],
               "-I", config['n_seq_intervals'],
               "-u", config['n_upload_threads'],
               "--verbose"]

    if 'applet' in config:
        command += ["-A", config['applet']]

    if 'workflow' in config:
        command += ["-w", config['workflow']]

    if 'script' in config:
        command += ["-s", config['script']]

    if 'downstream_input' in config:
        command += ["--downstream-input", config['downstream_input']]
    # Ensure all numerical values are formatted as string
    command = [str(word) for word in command]

    logging.info("Triggering incremental upload command: {0}".format(' '.join(command)))
    try:
        inc_out = sub.check_output(command)
    except sub.CalledProcessError, e:
        error_message = "Incremental upload command {0} failed.\nError code {1}:{2}"
        logging.error(error_message.format(e.cmd, e.returncode, e.output))


def process_folder(run_folder, base_dir, dnax_folders, config):
    """This function will:
       1. Check whether the given folder appears to be an Illumina run folder
       2. If it is a run folder, determine whether the run is:
          a. Complete (has a RunInfo.xml and a RTAComplete.txt/xml file)
          b. In-progress (has a RunInfo.xml file, but not a RTAComplete.txt/xml file)
          c. Stale (has a RunInfo.xml file, which was created more than Y times expected duration
             of a sequencing run, both the sequencing runtime and Y will be user-specified,
             with defaults of 2 and 24hrs respectively)"""
    folder_path = os.path.join(base_dir, run_folder)
    
    if not is_run_folder(folder_path):
        warning_message = '{0} does not appear to be an Illumina run folder. It will be skipped.'
        logging.warning(warning_message.format(run_folder))
        return
    
    # If this is an incomplete run folder and a stale run folder
    if is_stale_run_folder(folder_path, config["run_length"], config["n_seq_intervals"]):
        warning_message = '{0} is a stale Illumina run folder. It will be skipped.'
        logging.warning(warning_message.format(run_folder))
        return
    
    # Check to see if we have started to sync this folder already.
    if run_folder not in dnax_folders or is_sync_incomplete(run_folder, config):
        if run_folder in dnax_folders:
            logging.debug("Resuming incomplete sync for {}".format(run_folder))
        else:
            logging.debug("Starting sync for {}".format(run_folder))
        trigger_streaming_upload(run_folder, config)


def main():
    """ Main entry point """
    args = parse_args()
    logging.debug('Got args: ' + str(args))

    # Make sure that we can find the incremental_upload scripts
    curr_dir = sys.path[0]
    if (not os.path.isfile("{0}".format(os.path.join(curr_dir, 'incremental_upload.py'))) or
        not os.path.isfile("{0}".format(os.path.join(curr_dir, 'dx_sync_directory.py')))):
        logging.error("Failed to locate necessary scripts for incremental upload")
        sys.exit(1)

    token = get_dx_auth_token()
    logging.debug("Got token: {}".format(token))

    streaming_config = get_streaming_config(args.config, args.project,
                                            args.applet, args.workflow,
                                            args.script, token)
    logging.debug("Got config: {}".format(str(streaming_config)))

    streaming_config = check_config_fields(streaming_config)
    logging.debug("Validated config: {}".format(str(streaming_config)))

    run_folders = get_run_folders(args.directory)
    logging.debug("Got RUN folders: {}".format(str(run_folders)))

    dnax_folders = get_folders_in_dnax_project(args.project)
    logging.debug("Got DNAnexus folders: {}".format(str(dnax_folders)))

    partial_process_folder = partial(process_folder, base_dir=args.directory,
        dnax_folders=dnax_folders, config=streaming_config
    )
    
    pool = multiprocessing.Pool(processes=int(streaming_config["n_streaming_threads"]))
    pool.map_async(partial_process_folder, run_folders)
    pool.close()
    pool.join()


if __name__ == "__main__":
    main()