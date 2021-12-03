import datetime
import logging.config
import json
import os
import plistlib
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time
# import urllib.request
from distutils.util import strtobool
from pkg_resources import parse_version
from typing import List, Union

import requests

from actions import erase_device, prepare_device
from db_utils import Query


module_directory = os.path.dirname(os.path.realpath(__file__))


def log_setup(log_name="MAIN"): #, device_log=None, level=logging.INFO):

    class StrippingLogRecord(logging.LogRecord):

        pattern = re.compile(r"objc\[\d+\]: Class AMSupport.+ Which one is undefined\.")

        def getMessage(self):
            message = super(StrippingLogRecord, self).getMessage()
            message = self.pattern.sub("", message)
            return message

    logging.config.fileConfig(
        "/{}/logging_config.ini".format(module_directory), 
        disable_existing_loggers=False
    )
    logging.setLogRecordFactory(StrippingLogRecord)

    return logging.getLogger(log_name)


    # Example
    # try:
    #     # Do Something
    #     pass
    # except OSError as e:
    #     logger.error(e, exc_info=True)
    # except:
    #     logger.error("uncaught exception: %s", traceback.format_exc())





    # main_log_file = "/{}/logs/main.log".format(module_directory)



    # if not logger.hasHandlers():

    #     # Set loggin level
    #     logger.setLevel(logging.DEBUG)

    #     # Create file handler which logs even debug messages
    #     main_file_handler = logging.FileHandler(main_log_file)
    #     main_file_handler.setLevel(level)

    #     # Create console handler with a higher log level
    #     console_handler = logging.StreamHandler()
    #     console_handler.setLevel(logging.DEBUG)

    #     # Create file handler which logs even debug messages
    #     if device_log:
    #         device_file_handler = logging.FileHandler("/{}/logs/{}.log".format(module_directory, log_name))
    #         device_file_handler.setLevel(level)


    #     # Create formatter and add it to the handlers
    #     formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s - %(message)s')
    #     main_file_handler.setFormatter(formatter)
    #     device_file_handler.setFormatter(formatter)
    #     console_handler.setFormatter(formatter)

    #     # Add the handlers to the logger
    #     logger.addHandler(main_file_handler)
    #     logger.addHandler(device_file_handler)
    #     logger.addHandler(console_handler)

    # return logger



# def verbose_output(message, buffer = True):

#     date = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S")
#     tab = "\t" if buffer else ""

#     message = re.sub(r"objc\[\d+\]: Class AMSupport.+ Which one is undefined\.", "", message)
#     print("{}{} | {}".format(tab, date, message))



def report_end_time(device):
    """Updates the database when the device has completed the provisioning process

    Args:
        device:  Object of device's information from the database
    """

    device_logger = log_setup(log_name=device["ECID"])

    # Get current epoch time
    currentTime = time.time()

    # Update status and end time in the database
    with Query() as run:
        run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
            ("done", device["ECID"]))
        run.execute('UPDATE report SET end_time = ? WHERE id = ?', 
            (currentTime, device["id"]))

    # Successfully Prepared device
    device_logger.info("\U0001F7E2 [DONE] Device has been provisioned, it can be unplugged!")


def parse_json(json_data):

    try:
        return json.loads(json_data)

    except:
        return json_data




def check_for_cfgutil_errors(ECID, json_data):

    device_logger = log_setup(log_name=ECID)

    # Get the device's details
    with Query() as run:
        device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
            (ECID,)).fetchone()

    if isinstance(json_data, dict) and ECID in json_data["AffectedDevices"]:
    
        if json_data["Errors"][ECID]["Code"] == -402653030:
            device_logger.warning("\u26A0 Unable to pair with device, erasing...")


            erase_device(device)

        # Error Code 603 / -402653052
        elif json_data["Code"] in { -402653052, 603 }:

            # Device may have successfully Prepared, but was unable to capture that accurately
            device_logger.warning(
                "\u26A0 Unable to determine device state, it will be checked on its next attach")

            # Update status in the database
            with Query() as run:
                run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                    ("check", ECID))

            # print("Exiting...")
            sys.exit(0)

        # # Error Code 33001 / 607
        # elif json_data["Message"] == "The device is not activated.":

        #     device_logger.warning("\u26A0 The device was not activated, trying again.  \n\t\tError:\n{}".format(
        #         json_data["Message"]))

        #     # Attempt to Prepare device (again)
        #     prepare_device(device)


        # elif json_data["Message"] == "The configuration is not available.":

        #     device_logger.warning("\u26A0 Unable to prepare device.  \n\t\tError:  {}".format(
        #         json_data["Message"]))

        #     # Erase device
        #     erase_device(device)




