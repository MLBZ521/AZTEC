#!/bin/sh

# Get the scripts current directory
script_directory="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
# Get the scripts parent directory
parent_directory="$( /usr/bin/dirname "${script_directory}" )"

cd "${parent_directory}" && /opt/ManagedFrameworks/Python.framework/Versions/Current/bin/python3 -m AZTEC.detach
