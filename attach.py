# from distutils import util
import os
import random
import re
import sys
import time
from pkg_resources import parse_version

import utilities
from db_utils import Query


def prepare_device(ECID):
    """Prepares the provided device

    Args:
        ECID:  Object of device's information from the database
    """

    # Get the device's details
    with Query() as run:
        device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
            (ECID,)).fetchone()

    if device["status"] == "erased":
        utilities.verbose_output("{} | \u23F3 Waiting for device to finish booting...".format(device["SerialNumber"]))

        # Sleep while the device erases and starts back up
        time.sleep(70)

    utilities.verbose_output("{} | \u2699 Preparing".format(device["SerialNumber"]))

    # Update status in the database
    with Query() as run:
        results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
            ("preparing", device["ECID"]))

    results_prepare = utilities.runUtility( "cfgutil --ecid {} --format JSON prepare --dep \
        --language en --locale en_US".format(device["ECID"]) )

    # print("\tresults_prepare > success {}".format(results_prepare["success"]))
    # print("\tresults_prepare > Return Code {}".format(results_prepare["exitcode"]))
    # print("\tresults_prepare > stdout{}".format(results_prepare["stdout"]))
    # print("\tresults_prepare > stderr:  {}".format(results_prepare["stderr"]))

    # Verify success
    if results_prepare["success"]:

        # Add the end time to the database
        report_end_time(device)

    else:

        if re.match("The device is not activated.", results_prepare["stdout"]):
#DO SOMETHING HERE
            utilities.verbose_output("{} | \u26A0 [WARNING] The device was not activated, trying again.  \n\t\tError:\n{}".format(
                device["SerialNumber"], results_prepare["stdout"]))

            # Attempt to Prepare device (again)
            prepare_device(device["ECID"])

        # try:
        json_prepare_results = utilities.parse_json(results_prepare["stdout"])

        if isinstance(json_prepare_results, dict):

            # Verify results apply to the same device in error output
            if json_prepare_results["Code"] == -402653030 and device['ECID'] in json_prepare_results["AffectedDevices"]:

                utilities.verbose_output("{} | Policy prevents device from pairing with this computer, no futher information can be gathered!".format(device['SerialNumber']))

                # Add the end time to the database
                # print("prepare_device > report_end_time:  pairing prevented")
                report_end_time(device)

            # elif json_prepare_results["Message"] == ( "The device is not connected." or
            #         "This device is no longer connected." ):
                # Error Code 603 / -402653052
            elif json_prepare_results["Code"] in { -402653052, 603 } and device['ECID'] in json_prepare_results["AffectedDevices"]:

                # Device may have successfully Prepared, but was unable to capture that accurately
                utilities.verbose_output("{} | \u26A0 [WARNING] Unable to ".format(device["SerialNumber"]) +
                    "determine device state, it will be checked on its next attach")

                # Update status in the database
                with Query() as run:
                    results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                        ("check", device["ECID"]))

                # print("Exiting...")
                sys.exit(0)

            # Error Code 33001 / 607
            elif json_prepare_results["Message"] == "The device is not activated.":

                utilities.verbose_output("{} | \u26A0 [WARNING] The device was not activated, trying again.  \n\t\tError:\n{}".format(
                    device["SerialNumber"], json_prepare_results["Message"]))

                # Attempt to Prepare device (again)
                prepare_device(device["ECID"])

            elif json_prepare_results["Message"] == "The configuration is not available.":

                utilities.verbose_output("{} | \u26A0 [WARNING] Unable to prepare device.  \n\t\tError:  {}".format(
                    device["SerialNumber"], json_prepare_results["Message"]))

                # Erase device
                erase_device(device)

            elif ( json_prepare_results["Message"] == 
                "The device is already prepared and must be erased to change settings." ):

                # If the device was already prepared, erase it
                utilities.verbose_output("{} | Device was already prepared, erasing it...".format(device["SerialNumber"]))
                # # If the device was already prepared, continue on
                # utilities.verbose_output("{} | Device is supervised and prepared!".format(device["SerialNumber"]))

                # Erase device
                erase_device(device)

                # Update status in the database
                # with Query() as run:
                #     results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                #         ("done", device["ECID"]))

                # print("prepare_device > report_end_time: done")
                # report_end_time(device)

            else:

                # If the device failed to prepare, erase and try again
                utilities.verbose_output("{} | \u26A0 [WARNING] Unaccounted for prepare failure!".format(
                    device["SerialNumber"]))
    ##### Dev/Debug output (to be removed) 
                # print("Unknown failure.  Error information:")
                print("results_prepare > stdout:  ", results_prepare["stdout"])
                print("results_prepare > stderr:  ".format(re.sub(r"objc\[\d+\]: Class AMSupport.+ Which one is undefined\.", "", results_prepare["stderr"])))

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

            utilities.verbose_output("\U0001F6D1 [ERROR]:  Failed prepare device for unknown reason...  Error was:\n{}".format(json_prepare_results))


