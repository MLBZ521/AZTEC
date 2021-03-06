#!/opt/ManagedFrameworks/Python.framework/Versions/Current/bin/python3

import argparse
import os
import threading

from distutils.util import strtobool

from AZTEC import cfgutil, utilities
from AZTEC.db_utils import init_db


def main():
    """Starts the main AZTEC process"""

    ##################################################
    # Define Script Parameters

    parser = argparse.ArgumentParser(
        description="This script utilizes the Apple Configurator CLI Tools (`cfgutil`) to automate the provisioning process of Apple Devices.")
    parser.add_argument(
        "--database", "-d", 
        default="devices.db", 
        help="Specify a database file to create or use if it already exists.", 
        required=False)
    parser.add_argument("--reset", "-r", 
        choices=("true", "false", "yes", "y", "no", "n"),
        help="If the specified database already exists, optionally purge the devices table.", 
        required=False,
        type=str.lower)

    args, unknown = parser.parse_known_args()

    print("\n__{b}A{e}utomated {b}Z{e}ero {b}T{e}ouch {b}E{e}nrollment {b}C{e}onfigurator__\n".format(
        b="\033[1m", e="\033[0m"))

    # Get disk space metrics for verbosity
    total, used, free = utilities.get_disk_usage("/")
    print("Total Disk Space:  {}".format(total))
    print("Available Disk Space:  {}\n".format(free))

    # Check if the database file currently exists
    if os.path.isfile(args.database):
        reset = True

        if args.reset is None:
            reset = utilities.query_user_yes_no(
            "The devices database already exists, would you like to purge the existing content?")

        if not strtobool(args.reset.lower()):
            reset = False

        if strtobool(args.reset.lower()) and reset:
            print("Purging previous content...\n")
            init_db(args.database)

            # Back up previous log files
            utilities.log_backup()

    else:

        init_db(args.database)

    try:

        print("Setting up temporary file clean up job in the background...")
        event = threading.Event()
        background_job = utilities.Periodic(
            function = cfgutil.clean_configurator_temp_dir, 
            interval = 300, 
            event = event
        )
        background_job.start()

        print("\nStarting the main process...\n")
        print("System ready to accept devices!\n")

        utilities.execute_process(
            "cfgutil exec --on-attach '{path}/sh-attach.sh' --on-detach '{path}/sh-detach.sh'".format(
                path = utilities.module_directory
            ) 
        )

        background_job.cancel()

    except KeyboardInterrupt:

        print("Canceling background job...")
        background_job.cancel()


if __name__ == "__main__":
    main()