def execute_cfgutil(ECID, command): 

    results = run_utility( "cfgutil --ecid {} --format JSON {}".format(ECID, command))

    if re.match( "cfgutil: error: no devices found", results["stderr"] ):
        print("Exiting...")
        sys.exit(1)

    # Verify success
    if results["success"]:
        # Load the JSON into an Object
        # print("\tReturning session info:  {}".format(results["stdout"]))
        json_data = parse_json(results["stdout"])
        check_for_cfgutil_errors(ECID, json_data)
        return results, json_data["Output"][ECID]
        

# print("\tERROR:  \u26A0 Unable to obtain device info")
# print("\tReturn Code:  {}".format(results["exitcode"]))
# print("\tstdout:  {}".format(results["stdout"]))
# print("\tstderr:  {}".format(results["stderr"]))









def run_utility(command):
    """
    A helper function for subprocess.

    Args:
        command:  The command line level syntax that would be written in a 
        shell script or a terminal window.  (str)

    Returns:
        Results in a dictionary.
    """

    # Validate that command is not a string
    if not isinstance(command, str):
        raise TypeError('Command must be a str type')

    # Format the command
    command = shlex.split(command)

    # Run the command
    process = subprocess.Popen( command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
        shell=False, universal_newlines=True )
    (stdout, stderr) = process.communicate()

    return {
        "stdout": (stdout).strip(),
        "stderr": (stderr).strip() if stderr != None else None,
        "exitcode": process.returncode,
        "success": process.returncode == 0,
    }


def firmware_check(model):
    """Gets the latest compatible firmware version of a iOS, iPadOS, or tvOS Device

    Args:
        model:  Device mode, e.g. "iPad6,11"

    Returns:
        stdout:  latest firmware version as str, e.g. "13.6" or None
    """

    # Create a list to add compatible firmwares too
    all_fw = []

    # Look up current version results
    # response = urllib.request.urlopen("http://phobos.apple.com/version").read()
    # response = urllib.request.urlopen("http://ax.phobos.apple.com.edgesuite.net/WebObjects/MZStore.woa/wa/com.apple.jingle.appserver.client.MZITunesClientCheck/version/").read()
    response = requests.get(
        "http://ax.phobos.apple.com.edgesuite.net/WebObjects/MZStore.woa/wa/com.apple.jingle.appserver.client.MZITunesClientCheck/version/")
    content = plistlib.loads(response.text)

    # Get the dict item that contains the info required
    keys = content.get('MobileDeviceSoftwareVersionsByVersion')

    # Loop through the items in this dict
    for item in keys:

        try:
            # Try to find the supplied in this dict
            firmware_version = keys.get(item).get('MobileDeviceSoftwareVersions').get('{}'.format(
                model)).get("Unknown").get("Universal").get("Restore").get('ProductVersion')

            # Add firmware to list if found
            all_fw.append(firmware_version)

        except:
            pass

    if all_fw:
        # Sort the firmware list so that the newest if item 0 and grab that
        return sorted(all_fw, key=parse_version, reverse=True)[0]

    else:
        return None


def get_disk_usage(disk):
    """Gets the current disk usage properties and returns them

    Args:
        disk:  Which disk to check

    Returns:
        Results in a tuple format (total, used, free)
    """

    # Get the disk usage
    total, used, free = shutil.disk_usage(disk)

    total_human = HumanBytes.format(total, metric=False, precision=1)
    used_human = HumanBytes.format(used, metric=False, precision=1)
    free_human = HumanBytes.format(free, metric=False, precision=1)

    return (total_human, used_human, free_human)


