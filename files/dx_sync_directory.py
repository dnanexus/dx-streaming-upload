#!/usr/bin/env python

"""
Script to 'sync' a local directory into the platform. This does not
transfer files into the platform one-by-one, but rather uploads
gzipped tar files containing bundles of recently modified files.
"""

import argparse
import json
import os
import os.path
import sys
import tarfile
import time
import tempfile
import re
import subprocess
import dxpy
import dxpy.utils.resolver

# For more information about script and inputs run the script with --help option
# $ python dx_sync_directory.py --help
#
# Log file structure:
#
#  The log file is contains a serialized JSON object containing the
#  following keys and values:
#
#   sync_dir: the path to the local directory to by synchronized
#
#   tar_destination: Location on DNAnexus to upload the tarball
#
#   file_prefix: To use to name the files once uploaded to DNAnexus
#
#   include_patterns: An array of patterns of the files to include in the sync
#
#   exclude_patterns: An array of patterns of files to exclude from the sync
#
#   tar_files: an object describing the status of each of the tar
#   files to be uploaded. Each key is the local path to the tar file;
#   the corresponding values are objects with the following
#   keys/values:
#
#     status: one of the following strings:
#       "tarred" -- the tar file has been created, but not yet (successfully) uploaded
#       "uploaded" -- the tar file has been successfully uploaded, but not yet locally removed
#       "removed" -- the tar file has been successfully uploaded and removed from the local filesystem
#
#     timestamps [Python's time.time() timestamp]
#       "tar_start"
#       "tar_end"
#       "upload_start"
#       "upload_end"
#       "remove_start"
#       "remove_end"
#
#     file_id: file ID of the uploaded file in the platform
#
#   next_tar_index: number giving the index of the next tar file to be
#   created; used to construct the name of the file.
#
#   files: an object describing the files that have been synced. Each
#   key is the local path of a file; the corresponding values are
#   objects with the following keys/values:
#
#    mtime: the file's modified timestamp at the time it
#    was synced
#
#    size: the file's size, used to determine if tarball has met minimum size to upload

# Testing:
#
#  Run rsync to copy a run directory to another location on the filesystem,
#  like so:
#
#   rsync -av --no-t --bwlimit <KBps> <source-dir> <dest-dir>
#
#    '-a' sets archive mode, preserving file attributes
#
#    '--no-t' overrides the preservation of mtimes
#
#    '--bwlimit <KBps>' limits the transfer rate, to simulate files being
#    copied slowly throughout an instrument run. E.g., let N be the size of
#    the run directory in bytes, and S be the length of the instrument run
#    in seconds. Set this parameter to N/S in order to make the rsync take
#    roughly as long as the run.
#
#  (Keep in mind that rsync behaves differently depending on whether
#  <source-dir> has a trailing slash.)
#
#  While rsync is running, periodically run this script with sync_dir set
#  to the <dest-dir> above. Download and untar the resulting files, and
#  compare the contents to the contents of <dest-dir> using a recursive
#  diff:
#
#   diff -r <dir1> <dir2>

# TODO:
#
# - Use dx environment to get default for --tar-destination?
#
# - Compress log to save space? Test on large runs and determine whether
#   it's necessary. It may be better not to, in order to prevent
#   corruption.
#
# - Another idea to avoid possible log corruption: don't overwrite the
#   existing log file; instead, write to a new file, then move it
#   (i.e., rename it to have the same name as the existing log file).

