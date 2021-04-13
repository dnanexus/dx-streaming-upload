#!/usr/bin/env python

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

# Whether to print verbose Debuggin messages
DEBUG = False

# If upload is incomplete and local log has not been updated
# for this many intervals, the upload is considered to have failed
# and will be relaunched
N_INTERVALS_TO_WAIT = 5

# Default config values (used when corresponding configs
# are not provided in the config YAML file)
CONFIG_DEFAULT = {
    "log_dir": "/opt/dnanexus/LOGS",
    "tmp_dir": "/opt/dnanexus/TMP",
    "exclude": "",
    "min_age": 1000,
    "min_size": 1024,
    "max_size": 10000,
    "min_interval": 1800,
    "n_retries": 3,
    "run_length": "24h",
    "n_seq_intervals": 2,
    "n_upload_threads": 8,
    "downstream_input": '',
    "n_streaming_threads":1,
    "delay_sample_sheet_upload": False,
    "novaseq": False
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
        global DEBUG
        DEBUG = True
    return args

def get_dx_auth_token():
    """Parses dx_auth_token from the output of dx env
    Exits with error message if dx env failed to execute
    or the environment is not set with an auth token"""

    try:
        return dxpy.SECURITY_CONTEXT['auth_token']

    except KeyError, e:
        sys.exit("Could not parse auth_token in dxpy environment, ensure that you have logged in using an API token!\n{0}: {1}".format(e.errno, e.strerror))


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
        sys.exit("Config file is invalid: {0}".format(msg))

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
        sys.exit("Specified base directory for monitoring ({0}) is not a valid directory.".format(
            base_dir))

    # Get all directory names which are not hidden (ie doesn't starts with '.')
    return [dir_name for dir_name in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, dir_name))
            and not dir_name.startswith(".")]

def check_local_runs(base_dir, run_folders, run_length, n_intervals, novaseq=False):
    """ Check local folders to ascertain which are Illumina RUN directories (defined
    as containing a RunInfo.xml file in root of the folder).
    Classify such RUN folders into 3 classes:
     - Completed runs (has a RunInfo.xml and a RTAComplete.txt/xml file)
     - In-progress run (has a RunInfo.xml file, but not a RTAComplete.txt/xml file)
     - Stale run (has a RunInfo.xml file, which was created more than Y times expected duration
       of a sequencing run, both the sequencing runtime and Y will be user-specified,
       with defaults of 2 and 24hrs respectively).
    """

    not_run_folders, completed_runs, in_progress_runs, stale_runs = ([] for i in range(4))

    for run_folder in run_folders:
        folder_path = os.path.join(base_dir, run_folder)
        run_info_path = os.path.join(folder_path, 'RunInfo.xml')
        if not os.path.isfile(run_info_path):
            # Not a run_folder
                not_run_folders.append(run_folder)
        else:
            # Is a RUN folder
            if os.path.isfile(os.path.join(folder_path, 'RTAComplete.txt')) or \
                os.path.isfile(os.path.join(folder_path, 'RTAComplete.xml')) or \
                (novaseq and os.path.isfile(os.path.join(folder_path, 'CopyComplete.txt'))):
                # Is a completed RUN folder
                completed_runs.append(run_folder)
            else:
                # RUN is incomplete, check whether it's stale
                curr_time = time.time()
                created_time = os.path.getmtime(run_info_path)
                time_to_wait = dxpy.utils.normalize_timedelta(run_length) / 1000 * n_intervals
                if (curr_time - created_time) > time_to_wait:
                    # Stale run
                    if DEBUG: print "==DEBUG== run folder {0} was created on {1}; "\
                    "it is determined to be STALE and will NOT be uploaded.".format(run_folder,
                        time.strftime("%Z - %Y/%m/%d, %H:%M:%S", time.localtime(created_time)))

                    stale_runs.append(run_folder)
                else:
                    # Ongoing run
                    in_progress_runs.append(run_folder)

    return (not_run_folders, completed_runs, in_progress_runs, stale_runs)


