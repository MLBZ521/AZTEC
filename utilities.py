import datetime
import os
import plistlib
import re
import shlex
import shutil
import subprocess
import urllib.request
from distutils.util import strtobool
from pkg_resources import parse_version
from typing import List, Union


def runUtility(command):
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

    result_dict = {
        "stdout": (stdout).strip(),
        "stderr": (stderr).strip() if stderr != None else None,
        "exitcode": process.returncode,
        "success": True if process.returncode == 0 else False
    }

    return result_dict


def firmware_check(model):
    """Gets the latest compatible firmware version of a iOS, iPadOS, or tvOS Device

    Args:
        model:  Device mode, e.g. "iPad6,11"

    Returns:
        stdout:  latest firmware version as str, e.g. "13.6"
    """

    # Create a list to add compatible firmwares too
    all_fw = []

    # Look up current version results
    response = urllib.request.urlopen("http://phobos.apple.com/version").read()

    # Read the plist response
    content = plistlib.loads(response)

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

    if len(all_fw) > 0:

        # Sort the firmware list so that the newest if item 0 and grab that
        latest_firmware = sorted(all_fw, key=parse_version, reverse=True)[0]

        return latest_firmware

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

    # Get the time stamp thirty minutes in the past.
    reference_time = (datetime.datetime.now() - datetime.timedelta(seconds=-1800)).timestamp()

    # Walk the directory provided for recipes
    for root, folders, files in os.walk("/private/var/folders"):

        # Loop through the folders to find the desired folder
        for folder in folders:

            # Find the specific folder
            if re.search('com.apple.configurator.xpc.DeviceService', folder):

                # Loop through the folders to find the desired folder
                for folder in os.scandir(os.path.join(root, folder)):

                    # Confirm item is a folder and check the name
                    if folder.is_dir() and folder.name == "TemporaryItems":

                        # Loop through the sub folders
                        for folder in os.scandir(folder.path):

                            # Again, confirm item is a folder and check it's last access time
                            if folder.is_dir() and os.path.getatime(folder) < reference_time and is_string_GUID(folder.name):

                                # Delete the directory:
                                print("Deleting temporary directory:  {}".format(folder.name))
                                shutil.rmtree(folder.path)


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