def parse_args():
    """Parse the command-line arguments and canonicalize file path
    arguments."""

    parser = argparse.ArgumentParser(description='Script to "synchronize" a local directory into the platform. This does not' +
                                    '\n' + 'transfer files into the platform one-by-one, but rather uploads gzipped tar' +
                                    '\n' + 'files containing bundles of recently modified files.',
                                    epilog='Each time this script is run, it examines the specified directory and the log' +
                                    '\n' + 'file (if it exists). It identifies each file that has not yet been uploaded,' +
                                    '\n' + 'and whose modified timestamp is at least <min-age> seconds in the past.,' +
                                    '\n' + 'In addition, it finds all files which have been previously uploaded, but whose' +
                                    '\n' + 'modified timestamp has changed since the previous upload.' +
                                    '\n' +
                                    '\n' + 'All of the files to be uploaded are added to a gzipped TAR file which is' +
                                    '\n' + 'then uploaded. Newly uploaded files are recorded in the log file, including' +
                                    '\n' + 'the modified timestamp of each file at the time it was added to the tar file.' +
                                    '\n' +
                                    '\n' + 'The platform file ID of the uploaded file is printed to standard output, and' +
                                    '\n' + 'the script exits.',
                                    formatter_class=argparse.RawTextHelpFormatter
                                    )
    temp_dir = tempfile.gettempdir()
    parser.add_argument('--tar-directory', '-t', metavar='<directory>',
                        help='Local directory in which to write temporary tar files' +
                        '\n' + 'during upload.' +
                        '\n' + 'DEFAULT: %s' % (temp_dir) +
                        '\n' +
                        '\n')
    parser.add_argument('--tar-destination', '-T', metavar='<platform-location>', required=True,
                        help='Remote (platform) project-ID and folder to which to' +
                        '\n' + 'upload tar files.' +
                        '\n' + 'IF NOT SPECIFIED: files are uploaded to the current' +
                        '\n' + 'project and folder as determined from the dx' +
                        '\n' + 'environment.' +
                        '\n' +
                        '\n')
    parser.add_argument('--log-file', '-l', metavar='<file>', required=True,
                        help='Local path to a log file describing sync state.' +
                        '\n' + 'This file contains the path of each uploaded file,' +
                        '\n' + 'including the modified timestamp of the file at the' +
                        '\n' + 'time of upload. Previously uploaded files are ignored' +
                        '\n' + 'unless either of those attributes has changed.' +
                        '\n' +
                        '\n')
    parser.add_argument('--min-tar-size', '-s', type=int, metavar='<MB>',
                        help='The minimum size of the tar file to be uploaded. If' +
                        '\n' + 'the number of modified files does not total this' +
                        '\n' + 'size, the tar file will not be created or uploaded.' +
                        '\n' + 'If --finish is specified, this argument will' +
                        '\n' + 'automatically be set to 0. DEFAULT=0 MB' +
                        '\n' +
                        '\n')
    parser.add_argument('--max-tar-size', '-X', type=int, metavar='<MB>',
                        help='The maximum size of the tar file to be uploaded. If' +
                        '\n' + 'the total size of the files to be uploaded is' +
                        '\n' + 'greater, the files will be split into multiple' +
                        '\n' + 'archives. --max-tar-size must be greater than' +
                        '\n' + '--min-tar-size. DEFAULT=75 MB' +
                        '\n' +
                        '\n')
    parser.add_argument('--upload-threads', '-u', type=int, metavar='<int>',
                        help='Number of upload threads launched by Upload Agent' +
                        '\n' + '(Decrease to improve stability in low-bandwidth' +
                        '\n' + 'connections), DEFAULT=8' +
                        ']n' +
                        '\n')
    parser.add_argument('--include-patterns', '-i', metavar='<regex>', nargs='*',
                        help='An optional list of regex patterns to search for.' +
                        '\n' + 'If 1 or more regex patterns are given, then' +
                        '\n' + 'only the files matching the pattern will be tarred' +
                        '\n' + 'and uploaded. The pattern will be matched against' +
                        '\n' + 'the full file path. (i.e. "/foo" will match all the' +
                        '\n' + 'files and subdirectories under  a directory named foo/' +
                        '\n' + 'and the file foo.txt)'
                        '\n' +
                        '\n')
    parser.add_argument('--exclude-patterns', '-x', metavar='<regex>', nargs='*',
                        help='An optional list of regex patterns to exclude.' +
                        '\n' + 'If 1 or more regex patterns are given, the files' +
                        '\n' + 'matching the pattern will be skipped (not tarred nor' +
                        '\n' + 'uploaded). This pattern will override the' +
                        '\n' + '--include-patterns argument so if a file matches a' +
                        '\n' + 'regex specified by --include-patterns AND matches a regex' +
                        '\n' + 'specified here, the file will ultimately be excluded' +
                        '\n' + 'from upload. The pattern will be matched against the' +
                        '\n' + 'full file path.' +
                        '\n' +
                        '\n')
    parser.add_argument('--prefix', '-p', metavar='<prefix>', required=True,
                        help='Required prefix string to name the TAR archives to be' +
                        '\n' + 'uploaded. This prefix will be stored in the log. If the' +
                        '\n' + 'log file given already exists, the prefix will be compared' +
                        '\n' + 'to the one stored in the log. dx_sync_directory.py will' +
                        '\n' + 'fail if the prefix does not match.' +
                        '\n' +
                        '\n')

    upload_debug_group = parser.add_mutually_exclusive_group(required=False)
    upload_debug_group.add_argument('--dxpy-upload', '-d', action='store_true',
                                    help='This flag allows you to specify whether to use dxpy' +
                                    '\n' + 'instead of the default Upload Agent to upload your' +
                                    '\n' + 'data.' +
                                    '\n' +
                                    '\n')
    upload_debug_group.add_argument('--verbose', '-v', action='store_true',
                                    help='This flag allows you to specify upload agent' +
                                    '\n' + '--verbose mode.' +
                                    '\n' +
                                    '\n')


    age_group = parser.add_mutually_exclusive_group(required=False)
    age_group.add_argument('--min-age', '-m', type=int, metavar='<seconds>',
                           help='The minimum age (in seconds) of files to be synced.' +
                           '\n' + 'Only files whose modified timestamp is at least' +
                           '\n' + '<seconds> seconds in the past will be synced. This is' +
                           '\n' + 'a heuristic aimed at ensuring that we only upload' +
                           '\n' + 'files that have finished being written. If <seconds>' +
                           '\n' + 'is less than 1, the script will upload all files that' +
                           '\n' + 'have not yet been uploaded, so as to finish syncing a' +
                           '\n' + 'directory where files are no longer expected to be' +
                           '\n' + 'created or modified.' +
                           '\n' +
                           '\n')
    age_group.add_argument('--finish', '-f', action='store_true',
                           help='If this flag is set, the minimum age of files to be' +
                           '\n' + 'uploaded is set to zero, forcing all files not yet' +
                           '\n' + 'uploaded to be uploaded. If any tar file created' +
                           '\n' + 'during this or a previous run was not successfully' +
                           '\n' + 'uploaded, the script exits with a non-zero status' +
                           '\n' + 'code. If all tar files created during this or a' +
                           '\n' + 'previous run were successfully uploaded, the file IDs' +
                           '\n' + 'of the uploaded files are printed to standard output.' +
                           '\n' +
                           '\n')

    parser.add_argument('sync_dir', metavar='<directory>', help='Directory to sync.')

    args = parser.parse_args()
    return args