def erase_device(device):
    """Erases the provided device object.

    Args:
        device:  Object of device's information from the database
    """

    try:
        identifier = device["serialNumber"]

    except KeyError:
        identifier = device["ECID"]

    # Erase Device
    utilities.verbose_output("{} | \u2620 To proceed, the device will be erased!".format(identifier))
    utilities.verbose_output("{} | \u26A0\u26A0\u26A0 *** You have five seconds to remove the device before it is wiped! *** \u26A0\u26A0\u26A0".format(identifier))

    time.sleep(5)
    utilities.verbose_output("{} | \U0001F4A3 Erasing device...".format(identifier))

    results_erase = utilities.runUtility( "cfgutil --ecid {} erase".format(device["ECID"]) )

    # Verify success
    if results_erase["success"]:

        # Update status in the database
        with Query() as run:
            results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                ("erasing", device["ECID"]))

    elif re.match( "cfgutil: error: no devices found", results_erase["stderr"]):
        utilities.verbose_output("{} | \U0001F605 Disaster averted, device was not erased!".format(
            device["serialNumber"]))

    else:
        utilities.verbose_output("{} | \U0001F6D1 ERROR:  Failed to erase the device".format(identifier))
        utilities.verbose_output("Return Code {}".format(results_erase["exitcode"]))
        print("\t{}".format(re.sub(r"objc\[\d+\]: Class AMSupport.+ Which one is undefined\.", "", results_erase["stderr"])))


def restore_device(device):
    """Erases and updates the provided device object.

    Args:
        device:  Object of device's information from the database
    """

    try:
        identifier = device["serialNumber"]
        in_queue=True

    except KeyError:
        identifier = device["ECID"]
        in_queue=False

    # Update device using Restore, which will also erase it
    utilities.verbose_output("{} | \U0001F4A3 Erasing and updating device...".format(identifier))

    # delay = random.randrange(10, 200)
    # print("Random Delay before restore:  {}".format(delay))
    # time.sleep(delay)

    results_restore = utilities.runUtility( 
        "cfgutil -vvvv --format JSON --ecid {} restore".format(device["ECID"]) )

    # Verify success
    if not results_restore["success"]:
        utilities.verbose_output("{} | \U0001F6D1 ERROR:  Failed to restore device from Recovery Mode".format(
            device["ECID"]))
        utilities.verbose_output("Return Code {}".format(results_restore["exitcode"]))

# Verbose Testing output
        utilities.verbose_output("stderr:  {}".format(results_restore["stderr"]))

        if re.match(r"objc\[\d+\]: Class AMSupport.+ Which one is undefined\.", results_restore["stdout"]):
            sys.exit(0)

        json_restore_results = utilities.parse_json(results_restore["stdout"])
