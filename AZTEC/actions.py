import re
import sys
import time

from AZTEC import cfgutil, utilities
from AZTEC.db_utils import Query
from AZTEC.device import create_or_update_record, report_end_time


def has_not_booted(device):
    """Checks the devices reported Boot State and returns whether it has booted or not.

    Args:
        device (dict):  Object of device's information from the database

    Returns:
        bool: Returns boolean value if the device has booted
            True:  Device has not yet booted
            False:  Device has "booted"
                NOTE: while cfgutil may report a device as "booted"
                it may not have _actually_ finished booting.
    """

    device_logger = utilities.log_setup(log_name=device["ECID"])

    def sleep_return(sleep_time, result):
        """Sleeps the returns a value.

        Args:
            sleep_time (int): Number of seconds to sleep
            result (any): Any value

        Returns:
            any: Any value
        """

        time.sleep(sleep_time)
        return result


    if device["bootedState"] == "Recovery":
        device_logger.warning("\u26A0 Device is currently booted to Recovery Mode (DFU)...")
        return sleep_return(0, False)

    elif device["bootedState"] == "Restore":
        device_logger.info("\u26A0 Device is currently being restored...")
        return sleep_return(10, True)

    elif device["bootedState"] == "Booted":
        device_logger.debug("Device has booted...")
        return sleep_return(0, False)

    elif device["bootedState"] != "Booted":
        device_logger.info("\u23F3 Waiting for device to boot...")
        device_logger.info("Current state is:  {}".format(device["bootedState"]))
        return sleep_return(5, True)

    return sleep_return(10, True)


def erase_device(device):
    """Erases the provided device object.

    Args:
        device (dict):  Object of device's information from the database
    """

    device_logger = utilities.log_setup(log_name=device["ECID"])

    # Erase Device
    device_logger.info("\u2620 To proceed, the device will be erased!")
    device_logger.info(
        "\u26A0\u26A0\u26A0 *** You have five seconds to remove the device before it is wiped! *** \u26A0\u26A0\u26A0")

    # Update status in the database
    with Query() as run:
        run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
            ("erase_warning", device["ECID"]))

    time.sleep(5)
    device_logger.info("\U0001F4A3 Erasing device...")

    results_erase, json_data = cfgutil.execute(device["ECID"], "erase")

    # Verify success
    if results_erase["success"]:

        # Update status in the database
        with Query() as run:
            run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                ("erasing", device["ECID"]))

    elif re.match( "cfgutil: error: no devices found", results_erase["stderr"]):
# Probably will never run again...
        device_logger.info("\U0001F605 Disaster averted, device was not erased!")

    else:
        device_logger.error(
            "\U0001F6D1 Failed to erase the device\nReturn Code {}\nstderr:  {}".format(
                results_erase["exitcode"], results_erase["stderr"]))


def prepare_device(device):
    """Prepares the provided device.

    Args:
       device (dict):  Object of device's information from the database
    """

    device_logger = utilities.log_setup(log_name=device["ECID"])

    if device["status"] == "erased":
        device_logger.info("\u23F3 Waiting for device to finish booting...")

# Still needed?
        # Sleep while the device erases and starts back up
        time.sleep(70)

    device_logger.info("\u2699 Preparing")

    # Update status in the database
    with Query() as run:
        run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
            ("preparing", device["ECID"]))

    results_prepare, json_data = cfgutil.execute(
        device["ECID"], "prepare --dep --language en --locale en_US")

    # Verify success
    if results_prepare["success"]:

        # Add the end time to the database
        report_end_time(device)


def restore_device(device):
    """Erases and updates the provided device object.

    Args:
        device (dict):  Object of device's information from the database
    """

    device_logger = utilities.log_setup(log_name=device["ECID"])

    # Erase Device
    device_logger.info("\u2620 To proceed, the device will be erased!")
    device_logger.info(
        "\u26A0\u26A0\u26A0 *** You have five seconds to remove the device before it is wiped! *** \u26A0\u26A0\u26A0")

    # Update status in the database
    with Query() as run:
        run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
            ("erase_warning", device["ECID"]))

    time.sleep(5)

    # Update device using Restore, which will also erase it
    device_logger.info("\U0001F4A3 Erasing and updating device...")
    results_restore, json_data = cfgutil.execute(device["ECID"], "restore")

    # Verify success
    if not results_restore["success"]:
        device_logger.error(
            "\U0001F6D1 Failed to restore device from Recovery Mode\nReturn Code {}\nstderr:  {}".format(
            results_restore["exitcode"], results_restore["stderr"]))
        print("Attempted to restore device; results were:\n{}".format(json_data))

        if ( json_data["Message"] == 
            "This action cannot be performed on the device while it is already in use." ):

            device_logger.warning(
                "\u26A0 Device is already performing another command.\n\t\tError:  {}\n[NOTICE] Exiting this thread.".format(
                json_data["Message"]))
            sys.exit(0)

        else:

            while has_not_booted(device):
                device = create_or_update_record(device["ECID"])

            # # Erase device
            # erase_device(device)

            # Update status in the database
            # with Query() as run:
            #     results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
            #         ("error", device['ECID']))

    else:

        # Update status in the database
        with Query() as run:
            results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                ("erased", device["ECID"]))

        # Prepare Device
        prepare_device(device)