def check_inputs(args):

    # Check required inputs
    if not args.sync_dir:
        sys.exit("kwarg `sync_dir` is required for dx_sync_directory.py")
    if not args.tar_destination:
        sys.exit("kwarg `tar_destination` is required for dx_sync_directory.py")
    if not args.log_file:
        sys.exit("kwarg `log_file` is required for dx_sync_directory.py")
    if not args.prefix:
        sys.exit("kwarg `prefix` is required for dx_sync_directory.py")

    # Set defaults
    if not args.tar_directory:
        args.tar_directory = tempfile.gettempdir()
    if not args.min_tar_size:
        args.min_tar_size = 0
    if not args.max_tar_size:
        args.max_tar_size = 75
    if not args.include_patterns:
        args.include_patterns = []
    if not args.exclude_patterns:
        args.exclude_patterns = []

    # Canonicalize paths
    args.tar_directory = os.path.abspath(args.tar_directory)
    args.log_file = os.path.abspath(args.log_file)
    args.sync_dir = os.path.abspath(args.sync_dir)

    if args.finish:
        args.min_age = 0
        args.min_tar_size = 0

    # Convert min & max sizes to MB
    args.max_tar_size = args.max_tar_size * 2**20
    args.min_tar_size = args.min_tar_size * 2**20
    if args.max_tar_size <= args.min_tar_size:
        sys.exit("--max-tar-size must be greater than --min-tar-size")

    return args

def read_log(args):
    """Reads the log file."""

    print >> sys.stderr, '\n--- Reading log file...'

    if os.path.exists(args.log_file):
        with open(args.log_file, 'r') as logf:
            return json.load(logf)
    else:
        print >> sys.stderr, '  Log file not found, returning empty log.'
        return {'tar_files': {}, 'next_tar_index': 0, 'files': {},
                'tar_destination': args.tar_destination, 'file_prefix': args.prefix,
                'sync_dir': args.sync_dir, 'include_patterns': args.include_patterns,
                'exclude_patterns': args.exclude_patterns}
    return log