def clean_configurator_temp_dir():
    """Find the Apple Configurator temporary directory where files are
    temporarily extracted and deletes the subdirectories that have not been accessed
    in more than thirty minutes.  This directory can become bloated and is not
    automatically cleaned up by the cfgutil process.
    """

    # print("User Context:  ", os.getlogin())

    # Get the time stamp thirty minutes in the past.
    reference_time = (datetime.datetime.now() - datetime.timedelta(seconds=1800)).timestamp()

    # Walk the directory provided for recipes
    for root, folders, files in os.walk("/private/var/folders"):

        # Loop through the folders to find the desired folder
        for folder in folders:

            # Find the specific folder
            if re.search('com.apple.configurator.xpc.DeviceService', folder):

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
                                is_string_GUID(sub_sub_folder.name) 
                            ):

                                # Delete the directory:
                                print("Deleting temporary directory:  {}".format(
                                    sub_sub_folder.name))
                                shutil.rmtree(sub_sub_folder.path)


# Credit to Mitch McMabers / https://stackoverflow.com/a/63839503
# Slightly modified from source
class HumanBytes:
    """
    HumanBytes returns a string of the supplied file size in human friendly format.

    Returns:
        str: Formatted string
    """
    METRIC_LABELS: List[str] = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    BINARY_LABELS: List[str] = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    PRECISION_OFFSETS: List[float] = [0.5, 0.05, 0.005, 0.0005] # PREDEFINED FOR SPEED.
    PRECISION_FORMATS: List[str] = ["{}{:.0f} {}", "{}{:.1f} {}", "{}{:.2f} {}", "{}{:.3f} {}"] # PREDEFINED FOR SPEED.

    @staticmethod
    def format(num: Union[int, float], metric: bool=False, precision: int=1) -> str:
        """
        Human-readable formatting of bytes, using binary (powers of 1024)
        or metric (powers of 1000) representation.
        """

        assert isinstance(num, (int, float)), "num must be an int or float"
        assert isinstance(metric, bool), "metric must be a bool"
        assert isinstance(precision, int) and precision >= 0 and precision <= 3, "precision must be an int (range 0-3)"

        unit_labels = HumanBytes.METRIC_LABELS if metric else HumanBytes.BINARY_LABELS
        last_label = unit_labels[-1]
        unit_step = 1000 if metric else 1024
        unit_step_thresh = unit_step - HumanBytes.PRECISION_OFFSETS[precision]

        is_negative = num < 0
        if is_negative: # Faster than ternary assignment or always running abs().
            num = abs(num)

        for unit in unit_labels:
            if num < unit_step_thresh:
                # VERY IMPORTANT:
                # Only accepts the CURRENT unit if we're BELOW the threshold where
                # float rounding behavior would place us into the NEXT unit: F.ex.
                # when rounding a float to 1 decimal, any number ">= 1023.95" will
                # be rounded to "1024.0". Obviously we don't want ugly output such
                # as "1024.0 KiB", since the proper term for that is "1.0 MiB".
                break
            if unit != last_label:
                # We only shrink the number if we HAVEN'T reached the last unit.
                # NOTE: These looped divisions accumulate floating point rounding
                # errors, but each new division pushes the rounding errors further
                # and further down in the decimals, so it doesn't matter at all.
                num /= unit_step

        return HumanBytes.PRECISION_FORMATS[precision].format("-" if is_negative else "", num, unit)


def is_string_GUID(possible_GUID):
    """Validates is a passed string is in a valid GUID formart (Globally Unique Identifier).

    Args:
        possible_GUID:  A string that will be tested to be in a GUID format

    Returns:
        True or false
    """

    # Regex thto match the GUID Format
    regex_GUID_format = "^[{]?[0-9a-fA-F]{8}" + "-([0-9a-fA-F]{4}-)" + "{3}[0-9a-fA-F]{12}[}]?$"

    # Compile the regex
    pattern = re.compile(regex_GUID_format)

    # If the string is empty return false
    if possible_GUID == None:
        return False

    # Return if the string matched the regex
    if re.search(pattern, possible_GUID):

        return True

    else:
        return False


def query_user_yes_no(question):
    """Ask a yes/no question via input() and determine the value of the answer.

    Args:
        question:  A string that is written to stdout

    Returns:
        True or false based on the users' answer.
    """

    print('{} [Yes/No] '.format(question), end="")

    while True:

        try:

            return strtobool(input().lower())

        except ValueError:

            print('Please respond with [yes|y] or [no|n]: ', end="")