# Verbose Testing output
        print("Attempted to restore device; results were:\n{}".format(json_restore_results))

        if isinstance(json_restore_results, dict):

            if json_restore_results["Message"] == "This action cannot be performed on the device while it is already in use.":

                utilities.verbose_output("{} | \u26A0 [WARNING] Device is already performing another command.  \n\t\tError:  {}".format(
                    identifier, json_restore_results["Message"]))

                utilities.verbose_output("{} | \u26A0 [NOTICE] Exiting this thread.".format(identifier))
                sys.exit(0)

            else:

                while has_not_booted(device):
                    pass

                # # Erase device
                # erase_device(device)

                # Update status in the database
                # with Query() as run:
                #     results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                #         ("error", device['ECID']))

        else:

            utilities.verbose_output("\U0001F6D1 [ERROR]:  Failed restore device for unknown reason...  Error was:\n{}".format(json_restore_results))

    else:

        if in_queue:

            # Update status in the database
            with Query() as run:
                results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                    ("erased", device["ECID"]))

            get_serial_number(device["ECID"])

            # Prepare Device
            prepare_device(device["ECID"])

        else:

            return


def get_serial_number(ECID):

    # Get the devices' serial number
    results_serial_number = utilities.runUtility( 
        "cfgutil --ecid {} get serialNumber".format(ECID) )

    serial_number = results_serial_number["stdout"]

    # Update status in the database
    with Query() as run:
        results = run.execute('UPDATE devices SET SerialNumber = ? WHERE ECID = ?', 
            (serial_number, ECID))

        # Get the device's details
        device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
            (ECID,)).fetchone()

    return device


def report_end_time(device):
    """Updates the database when the device has completed the provisioning process

    Args:
        device:  Object of device's information from the database
    """

    # Get current epoch time
    currentTime = time.time()

    # Update status and end time in the database
    with Query() as run:
        results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
            ("done", device["ECID"]))
        results = run.execute('UPDATE report SET end_time = ? WHERE id = ?', 
            (currentTime, device["id"]))

    # Successfully Prepared device
    utilities.verbose_output("{} | \U0001F7E2 [DONE] Device has been provisioned, it can be unplugged!".format(device["SerialNumber"]))


def get_session_info(ECID):
    """Gets the provided ECID's current status

    Args:
        ECID:  Device's ECID
    Returns:  
        JSON object of the device's current status
    """

    # print("Getting session info...")

    results_get_session_info = utilities.runUtility( 
        "cfgutil --ecid {} --format JSON get ".format(ECID) + 
            "activationState bootedState isSupervised UDID deviceType buildVersion \
            firmwareVersion locationID batteryCurrentCapacity batteryIsCharging" )

    # Verify success
    if results_get_session_info["success"]:
        # Load the JSON into an Object
        # print("\tReturning session info:  {}".format(results_get_session_info["stdout"]))
        return utilities.parse_json(results_get_session_info["stdout"])["Output"]

    # print("\tERROR:  \u26A0 Unable to obtain device info")
    # print("\tReturn Code:  {}".format(results_get_session_info["exitcode"]))
    # print("\tstdout:  {}".format(results_get_session_info["stdout"]))
    # print("\tstderr:  {}".format(results_get_session_info["stderr"]))

    if re.match( "cfgutil: error: no devices found", results_get_session_info["stderr"] ):
        # print("Exiting...")
        sys.exit(1)

    # Try again
    time.sleep(5)
    # print("get_session_info > get_session_info")
    get_session_info(ECID)