def check_log(log, args):
    print >> sys.stderr, ( '\n--- Checking that log matches inputs' )
    try:
        log_sync_dir = log['sync_dir']
        if log_sync_dir != args.sync_dir:
            sys.exit('ERROR: Sync dir specified in input %s does not match sync dir in log %s' %
                     (args.sync_dir, log_sync_dir))

        log_tar_destination = log['tar_destination']
        if log_tar_destination != args.tar_destination:
            sys.exit('ERROR: DNAnexus tar destination specified in input %s does not match log %s' %
                     (args.tar_destination, log_tar_destination))

        log_include = log['include_patterns']
        if not set(log_include) == set(args.include_patterns):
            sys.exit('ERROR: patterns to include (%s) do not match log %s' %
                    (args.include_patterns, log_include))

        log_exclude = log['exclude_patterns']
        if not set(log_exclude) == set(args.exclude_patterns):
            sys.exit('ERROR: patterns to exclude (%s) do not match log %s' %
                     (args.exclude_patterns, log_exclude))

        # Check that log has correct keys
        log_tar_files = log['tar_files']
        log_next_tar_index = log['next_tar_index']
        log_files = log['files']
        log_file_prefix = log['file_prefix']
    except KeyError, e:
        sys.exit('ERROR: Invalid log file. Log does not have "%s" key' % (e))

    return

def get_files_to_upload(log, args):
    """Traverses the directory to be synced, and identifies which
    files should be synced. Exclude files which match patterns to exclude.
    If include_patterns is specified, include only files which match."""

    print >> sys.stderr, "\n--- Getting files to upload in %s ..." % args.sync_dir

    cur_time = int(time.time())
    to_upload = []

    for root, dirs, files in os.walk(args.sync_dir):
        for name in dirs + files:
            full_path = os.path.join(root, name)
            cur_mtime = os.path.getmtime(full_path)

            # Python empty list is false
            if args.exclude_patterns and full_path_matches_pattern(full_path, args.exclude_patterns):
                continue
            if args.include_patterns and not full_path_matches_pattern(full_path, args.include_patterns):
                continue

            if cur_time - cur_mtime > args.min_age:
                if (full_path not in log['files']) or (cur_mtime > log['files'][full_path]['mtime']):
                    to_upload.append(full_path)

    return to_upload

def full_path_matches_pattern(full_path, patterns_list):
    for pattern in patterns_list:
        if re.search(pattern, full_path):
            return True
    return False

def split_into_tar_files(files_to_upload, log, args):
    """Split list so tar files uploaded are not greater than max_tar_size"""

    print >> sys.stderr, "\n--- Splitting into tar files to upload..."

    tars_to_upload = []
    current_tar = {"size": 0, "files": []}
    total_size = 0
    for f in files_to_upload:
        fsize = os.path.getsize(f)
        if current_tar["size"] + fsize > args.max_tar_size:
            tars_to_upload.append(current_tar)
            current_tar = {"size": 0, "files": []}
        current_tar["files"].append(f)
        current_tar["size"] += fsize
        total_size += fsize
    tars_to_upload.append(current_tar)

    if total_size < args.min_tar_size:
        print >> sys.stderr, ('QUITTING: Size of files to upload is not big ' +
                'enough to to be uploaded yet. Please run again later or ' +
                'specify --min-tar-size to be smaller')
        return []

    return tars_to_upload

def create_tar_file(files_to_upload, log, args):
    """Create a tar file containing the given files to be uploaded."""

    if len(files_to_upload["files"]) == 0:
        print >> sys.stderr, "\n--- No files to upload, skipping tar file creation..."
        return log

    tar_filename = "%s_%03d.tar.gz" % (log['file_prefix'], log['next_tar_index'])
    tar_full_path = os.path.join(args.tar_directory, tar_filename)

    print >> sys.stderr, "\n--- Creating tar file %s..." % tar_full_path

    tar_start = time.time()
    tar_file = tarfile.open(tar_full_path, 'w:gz')

    log_updates = {}

    for f_abs in files_to_upload["files"]:
        f_rel = os.path.relpath(f_abs, args.sync_dir)
        tar_file.add(f_abs, arcname=f_rel, recursive=False)
        log_updates[f_abs] = {'mtime': os.path.getmtime(f_abs)}

    tar_file.close()
    tar_end = time.time()

    log['tar_files'][tar_full_path] = {'status': 'tarred',
                                       'size': files_to_upload["size"],
                                       'timestamps': {'tar_start': tar_start,
                                                      'tar_end': tar_end}
                                      }
    log['next_tar_index'] += 1
    for filename in log_updates:
        log['files'][filename] = log_updates[filename]
    return update_log(log, args)

