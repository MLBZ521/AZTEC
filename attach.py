import json
import os
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
        print("\t{}:  \u23F3 Waiting for device to finish booting...".format(device["SerialNumber"]))

        # Sleep while the device erases and starts back up
        time.sleep(100)

    print("\t{}:  \u2699 Preparing".format(device["SerialNumber"]))

    # Update status in the database
    with Query() as run:
        results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
            ("preparing", device["ECID"]))

    results_prepare = utilities.runUtility( "cfgutil --ecid {} --format JSON prepare --dep \
        --language en --locale en_US".format(device["ECID"]) )

    # Verify success
    if not results_prepare["success"]:

        try:
            json_prepare_results = json.loads(results_prepare["stdout"])

            session_info = ( get_session_info(device["ECID"]) )["Output"][device["ECID"]]

            # Verify results apply to the same device in error output
            if json_prepare_results["Code"] == -402653030 and device['ECID'] in json_prepare_results["AffectedDevices"]:

                print("\t{}:  Policy prevents device from pairing with this computer, no futher information can be gathered!".format(device['SerialNumber']))

                # Add the end time to the database
                report_end_time(device)

            # Check if device is Supervised
            elif session_info["isSupervised"] == "Yes":

                if ( json_prepare_results["Message"] == 
                    "The device is already prepared and must be erased to change settings." ):

                    # If the device was already prepared, continue on
                    print("\t{}:  Device is supervised and prepared!".format(device["SerialNumber"]))

                    # Update status in the database
                    with Query() as run:
                        results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                            ("done", device["ECID"]))

                    report_end_time(device)

                else:

                    # The device was not prepared
                    print("\t{}:  Device is not prepared!".format(device["SerialNumber"]))

##### Dev/Debug output (to be removed)
                    print("Device was not prepared.  Error information:")
                    print("stdout:  ", results_prepare["stdout"])
                    print("stderr:  ", results_prepare["stderr"])

                    # Attempt to Prepare device (again)
                    prepare_device(device["ECID"])


            elif json_prepare_results["Message"] == ( "The device is not connected." or
                    "This device is no longer connected." ):
                # Error Code 603 / -402653052

                # Device may have successfully Prepared, but was unable to capture that accurately
                print("\t{}:  \u26A0 [WARNING] Unable to ".format(device["SerialNumber"]) +
                    "determine device state, it will be checked on its next attach")

                # Update status in the database
                with Query() as run:
                    results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                        ("check", device["ECID"]))

            # Error Code 33001 / 607
            elif json_prepare_results["Message"] == ( "The configuration is not available." or 
                "The device is not activated" ):

                print("\t{}:  \u26A0 [WARNING] Unable to prepare device.  \n\t\tError:\n{}".format(
                    device["SerialNumber"], json_prepare_results["Message"]))

                # Attempt to Prepare device (again)
                prepare_device(device["ECID"])

            else:

                # If the device failed to prepare, erase and try again
                print("\t{}:  \u26A0 [WARNING] Failed to prepare the device!".format(
                    device["SerialNumber"]))
##### Dev/Debug output (to be removed) 
                print("Unknown failure.  Error information:")
                print("stdout:  ", results_prepare["stdout"])
                print("stderr:  ", results_prepare["stderr"])

                # Erase device
                erase_device(device)

        except:
            # Catch all other unknown errors

##### Dev/Debug output (to be removed)
            print("Exception Error information:")
            print("stdout:  ", results_prepare["stdout"])
            print("stderr:  ", results_prepare["stderr"])

            # Erase device
            erase_device(device)

    else:

        # Add the end time to the database
        report_end_time(device)


def erase_device(device):
    """Erases the provided device object.

    Args:
        device:  Object of device's information from the database
    """

    # Erase Device
    print("\t{}:  \u2620 To proceed, the device will be erased!".format(device["serialNumber"]))
    print("\t{}:  \u26A0\u26A0\u26A0 *** You have five seconds to remove the device before it is wiped! *** \u26A0\u26A0\u26A0".format(device["serialNumber"]))

    time.sleep(5)
    print("\t{}:  \U0001F4A3 Erasing device...".format(device["serialNumber"]))

    results_erase = utilities.runUtility( "cfgutil --ecid {} erase".format(device["ECID"]) )

    # Verify success
    if results_erase["success"]:

        # Update status in the database
        with Query() as run:
            results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                ("erasing", device["ECID"]))

    elif re.match( "cfgutil: error: no devices found", results_erase["stderr"] ):
        print("\t{}:  \U0001F605 Disaster averted, device was not erased!".format(
            device["serialNumber"]))

    else:
        print("\tERROR:  \U0001F6D1 Failed to erase the device")
        print("\tReturn Code {}".format(results_erase["exitcode"]))
        print("\t{}".format(results_erase["stderr"]))


