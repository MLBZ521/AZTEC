import datetime
import json
import logging.config
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import threading

from distutils.util import strtobool
from typing import List, Union

from logging_config import (
    LOGGING_CONFIG_DEVICE_HANDLER, 
    LOGGING_CONFIG_DEVICE_LOGGER, 
    LOGGING_CONFIG_MAIN
)


module_directory =  os.path.dirname(os.path.abspath(__file__))
package_directory = pathlib.Path(__file__).parent.absolute().parent.absolute()
log_directory = "{}/logs".format(package_directory)


class Periodic(threading.Thread):
    """Creates a background job (thread) that runs periodically."""

    def __init__(self, /, function, interval=60, iterations=0, **kwargs):
        threading.Thread.__init__(self)

        self.function = function
        self.interval = kwargs.get("interval", interval)
        self.iterations = kwargs.get("iterations", iterations)
        self.kwargs = kwargs
        self.fn_kwargs = kwargs.get("fn_kwargs", {})
        self.finished = kwargs.get("event")
        self.count = 0


    def run(self):
        """Runs when the class is executed."""

        try:

            while not self.finished.is_set() and (
                self.iterations <= 0 or self.count < self.iterations
            ):
                self.finished.wait(self.interval)
                self.function(**self.fn_kwargs)
                self.count += 1

        except KeyboardInterrupt:
            print("utilities > Closing background thread...")
            self.cancel()

    def cancel(self):
        """Runs when the class is canceled/closed."""

        print("Background thread canceled!")
        self.finished.set()


def log_backup():
    """Backs up the log directory for future review."""

    if os.path.exists(log_directory):

        format_string = "%Y-%m-%d %I.%M.%S"
        formatted_time = datetime.datetime.fromisoformat(str(datetime.datetime.now()))
        time_stamp = formatted_time.strftime(format_string)
        os.rename(log_directory, "{}_{}".format(log_directory, time_stamp))


def log_setup(log_name="main"): # level=logging.INFO):
    """Sets up a logger to handle logging messages for the AZTEC process.

    Multiple log files are created:
        main:  This is the parent log (and console) that all information is posted too
        <device>:  Each device will have its own log for easier parsing for device specific errors

    Args:
        log_name ([str], optional): A log to write too. Defaults to "main"
            If not main, a device ECID should be passed to create a device specific log

    Returns:
        [logger]: A logger object
    """

    class StrippingLogRecord(logging.LogRecord):
        """A class that is used to strip undesired information from the
        provided text in a message before it is written to a log.

        Args:
            logging (LogRecord): The message to parse

        Returns:
            str: The parsed message
        """

        pattern = re.compile(r"objc\[\d+\]: Class AMSupport.+ Which one is undefined\.")

        def getMessage(self):
            message = super(StrippingLogRecord, self).getMessage()
            message = self.pattern.sub("", message)
            return message


    if not os.path.exists(log_directory):
        os.mkdir(log_directory)

    LOGGING_CONFIG_MAIN.get("handlers").get("main").update(
        { "filename": "{}/main.log".format(log_directory) } )

    if log_name not in ( None, "main" ):

        if "device" in LOGGING_CONFIG_DEVICE_LOGGER.keys():
            LOGGING_CONFIG_DEVICE_LOGGER[log_name] =  LOGGING_CONFIG_DEVICE_LOGGER.pop("device")

        LOGGING_CONFIG_DEVICE_HANDLER.get("device").update(
            { "filename": "{}/{}.log".format(log_directory, log_name) } )
        LOGGING_CONFIG_MAIN.get("handlers").update(LOGGING_CONFIG_DEVICE_HANDLER)
        LOGGING_CONFIG_MAIN.get("loggers").update(LOGGING_CONFIG_DEVICE_LOGGER)
        LOGGING_CONFIG_MAIN.get("loggers").get("main").get("handlers").append("device")

    logging.config.dictConfig(LOGGING_CONFIG_MAIN)

    logging.setLogRecordFactory(StrippingLogRecord)

    return logging.getLogger(log_name)


def parse_json(json_data):
    """Parses the provided str as a json/dict object.

    Args:
        json_data (str): A json formatted string

    Returns:
        dict or str: If the provided arg is a json formatted string, a dictionary is returned,
            otherwise the string itself is returned
    """
    try:
        return json.loads(json_data)

    except:
        print("*** Expected JSON Data is not JSON data?!?  Data is:\n{}\n".format(json_data))
        return json_data


def keys_exists(element, *keys):
    """
    Check if *keys (nested) exists in `element` (dict).

    Credit:  Arount
    Source:  https://stackoverflow.com/a/43491315
    Notes:  Slightly modified from source

    Args:
        element (dict): A dictionary (e.g. JSON data)
        keys (str(s)): Strings of potentionally nested keys 
            from top-down in the element's structure

    Returns:
        boolean

    """

    if not isinstance(element, dict):
        raise AttributeError('keys_exists() expects dict as first argument.')

    if len(keys) == 0:
        raise AttributeError('keys_exists() expects at least two arguments, one given.')

    _element = element

    for key in keys:

        try:
            _element = _element[key]

        except KeyError:
            return False

    return True


class HumanBytes:
    """
    HumanBytes returns a string of the supplied file size in human friendly format.

    Credit:  Mitch McMabers
    Source:  https://stackoverflow.com/a/63839503
    Notes:  Slightly modified from source

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


def get_disk_usage(disk):
    """Gets the current disk usage properties and returns them.

    Args:
        disk (str):  Which disk to check

    Returns:
        (tuple): Results in a tuple format (total, used, free)
    """

    # Get the disk usage
    total, used, free = shutil.disk_usage(disk)

    total_human = HumanBytes.format(total, metric=False, precision=1)
    used_human = HumanBytes.format(used, metric=False, precision=1)
    free_human = HumanBytes.format(free, metric=False, precision=1)

    return (total_human, used_human, free_human)


def is_string_GUID(possible_GUID):
    """Validates is a passed string is in a valid GUID formart (Globally Unique Identifier).

    Args:
        possible_GUID (str):  A string that will be tested to be in a GUID format

    Returns:
        True or false
    """

    # Regex to match the GUID Format
    regex_GUID_format = "^[{]?[0-9a-fA-F]{8}" + "-([0-9a-fA-F]{4}-)" + "{3}[0-9a-fA-F]{12}[}]?$"

    # Compile the regex
    pattern = re.compile(regex_GUID_format)

    # If the string is empty return false
    if possible_GUID is None:
        return False

    # Return if the string matched the regex
    return bool(re.search(pattern, possible_GUID))


def query_user_yes_no(question):
    """Ask a yes/no question via input() and determine the value of the answer.

    Args:
        question (str):  A string that is written to stdout

    Returns:
        True or false based on the users' answer
    """

    print('{} [Yes/No] '.format(question), end="")

    while True:

        try:

            return strtobool(input().lower())

        except ValueError:

            print('Please respond with [yes|y] or [no|n]: ', end="")


def execute_process(command):
    """
    A helper function for subprocess.

    Args:
        command (str):  The command line level syntax that would be written in a 
            shell script or a terminal window

    Returns:
        dict:  Results in a dictionary
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
        "success": process.returncode == 0
    }