def upload_tar_files(log, args):
    """Uploads any tar files that haven't yet been uploaded"""

    print >> sys.stderr, "\n--- Uploading tar files..."

    tar_destination_project, tar_destination_folder, _ = dxpy.utils.resolver.resolve_path(args.tar_destination, expected='folder')

    upload_count = 0
    for tar_file in log['tar_files']:
        if log['tar_files'][tar_file]['status'] == 'tarred':
            print >> sys.stderr, "Uploading %s to %s:%s..." % (tar_file, tar_destination_project,
                                                                 tar_destination_folder)
            upload_count += 1
            upload_start = time.time()
            if args.dxpy_upload:
                dx_file = dxpy.upload_local_file(tar_file, project=tar_destination_project, folder=tar_destination_folder)
                dx_file_id = dx_file.get_id()
            else:
                opts=''
                if args.upload_threads:
                    opts += '-u %d ' %args.upload_threads
                if args.verbose:
                    opts += '--verbose '

                ua_command = "ua --project %s --folder %s --do-not-compress --wait-on-close --progress %s %s --chunk-size 25M" % (tar_destination_project, tar_destination_folder, opts, tar_file)
                print >> sys.stderr, ua_command
                try:
                    dx_file_id = subprocess.check_output(ua_command, shell=True)
                    dx_file_id = dx_file_id.strip()
                except subprocess.CalledProcessError:
                    sys.exit("ERROR: Tar file %s was not uploaded. Please check log for progress and rerun script" % tar_file)
            upload_end = time.time()

            log['tar_files'][tar_file]['status'] = 'uploaded'
            log['tar_files'][tar_file]['file_id'] = dx_file_id
            log['tar_files'][tar_file]['timestamps']['upload_start'] = upload_start
            log['tar_files'][tar_file]['timestamps']['upload_end'] = upload_end
            log = update_log(log, args)
    if upload_count == 0:
        print >> sys.stderr, "\tNo files uploaded..."
    return log

def remove_tar_files(log, args):
    """Removes tar files that have been uploaded from the local disk."""

    print >> sys.stderr, "\n--- Removing uploaded tar files..."

    remove_count = 0
    for tar_file in log['tar_files']:
        if log['tar_files'][tar_file]['status'] == 'uploaded':
            print >> sys.stderr, "Removing %s..." % tar_file

            remove_count += 1
            remove_start = time.time()
            os.remove(tar_file)
            remove_end = time.time()

            log['tar_files'][tar_file]['status'] = 'removed'
            log['tar_files'][tar_file]['timestamps']['remove_start'] = remove_start
            log['tar_files'][tar_file]['timestamps']['remove_end'] = remove_end
            log = update_log(log, args)

    if remove_count == 0:
        print >> sys.stderr, "\tNo files removed..."

    return log

def print_all_file_ids(log):
    """Outputs the file ID of each tar file that has been uploaded."""

    failed_uploads = 0
    file_ids = []

    for tar_file in log['tar_files']:
        if log['tar_files'][tar_file]['status'] == 'removed':
            file_ids.append(log['tar_files'][tar_file]['file_id'])
        elif log['tar_files'][tar_file]['status'] == 'uploaded':
            print >> sys.stderr, 'WARNING: %s was uploaded but not removed' % tar_file
            file_ids.append(log['tar_files'][tar_file]['file_id'])
        else:
            print >> sys.stderr, 'ERROR: %s was not uploaded' % tar_file
            failed_uploads += 1

    assert failed_uploads >= 0

    if failed_uploads == 0:
        for file_id in file_ids:
            print file_id.strip()
    elif failed_uploads == 1:
        sys.exit('One file was not successfully uploaded.')
    else:
        sys.exit('%s files were not successfully uploaded.' % failed_uploads)

def write_log(log, log_file):
    """Writes the log to the log file."""

    print >> sys.stderr, '\n--- Writing log file...'

    with open(log_file, 'w') as logf:
        json.dump(log, logf)

def update_log(log, args):
    """Write current state of logs"""

    write_log(log, args.log_file)
    return read_log(args)

def main():
    """Main function."""

    args = parse_args()

    print >> sys.stderr, '\nUser Input:\n%s\n' % args

    args = check_inputs(args)

    log = read_log(args)

    check_log(log, args)

    files_to_upload = get_files_to_upload(log, args)

    tars_to_upload = split_into_tar_files(files_to_upload, log, args)

    for tar in tars_to_upload:
        log = create_tar_file(tar, log, args)
        log = upload_tar_files(log, args)
        log = remove_tar_files(log, args)

    # Run through upload & remove in case last invocation was interrupted
    if len(tars_to_upload) == 0:
        log = upload_tar_files(log, args)
        log = remove_tar_files(log, args)

    print_all_file_ids(log)

if __name__ == '__main__':
    main()
