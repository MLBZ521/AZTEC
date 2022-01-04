import datetime
import os
import re
import shutil
import stat
import sys

from AZTEC import utilities
from AZTEC.actions import erase_device
from AZTEC.db_utils import Query


def execute(ECID, command):
    """Helper function for the cfgutil binary.

    Args:
        ECID (str): ECID of a device
        command (str): the switch (and optional values) to execute

    Returns:
        results (dict):  Dict of values from utilities.execute_process
        json_data (dict):  Dict object parsed from the utilities.execute_process["stdout"] key
    """

    device_logger = utilities.log_setup(log_name=ECID)

    results = utilities.execute_process("cfgutil --ecid {} --format JSON {}".format(ECID, command))

    if re.match( "cfgutil: error: no devices found", results["stderr"] ):
        sys.exit(1)

    # Verify success
    if not results["success"]:
        device_logger.error(
            "Return Code:  {}\nstdout:  {}\nstderr:  {}".format(
                results["exitcode"], results["stdout"], results["stderr"]))

    # Load the JSON into an Object
    json_data = utilities.parse_json(results["stdout"])
    # device_logger.debug("cfgutil > execute > json_data:  {}".format(json_data))
    check_for_errors(ECID, json_data)
    
    try:
        return results, json_data["Output"][ECID]
    except:
        return results, json_data


def check_for_errors(ECID, json_data):
    """Checks the output from a `cfgutil --format JSON` command against known error codes.
    If an error was present for the provided ECID, an appropriate action is taken.

    Args:
        ECID (str): ECID of a device
        json_data (dict): json dict to parse
    """

    device_logger = utilities.log_setup(log_name=ECID)

    # Get the device's details
    with Query() as run:
        device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
            (ECID,)).fetchone()

    # try:

    if isinstance(json_data, dict):

        if (
            "AffectedDevices" in json_data.keys() and 
            ECID in json_data["AffectedDevices"]
        ):

            if json_data["Code"] == 401:
                device_logger.error(
                    "\u26A0\U0001F6D1\u26A0 Mac is out of date!\nError Message:  {}".format(
                        json_data["Message"]))
                sys.exit(1)

            # Error Code:  33001 / 607?
            elif json_data["Code"] == 33001:
                # Message: "The configuration is not available."

                device_logger.warning(
                    "\u26A0 Failed to prepare device, trying again.\n\t\tError:\n{}".format(
                    json_data["Message"]))

                # Erase device
                erase_device(device)

            # Error Code:  ?
            elif json_data["Message"] == "The device is not activated.":

                device_logger.warning(
                    "\U0001F6D1 Unable to prepare device.  \n\t\tError:  {}".format(
                    json_data["Message"]))

                # Erase device
                erase_device(device)

            # Error Code:  ?
            elif ( json_data["Message"] == 
                "The device is already prepared and must be erased to change settings." ):

                # If the device was already prepared, erase it
                device_logger.info("Device was already prepared, erasing it...")

                # Erase device
                erase_device(device)

            else:

                # Unknown error, erase and try again
                device_logger.warning(
                    "\U0001F6D1 Unaccounted for failure.  Error was:\n{}".format(json_data))
                
                # Erase device
                erase_device(device)

        elif (
            utilities.keys_exists(json_data, "Output", "Errors", ECID) and 
            bool(json_data["Output"]["Errors"][ECID])
        ):

            json_data = json_data["Output"]["Errors"]

            if json_data[ECID]["Code"] == -402653030:
                device_logger.warning("\u26A0 Unable to pair with device, erasing...")

                # Erase device
                erase_device(device)

                # or:
                # device_logger.info(
                #     "Policy prevents device from pairing with this computer, no futher information can be gathered!")

                # Add the end time to the database
                # device.report_end_time(device)

            # Error Code 603 / -402653052
            elif json_data[ECID]["Code"] in { -402653052, 603 }:

                # Device may have successfully Prepared, but was unable to capture that accurately
                device_logger.warning(
                    "\u26A0 Unable to determine device state, it will be reevaluated on next attach")

                # Update status in the database
                with Query() as run:
                    run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                        ("check", ECID))

                sys.exit(0)

    # except:
    #     device_logger.debug("check_for_errors > json_data:  {}".format(json_data))
    #     device_logger.error("Failed to parse the json_data for errors!\nError was:\n{}\n\nExiting".format(traceback.format_exc()))
    #     sys.exit(1)


def clean_configurator_temp_dir():
    """Find the Apple Configurator temporary directory where files are
    temporarily extracted and deletes the subdirectories that have not been accessed
    in more than thirty minutes.  This directory can become bloated and is not
    automatically cleaned up by the cfgutil process.
    """

    main_logger = utilities.log_setup()

    # Get the time stamp thirty minutes in the past.
    reference_time = (datetime.datetime.now() - datetime.timedelta(seconds=1800)).timestamp()

    # Walk the directory provided for recipes
    for root, folders, files in os.walk("/private/var/folders"):

        # Loop through the folders to find the desired folder
        for folder in folders:

            # Find the specific folder
            if re.search('com.apple.configurator.xpc.DeviceService', folder):

                os.chmod(os.path.join(root, folder), stat.S_IRWXU | stat.S_IRGRP | stat.S_IWGRP)

                # Loop through the folders to find the desired folder
                for sub_folder in os.scandir(os.path.join(root, folder)):

                    # Confirm item is a folder and check the name
                    if sub_folder.is_dir() and sub_folder.name == "TemporaryItems":

                        # Change permissions so that the group can read the folder
                        os.chmod(sub_folder.path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IWGRP)

                        # Loop through the sub folders
                        for sub_sub_folder in os.scandir(sub_folder.path):

                            # Again, confirm item is a folder and check it's last access time
                            if ( sub_sub_folder.is_dir() and 
                                os.path.getatime(sub_sub_folder) < reference_time and 
                                utilities.is_string_GUID(sub_sub_folder.name) 
                            ):

                                # Delete the directory:
                                main_logger.info("Deleting temporary directory:  {}".format(
                                    sub_sub_folder.name))
                                shutil.rmtree(sub_sub_folder.path)