def create_record(ECID):

    # Device is not in the queue, so needs to be erased.
    utilities.verbose_output("{} | \u2795 Adding device to queue...".format(ECID))

    session_info_full = get_session_info(ECID)
    activationState = (
        os.getenv("activationState")
        or session_info_full[ECID]["activationState"]
    )

    bootedState = (
        os.getenv("bootedState")
        or session_info_full[ECID]["bootedState"]
    )

    isSupervised = (
        os.getenv("isSupervised")
        or session_info_full[ECID]["isSupervised"]
    )

    udid = os.getenv("UDID") or session_info_full[ECID]["UDID"]
    deviceType = (
        os.getenv("deviceType")
        or session_info_full[ECID]["deviceType"]
    )

    buildVersion = (
        os.getenv("buildVersion")
        or session_info_full[ECID]["buildVersion"]
    )

    firmwareVersion = (
        os.getenv("firmwareVersion")
        or session_info_full[ECID]["firmwareVersion"]
    )

    locationID = (
        os.getenv("locationID")
        or session_info_full[ECID]["locationID"]
    )

    batteryCurrentCapacity = (
        os.getenv("batteryCurrentCapacity")
        or session_info_full[ECID]["batteryCurrentCapacity"]
    )

    batteryIsCharging = (
        os.getenv("batteryIsCharging")
        or session_info_full[ECID]["batteryIsCharging"]
    )

    with Query() as run:
        # Add device to database
        run.execute("INSERT INTO devices ( status, ECID, UDID, \
            deviceType, buildVersion, firmwareVersion, locationID, activationState, \
            bootedState, isSupervised, batteryCurrentCapacity, batteryIsCharging) \
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ( 'new', ECID, udid, deviceType, buildVersion, firmwareVersion, locationID, 
            activationState, bootedState, isSupervised, batteryCurrentCapacity, batteryIsCharging) )

        # Get the device's details
        device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
            (ECID,)).fetchone()

        # Get current epoch time
        currentTime = time.time()

        # Update the report table
        results = run.execute("INSERT INTO report (id, start_time) VALUES (?, ?)", 
            (device["id"], currentTime) )

    return device


def has_not_booted(device):

    # Get the devices' boot state
    results_booted_state = utilities.runUtility( 
        "cfgutil --ecid {} --format JSON get bootedState".format(device["ECID"]) )

    # print(results_booted_state)

    # Verify success
    if not results_booted_state["success"]:
        utilities.verbose_output("{} | \U0001F6D1 ERROR:  Failed to get devices boot state!".format(device["ECID"]))
        utilities.verbose_output("Return Code {}".format(results_booted_state["exitcode"]))
        utilities.verbose_output("{}".format(results_booted_state["stderr"]))
        # Hard exiting for now, until a reason not to is discovered.
        sys.exit(2)
        return True

    else:

        json_results_booted_state = utilities.parse_json(results_booted_state["stdout"])
        # print(json_results_booted_state["Output"][device["ECID"]]["bootedState"])

        if isinstance(json_results_booted_state, dict):

            if json_results_booted_state["Output"][device["ECID"]]["bootedState"] == "Recovery":
                utilities.verbose_output("{} | \u26A0 [WARNING] Device is currently booted to Recovery Mode (DFU)...".format(
                    device["ECID"]))
                restore_device(device)
                return True
                # sys.exit(0)

            elif json_results_booted_state["Output"][device["ECID"]]["bootedState"] == "Restore":
                utilities.verbose_output("{} | \u26A0 [STATUS] Device is currently being restored...".format(
                    device["ECID"]))
                time.sleep(60)
                return True
                # sys.exit(0)

            elif json_results_booted_state["Output"][device["ECID"]]["bootedState"] != "Booted":
                utilities.verbose_output("{} | \u23F3 Waiting for device to boot...".format(device["ECID"]))
                time.sleep(5)
                return True

        else:

            utilities.verbose_output("\U0001F6D1 [ERROR]:  Failed to get devices boot state...  Error was:\n{}".format(json_results_booted_state))

    return False


