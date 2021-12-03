# import os
# import random
import re
import sys
import time

import utilities
from db_utils import Query
from device import create_or_update_record


def has_not_booted(device):
    """
    OR instead of checking checking bootedState again; just use device["bootedState"]

    """

    device_logger = utilities.log_setup(log_name=device["ECID"])

    # Get the devices' boot state
    # results_booted_state, json_data = utilities.execute_cfgutil(device["ECID"], "get bootedState")
    # # print(results_booted_state)

    # # Verify success
    # if not results_booted_state["success"]:
    #     device_logger.error("\U0001F6D1 Failed to get devices boot state!\nReturn Code {}\nstderr:  {}".format(results_booted_state["exitcode"], results_booted_state["stderr"]))
    #     # device_logger.error("Return Code {}".format(results_booted_state["exitcode"]))
    #     # device_logger.error("{}".format(results_booted_state["stderr"]))
    #     # Hard exiting for now, until a reason not to is discovered.
    #     sys.exit(2)
    #     # return True

    # # else:

        # json_results_booted_state = utilities.parse_json(results_booted_state["stdout"])
        # print(json_data["bootedState"])

        # if isinstance(json_results_booted_state, dict):

    if device["bootedState"] == "Recovery":
        device_logger.warning("\u26A0 Device is currently booted to Recovery Mode (DFU)...")
        # restore_device(device)
        return False
        # sys.exit(0)

    elif device["bootedState"] == "Restore":
        device_logger.info("\u26A0 Device is currently being restored...")
        time.sleep(10)
        return True
        # sys.exit(0)

    elif device["bootedState"] == "Booted":
        device_logger.info("Device has booted...")
        return False

    elif device["bootedState"] != "Booted":
        device_logger.info("\u23F3 Waiting for device to boot...")
        time.sleep(5)
        return True

        # else:

        #     device_logger.error("\U0001F6D1 Failed to get devices boot state...  Error was:\n{}".format(json_results_booted_state))

    return True


def erase_device(device):
    """Erases the provided device object.

    Args:
        device:  Object of device's information from the database
    """

    # try:
    #     identifier = device["serialNumber"]

    # except KeyError:
    #     identifier = device["ECID"]

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

    results_erase, json_data = utilities.execute_cfgutil(device["ECID"], "erase")

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
        # device_logger.error("\t{}".format(re.sub(r"objc\[\d+\]: Class AMSupport.+ Which one is undefined\.", "", results_erase["stderr"])))


def prepare_device(device):
    """Prepares the provided device

    Args:
        ECID:  Object of device's information from the database
    """

    device_logger = utilities.log_setup(log_name=device["ECID"])

    # Get the device's details
    # with Query() as run:
    #     device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
    #         (device["ECID"],)).fetchone()

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

    results_prepare, json_data = utilities.execute_cfgutil(
        device["ECID"], "prepare --dep --language en --locale en_US")

    # print("\tresults_prepare > success {}".format(results_prepare["success"]))
    # print("\tresults_prepare > Return Code {}".format(results_prepare["exitcode"]))
    # print("\tresults_prepare > stdout{}".format(results_prepare["stdout"]))
    # print("\tresults_prepare > stderr:  {}".format(results_prepare["stderr"]))

    # Verify success
    if results_prepare["success"]:

        # Add the end time to the database
        utilities.report_end_time(device)

    else:

        if re.match("The device is not activated.", results_prepare["stdout"]):