def restore_device(device):
    """Erases and updates the provided device object.

    Args:
        device:  Object of device's information from the database
    """

    try:
        identifer = device["serialNumber"]

    except KeyError:
        identifer = device["ECID"]

    # Update device using Restore, which will also erase it
    print("\t{}:  \U0001F4A3 Erasing and updating device...".format(identifer))

    results_restore = utilities.runUtility( 
        "cfgutil --ecid {} restore".format(device["ECID"]) )

    # Verify success
    if not results_restore["success"]:
        print("\tERROR:  \U0001F6D1 Failed to restore device from Recovery Mode")
        print("\tReturn Code {}".format(results_restore["exitcode"]))
        print("\t{}".format(results_restore["stderr"]))

        # Update status in the database
        with Query() as run:
            results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                ("ERROR", device['ECID']))

    else:

        get_serial_number(device["ECID"])

        # Prepare Device
        prepare_device(device["ECID"])


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
    print("\t{}:  \U0001F7E2 [UNPLUG] Device has been provisioned".format(device["SerialNumber"]))


def get_session_info(ECID):
    """Gets the provided ECID's current status

    Args:
        ECID:  Device's ECID
    Returns:  
        JSON object of the device's current status
    """

    results_get_session_info = utilities.runUtility( 
        "cfgutil --ecid {} --format JSON get ".format(ECID) + 
            "activationState bootedState isSupervised" )

    # Verify success
    if results_get_session_info["success"]:
        # Load the JSON into an Object
        return json.loads(results_get_session_info["stdout"])

    print("\tERROR:  \u26A0 Unable to obtain device info")
    print("\tReturn Code {}".format(results_get_session_info["exitcode"]))
    print("\t{}".format(results_get_session_info["stderr"]))

    if re.match( "cfgutil: error: no devices found", results_erase["stderr"] ):
        sys.exit(1)

    # Try again
    time.sleep(10)
    get_session_info(ECID)


def create_record(ECID):

    # Device is not in the queue, so needs to be erased.
    print("\t{}:  \u2795 Adding device to queue...".format(ECID))

    with Query() as run:
        # Add device to database
        run.execute("INSERT INTO devices ( status, ECID, UDID, \
            deviceType, buildVersion, firmwareVersion, locationID) VALUES (?, ?, ?, ?, \
            ?, ?, ?)", ( 'new', ECID, os.getenv("UDID"), 
                os.getenv("deviceType"), os.getenv("buildVersion"), 
                os.getenv("firmwareVersion"), os.getenv("locationID") ) )

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
        "cfgutil --ecid {} get bootedState".format(device["ECID"]) )

    # Verify success
    if not results_booted_state["success"]:
        print("\tERROR:  \U0001F6D1 Failed to get devices boot state!")
        print("\tReturn Code {}".format(results_booted_state["exitcode"]))
        print("\t{}".format(results_booted_state["stderr"]))
        return True

    elif results_booted_state["stdout"] != "Booted":
        print("\t{}:  \u23F3 Waiting for device to boot...".format(device["SerialNumber"]))
        time.sleep(5)
        return True

    return False


def main():

    # Monitor available disk space
    total, used, free = utilities.get_disk_usage("/")
    print("Monitoring Available Disk Space:  {}".format(free))

    # Get the sessions' device ECID (this will be our primary unique 
    # identifer for this device during for subsequent sessions )
    session_ECID = os.getenv('ECID')

    # If a device was successfully detected
    if session_ECID:

        print("{}:  [ATTACH WORKFLOW]".format(session_ECID))

        # Check if device has been added to database
        with Query() as run:
            device = run.execute('SELECT * FROM devices WHERE ECID = ?', (session_ECID,)).fetchone()

        # If a device was not retrived
        if not device:
            device = create_record(session_ECID)

        # Get the devices' serial number (this will be for user facing content)
        session_info_full = get_session_info(session_ECID)

        try:

            session_info_error = session_info_full["Output"]["Errors"][session_ECID]

            if session_info_error["serialNumber"]["Code"] == -402653030:

                print("\t{}:  \u26A0 [WARNING] Unable to pair with device, erasing...".format(session_ECID))

                # Get the device's details
                with Query() as run:
                    device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
                            (session_ECID,)).fetchone()

                erase_device(device)

        except:
            pass


        session_info = session_info_full["Output"][session_ECID]

        if session_info["bootedState"] == "Recovery":
            print("\t{}:  \u26A0 [WARNING] Device is currently booted to Recovery Mode (DFU)...".format(
                session_ECID))
            restore_device(device)

        else:

            # Get the devices' serial number (this will be for user facing content)
            device = get_serial_number(device["ECID"])

            # Wait for the device to finish booting before continuing...
            # Considering if the attach workflow is running, the device is considered "Booted", 
            # this will likely never come into play.
            while has_not_booted(device):
                pass

            if device["status"] == "new":

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

                    # Prepare Device
                    prepare_device(device["ECID"])

                elif ( activation_state == "Activated" and 
                        supervision_state == True and 
                        device["status"] == "check" ):

                    # If the device was already prepared, continue on
                    report_end_time(device)

                else:

                    # if device["status"] != "new":
            # ^^^ Maybe check against a [ list of known device states] ?

                    # Unknown device state
                    print("\t{}:  \u26A0 [WARNING] Unknown device state".format(device["SerialNumber"]))

                    # Erase the device
                    erase_device(device)

    else:
        print("\t  \U0001F6D1 [ERROR] Unable to determine device information for an attached device!")


    # try:
        # Attempt to clean up the temporary directory so that files are not filling up the hard drive space.
    utilities.clean_configurator_temp_dir()

    # except:
    #     print("\u26A0\u26A0 [WARNING] Failed to clear temporary storage! \u26A0\u26A0")


if __name__ == "__main__":
    main()