def main():

    # Monitor available disk space
    total, used, free = utilities.get_disk_usage("/")
    print("Monitoring Available Disk Space:  {}".format(free))

    # Get the sessions' device ECID (this will be our primary unique 
    # identifier for this device during for subsequent sessions )
    session_ECID = os.getenv('ECID')

    if not session_ECID:

        # If a device was not successfully detected
        utilities.verbose_output("\U0001F6D1 [ERROR] Unable to determine device information for an attached device!")

    else:

        # If a device was successfully detected
        utilities.verbose_output("{}:  [ATTACH WORKFLOW]".format(session_ECID), False)

        # Check if device has been added to database
        with Query() as run:
            device = run.execute('SELECT * FROM devices WHERE ECID = ?', (session_ECID,)).fetchone()

        # If a device was not retrived
        if not device:
            device = create_record(session_ECID)

        # check_state = dict
        check_state = { "ECID": session_ECID }
        while has_not_booted(check_state):
            pass

        # Get the devices' serial number (this will be for user facing content)
        # print("main > get_session_info")
        session_info_full = get_session_info(session_ECID)

        try:

            session_info_error = session_info_full["Errors"][session_ECID]

            if session_info_error["serialNumber"]["Code"] == -402653030:

                utilities.verbose_output("{} | \u26A0 [WARNING] Unable to pair with device, erasing...".format(session_ECID))

                # Get the device's details
                with Query() as run:
                    device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
                            (session_ECID,)).fetchone()

                erase_device(device)

        except:
            pass


        session_info = session_info_full[session_ECID]

        if session_info["bootedState"] == "Recovery":
            utilities.verbose_output("{} | \u26A0 [WARNING] Device is currently booted to Recovery Mode (DFU)...".format(
                session_ECID))
            # restore_device(device)
            utilities.verbose_output("\U0001F6D1 [ERROR] NEED TO FIGURE OUT HOW TO HANDLE AT THIS POINT!")
            sys.exit(0)

        else:

            # Get the devices' serial number (this will be for user facing content)
            device = get_serial_number(device["ECID"])

            # Wait for the device to finish booting before continuing...
            # Considering if the attach workflow is running, the device is considered "Booted", 
            # this will likely never come into play.
            while has_not_booted(device):
                pass

            if device["status"] in { "new", "error" }:

                # Get the latest firmware this device model supports
                latest_firmware = utilities.firmware_check(device["deviceType"])

                # Check if the current firmware is older than the latest
                if parse_version(device["firmwareVersion"]) < parse_version(str(latest_firmware)) :
                    # Restore the device
                    restore_device(device)

                else:
                    # Firmware is the latest, so simply erase the device
                    erase_device(device)

            else:
                # Device has already started the provisioning process

                # Set the device States
                activation_state = session_info["activationState"]
                supervision_state = session_info["isSupervised"]

                # Check device's current state
                if activation_state == "Unactivated":
                    # print("main > unactivated")
                    # Prepare Device
                    prepare_device(device["ECID"])

                elif ( activation_state == "Activated" and supervision_state == True ):

                    if device["status"] == "check":
                        # Add the end time to the database
                        # print("main > report_end_time:  reboot check")
                        report_end_time(device)

                    elif device["status"] == "done":
                        utilities.verbose_output("{} | \U0001F7E2 [UNPLUG] Device configuration likely initiated a reboot, it is safe to unplug.".format(device["SerialNumber"]))

                    else:

                        # Unknown device state
                        utilities.verbose_output("{} | \u26A0 [WARNING] Unknown device state".format(device["SerialNumber"]))

                        # Erase the device
                        erase_device(device)

                else:

                    # if device["status"] != "new":
            # ^^^ Maybe check against a [ list of known device states] ?

                    # Unknown device state
                    utilities.verbose_output("{} | \u26A0 [WARNING] Unknown device state".format(device["SerialNumber"]))

                    # Erase the device
                    erase_device(device)


    # try:
        # Attempt to clean up the temporary directory so that files are not filling up the hard drive space.
    utilities.clean_configurator_temp_dir()

    # except:
    #     print("\u26A0\u26A0 [WARNING] Failed to clear temporary storage! \u26A0\u26A0")


if __name__ == "__main__":
    main()
