#!/usr/bin/env python3

import os

import db_utils
import utilities


def main():

    print("\n__Automated Zero Touch Enrollment Configurator__\n")

    total, used, free = utilities.get_disk_usage("/")

    print("Total Disk Space:  {}".format(total))
    print("Available Disk Space:  {}\n".format(free))

    utilities.clean_configurator_temp_dir()

    # Check if the database file currently exists
    if os.path.isfile("devices.db"):
        results = utilities.query_user_yes_no("The devices database already exists, would you like to purge the existing content?")

        if results:
            print("Purging previous content...")
            db_utils.init_db("devices.db")

    else:
        db_utils.init_db("devices.db")

    print("\nStarting the main process...\n")
    print("System ready to accept devices!\n")
    utilities.runUtility( "cfgutil exec --on-attach ./sh-attach.sh --on-detach ./sh-detach.sh" )


if __name__ == "__main__":
    main()