#DO SOMETHING HERE????
            device_logger.warning(
                "\u26A0 The device was not activated, trying again.  \n\t\tError:\n{}".format(
                results_prepare["stdout"]))

            # Attempt to Prepare device (again)
            prepare_device(device)

        # try:
        # json_prepare_results = utilities.parse_json(results_prepare["stdout"])

        # if isinstance(json_prepare_results, dict):

            # Verify results apply to the same device in error output
            if json_data["Code"] == -402653030 and device['ECID'] in json_data["AffectedDevices"]:

                device_logger.info(
                    "Policy prevents device from pairing with this computer, no futher information can be gathered!")

                # Add the end time to the database
                # print("prepare_device > report_end_time:  pairing prevented")
                utilities.report_end_time(device)

            # elif json_data["Message"] == ( "The device is not connected." or
            #         "This device is no longer connected." ):
                # Error Code 603 / -402653052
            # elif json_data["Code"] in { -402653052, 603 } and device['ECID'] in json_data["AffectedDevices"]:

            #     # Device may have successfully Prepared, but was unable to capture that accurately
            #     device_logger.warning("\u26A0 Unable to determine device state, it will be checked on its next attach")

            #     # Update status in the database
            #     with Query() as run:
            #         results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
            #             ("check", device["ECID"]))

            #     # print("Exiting...")
            #     sys.exit(0)

            # Error Code 33001 / 607
            elif json_data["Message"] == "The device is not activated.":

                device_logger.warning(
                    "\u26A0 The device was not activated, trying again.  \n\t\tError:\n{}".format(
                    json_data["Message"]))

                # Attempt to Prepare device (again)
                prepare_device(device)

            elif json_data["Message"] == "The configuration is not available.":

                device_logger.warning("\u26A0 Unable to prepare device.  \n\t\tError:  {}".format(
                    json_data["Message"]))

                # Erase device
                erase_device(device)

            elif ( json_data["Message"] == 
                "The device is already prepared and must be erased to change settings." ):

                # If the device was already prepared, erase it
                device_logger.info("Device was already prepared, erasing it...")
                # # If the device was already prepared, continue on
                # device_logger.info("Device is supervised and prepared!")

                # Erase device
                erase_device(device)

                # Update status in the database
                # with Query() as run:
                #     results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                #         ("done", device["ECID"]))

                # print("prepare_device > report_end_time: done")
                # utilities.report_end_time(device)

            else:

                # If the device failed to prepare, erase and try again
                device_logger.warning("\u26A0 Unaccounted for prepare failure!")
    ##### Dev/Debug output (to be removed) 
                # print("Unknown failure.  Error information:")
                print("results_prepare > stdout:  ", results_prepare["stdout"])
                print(
                    "results_prepare > stderr:  ".format(
                        re.sub(r"objc\[\d+\]: Class AMSupport.+ Which one is undefined\.", "", results_prepare["stderr"])))

                # Erase device
                erase_device(device)

    #         except:
    #             # Catch all other unknown errors

    # ##### Dev/Debug output (to be removed)
    #             print("Exception Error information:")
    #             print("stdout:  ", results_prepare["stdout"])
    #             print("stderr:  ", results_prepare["stderr"])

    #             # Erase device
    #             erase_device(device)
        else:

            device_logger.error(
                "\U0001F6D1 Failed prepare device for unknown reason...  Error was:\n{}".format(
                    json_data))


def restore_device(device):
    """Erases and updates the provided device object.

    Args:
        device:  Object of device's information from the database
    """

    device_logger = utilities.log_setup(log_name=device["ECID"])

    # try:
    #     identifier = device["serialNumber"]
    #     in_queue=True

    # except KeyError:
    #     identifier = device["ECID"]
    #     in_queue=False

    # Update device using Restore, which will also erase it
    device_logger.info("\U0001F4A3 Erasing and updating device...")

    # delay = random.randrange(10, 200)
    # print("Random Delay before restore:  {}".format(delay))
    # time.sleep(delay)

    # results_restore = utilities.run_utility( 
    #     "cfgutil -vvvv --format JSON --ecid {} restore".format(device["ECID"]) )

    results_restore, json_data = utilities.execute_cfgutil(device["ECID"], "restore")

    # Verify success
    if not results_restore["success"]:
        device_logger.error(
            "\U0001F6D1 Failed to restore device from Recovery Mode\nReturn Code {}\nstderr:  {}".format(
            results_restore["exitcode"], results_restore["stderr"]))
# Verbose Testing output
        # device_logger.error("Return Code {}".format(results_restore["exitcode"]))
        # device_logger.error("stderr:  {}".format(results_restore["stderr"]))
# Still needed?
        # if re.match(r"objc\[\d+\]: Class AMSupport.+ Which one is undefined\.", results_restore["stdout"]):
        #     sys.exit(0)

        # json_restore_results = utilities.parse_json(results_restore["stdout"])
# Verbose Testing output
        print("Attempted to restore device; results were:\n{}".format(json_data))

        # if isinstance(json_restore_results, dict):

        if ( json_data["Message"] == 
            "This action cannot be performed on the device while it is already in use." ):

            device_logger.warning(
                "\u26A0 Device is already performing another command.  \n\t\tError:  {}\n[NOTICE] Exiting this thread.".format(
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

        # else:

        #     device_logger.error("\U0001F6D1 Failed restore device for unknown reason...  Error was:\n{}".format(json_restore_results))

    else:

        # if in_queue:

        # Update status in the database
        with Query() as run:
            results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                ("erased", device["ECID"]))

        # get_serial_number(device["ECID"])

        # Prepare Device
        prepare_device(device)

        # else:

        #     return