def check_dnax_folders(run_folders, project):
    """Check the RUN folders that have been synced (fully/partially) onto DNAnexus by looking into the
    RUN_UPLOAD_DEST folder of the given project. """
    try:
        dx_proj = dxpy.bindings.DXProject(project)

    except dxpy.exceptions.DXError, e:
        sys.exit("Invalid project ID ({0}) given. {1}".format(project, str(e)))

    try:
        dnax_folders = dx_proj.list_folder(RUN_UPLOAD_DEST, only="folders")['folders']
        dnax_folders = [os.path.basename(folder) for folder in dnax_folders]

        synced_folders = filter( (lambda folder: folder in dnax_folders), run_folders)
        unsynced_folders = filter( (lambda folder: folder not in dnax_folders), run_folders)

        return (synced_folders, unsynced_folders)

    # RUN_UPLOAD_DEST is not a valid directory in project
    # ie, incremental upload has never been triggered in this project
    # All RUN folders are considered to be unsynced
    except dxpy.exceptions.ResourceNotFound, e:
        if DEBUG: print "==DEBUG== {0} not found in project {1}".format(RUN_UPLOAD_DEST, project)
        if DEBUG: print "==DEBUG== Interpreting this as all local RUN folders are unsynced"
        return ([], run_folders)

    # Dict returned by list_folder did not contian a "folders" key
    # This is an unexpected exception
    except KeyError, e:
        sys.exit("Unknown exception when fetching folders in {0} of {1}. {2}: {3}.".format(
                  RUN_UPLOAD_DEST, project, e.errno, e.strerror))

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
        sys.exit("Unexpected result when searching for upload sentinel of run {0}. {1}".format(run_name, e))


def local_upload_has_lapsed(folder, config):
    """ Determines whether an incomplete RUN directory sync has "lapsed", ie
    it has failed and need to be re-triggered. Local_upload_has_lapsed will return
    True if there has been no update to the local LOG file for N_INTERVALS_TO_WAIT *
    config['min_interval']"""

    local_log_files = glob.glob('{0}/*{1}*'.format(config['log_dir'], folder))
    if not local_log_files:
        # Could not find a local log file for the run-folder for which the upload has been initiated
        # The log file could have been moved or deleted. Treat this as an lapsed upload
        if DEBUG:
            print "==INFO== Local log file could not be found for "\
                    "{run} at {folder}""".format(run=folder,
                                             folder='{0}/{1}'.format(config['log_dir'], folder))
            print "==INFO== Treating run {0} as a lapsed local upload, "\
                   "and will reinitiate streaming upload""".format(folder)

        return True

    if len(local_log_files) > 1:
        # Found multiple log file satisfying the name of the run folder, we will use the latest
        # log as the accurate one. NOTE: This script does not currently support upload by lane
        # so we do *NOT* anticipate multiple records per run folder
        if DEBUG:
            print "==INFO== Found {n} log files for run {run} in folder {folder}."\
                   "Using the latest log. The log files are {files}.".format(n=len(local_log_files),
                                                                            run=folder,
                                                                            folder='{0}/{1}'.format(config['log_dir'], folder),
                                                                            files=local_log_files)
    # Get most recently modified file's mod time
    mod_time = max([os.path.getmtime(path) for path in local_log_files])
    elapsed_time = time.time() - mod_time

    return ((elapsed_time / config['min_interval']) > N_INTERVALS_TO_WAIT)

def check_complete_sync(synced_folders, config):
    """ Check whether the RUN folder sync is complete by querying the state
    of the sentinel record (closed = complete, open = incomplete). Returns
    a list of incomplete syncs which have been deemed to be inactive, according
    to the local_upload_has_lapsed function"""
    incomplete_syncs = []
    for folder in synced_folders:
        sentinel_record = find_record(folder, config['project'])
        try:
            state = sentinel_record.describe()['state']
            # Upload sentinel is open, signifies that incremental upload
            # is incomplete
            if state == "open":
                if (local_upload_has_lapsed(folder, config)):
                    incomplete_syncs.append(folder)

        except KeyError, e:
            sys.exit("Unknown exception when getting state of record {0}. {1}: {2}".format(sentinel_record, e.errno, e.strerror))

    return incomplete_syncs

