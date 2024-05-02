#!/bin/bash
set -e

RED="\e[31m"
YELLOW="\e[33m"
NC="\e[0m"

logFp=$1
name=$2

# echo Catched arguments
# echo "logFp=\"${logFp}\""
# echo "name=\"${name}\""
# echo -----------------


usage() {
    printf "Usage: viewlogs PATH TEXT\n"
    printf "\nView logs of monitor_runs.py in with highlight text\n"
    printf "To be noted, the script always highlights with case-insensitive matched strings.\n"
    printf "Arguments:\n"
    printf "\n    PATH         \tLocal Path to Monitor Log File\n"
    printf "\n    TEXT         \tAvailable Options\n"
    printf "\n                     \t- \"dx_sync_directory.py\""
    printf "\n                     \t- \"incremental_upload.py\""
    printf "\n                     \t- \"monitor_runs.py\""
    printf "\n                     \t- \"all\""
    printf "\n                  \tWhen \"all\" is set, it highlights the other 3 options."
    printf "\n                  \tWhen another value is set, it highlights the value only."
    printf "\n\n"
}

validation() {
    if [[ -z $logFp ]]; then
        printf "${RED}ERROR: The command expects the 1st argument is the path to log file${NC}\n"
        usage
        exit 1
    fi

    if [[ -z $name ]]; then
        printf "${RED}ERROR: The command expects the 2nd argument is the highlighted text${NC}\n"
        usage
        exit 1
    fi
}

main() {
    log_dir=$(dirname "$logFp")
    log_basename=$(basename "$logFp")
    log_full_fp="$log_dir/$log_basename"

    # Wait for log file to appear (timeout is 10 minutes)
    for i in $(seq 1 120); do
        if [[ -f "$log_full_fp" ]]; then
            # shellcheck disable=SC2183
            printf "%*s\n" 25 | tr ' ' '-'
            printf "| LOG VIEW\n"
            # shellcheck disable=SC2183
            printf "%*s\n" 25 | tr ' ' '-'
            if [[ $name == all ]]; then
                tail -n +1 -f $logFp | grep --color=always -i \
                    -e "^\|error" -e "^\|exception" -e "^\|warning"  -e "^\|traceback" \
                    -e "^\|%\scomplete" -e "^\|uploaded" -e "^\|closed" \
                    -e "^\|\[monitor_runs.py\]" \
                    -e "^\|\[incremental_upload.py\]" \
                    -e "^\|\[dx_sync_directory.py\]" 
            else
                tail -n +1 -f $logFp | grep --color=always -i \
                    -e "^\|error" -e "^\|exception" -e "^\|warning"  -e "^\|traceback" \
                    -e "^\|%\scomplete" -e "^\|uploaded" -e "^\|closed" \
                    -e "^\|$name"
            fi
        else
            printf "(i=${i}) Waiting for log file to appear ... sleep 5 secs\n"
            sleep 5
        fi    
    done

    if [ ! -f "$log_full_fp" ]; then
        printf "${RED}ERROR: File does not exist: ${logFp}${NC}\n"
        exit 1
    fi

}

validation
main

# viewlogs ~/monitor_run-folder-a.log dx_sync_directory