def _trigger_streaming_upload(folder, config):
    """ Execute the incremental_upload.py script, assumed to be located
    in the same directory as the executed monitor_runs.py, potentially multiple
    instances of this can be triggered using a thread pool"""
    curr_dir = sys.path[0]
    inc_upload_script_loc = "{0}/{1}".format(curr_dir, "incremental_upload.py")
    command = ["python", inc_upload_script_loc,
               "-a", config['token'],
               "-p", config['project'],
               "-r", folder,
               "-t", config['tmp_dir'],
               "-L", config['log_dir'],
               "-m", config['min_age'],
               "-z", config['min_size'],
               "-M", config['max_size'],
               "-i", config['min_interval'],
               "-R", config['n_retries'],
               "-D", config['run_length'],
               "-I", config['n_seq_intervals'],
               "-u", config['n_upload_threads'],
               "--verbose"]

    if config['novaseq']:
        command += ['-n']

    if config['exclude'] != '':
        command += ["-x", config['exclude']]

    if 'applet' in config:
        command += ["-A", config['applet']]

    if 'workflow' in config:
        command += ["-w", config['workflow']]

    if 'script' in config:
        command += ["-s", config['script']]

    if 'downstream_input' in config:
        command += ["--downstream-input", config['downstream_input']]

    if config.get("delay_sample_sheet_upload", False):
        command.append("-S")
    # Ensure all numerical values are formatted as string
    command = [str(word) for word in command]

    print "==INFO== Triggering incremental upload command: {0}".format(
        ' '.join(command))
    try:
        inc_out = sub.check_output(command)
    except sub.CalledProcessError, e:
        print "==ERROR== Incremental upload command {0} failed.\n "\
        "Error code {1}:{2}".format(e.cmd, e.returncode, e.output)

def trigger_streaming_upload(folders, config):
    """ Open a thread pool of size N_STREAMING_THREADS
    and trigger streaming upload for all unsynced and incomplete folders"""
    pool = multiprocessing.Pool(processes=int(config["n_streaming_threads"]))
    for folder in folders:
        print "Adding folder {0} to pool".format(folder)
        pool.apply_async(_trigger_streaming_upload, args=(folder, config)).get()

    # Close pool, no more tasks can be added
    pool.close()

    # Wait for all incremental upload threads
    pool.join()

def main():
    """ Main entry point """
    args = parse_args()
    if DEBUG: print "==DEBUG== Got args, ", args

    # Make sure that we can find the incremental_upload scripts
    curr_dir = sys.path[0]
    if (not os.path.isfile("{0}/{1}".format(curr_dir, 'incremental_upload.py')) or
        not os.path.isfile("{0}/{1}".format(curr_dir, 'dx_sync_directory.py'))):
        sys.exit("Failed to locate necessary scripts for incremental upload")

    token = get_dx_auth_token()
    if DEBUG: print "==DEBUG== Got token: ", token

    run_folders = get_run_folders(args.directory)
    if DEBUG: print "==DEBUG== Got RUN folders: ", run_folders

    streaming_config = get_streaming_config(args.config, args.project,
                                            args.applet, args.workflow,
                                            args.script, token)

    if DEBUG: print "==DEBUG== Got config: ", streaming_config

    streaming_config = check_config_fields(streaming_config)
    if DEBUG: print "==DEBUG== Validated config: ", streaming_config

    (not_runs, completed_runs, ongoing_runs, stale_runs) = check_local_runs(args.directory, run_folders,
                                                                  streaming_config['run_length'],
                                                                  streaming_config['n_seq_intervals'], streaming_config.get("novaseq", False))

    if DEBUG:
        print "==DEBUG== Searching for run directories in {0}:".format(args.directory)
        if not_runs:
            print "==DEBUG== Following folders are deemed NOT to be run directories: {0}".format(not_runs)
        if completed_runs:
            print "==DEBUG== Following folders are deemed to be COMPLETED runs: {0}".format(completed_runs)
        if ongoing_runs:
            print "==DEBUG== Following folders are deemed to be ONGOING runs: {0}".format(ongoing_runs)
        if stale_runs:
            print "==DEBUG== Following folders are deeemed to be STALE runs "\
            "and will not be uploaded: {0}".format(stale_runs)

    syncable_folders = completed_runs + ongoing_runs
    (synced_folders, unsynced_folders) = check_dnax_folders(syncable_folders, args.project)
    if DEBUG: print "==DEBUG== Got synced folders: ", synced_folders
    if DEBUG: print "==DEBUG== Got unsynced folders: ", unsynced_folders

    folders_to_sync = []
    if synced_folders:
        incomplete_syncs = check_complete_sync(synced_folders, streaming_config)
        folders_to_sync += incomplete_syncs
        if DEBUG: print "==DEBUG== Got incomplete folders: ", incomplete_syncs

    # Preferentially upload partially-synced folders before unsynced ones
    folders_to_sync += unsynced_folders
    folders_to_sync = ["{0}/{1}".format(args.directory, folder) for folder in folders_to_sync]

    if DEBUG: "==DEBUG== Folders to sync: {0}".format(folders_to_sync)

    trigger_streaming_upload(folders_to_sync, streaming_config)

if __name__ == "__main__":
    main()
