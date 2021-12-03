import json
import os
import re
import time
from pkg_resources import parse_version

import utilities
from db_utils import Query


def prepare_device(ECID):
    """Prepares the provided device

    Args:
        device:  Object of device's information from the database
    """

    session_info = get_session_info(ECID)

    # Get the device's current details
    with Query() as run:
        device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
            (ECID,)).fetchone()

    if device['status'] == "erased":
        print("\t{}:  \u23F3 Waiting for device to boot up...".format(device['SerialNumber']))

        # Sleep while the device erases and starts back up
        time.sleep(100)

    print("\t{}:  \u2699 Preparing".format(device['SerialNumber']))

    # Update status in the database
    with Query() as run:
        results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
            ("preparing", device['ECID']))

    results_prepare = utilities.runUtility( "cfgutil --ecid {} --format JSON prepare --dep \
        --language en --locale en_US".format(device['ECID']) )

    # Verify success
    if not results_prepare['success']:

#remove
        # print(results_prepare['stdout'])
        # print("space")
        # print(results_prepare)

        json_prepare_results = json.loads(results_prepare['stdout'])

        # Verify results apply to the same device in error output
        if json_prepare_results["Code"] == -402653030 and device['ECID'] in json_prepare_results["AffectedDevices"]:

            print("\t{}:  Policy prevents device from pairing with this computer, no futher information can be gathered!".format(device['SerialNumber']))

            # Add the end time to the database
            report_end_time(device)

        else:

            try:

# check if try is needed here?
                # json_prepare_results = json.loads(results_prepare['stdout'])

                # Check if device is Supervised
                if session_info["Output"][device['ECID']]['isSupervised'] == "Yes":

                    if json_prepare_results["Message"] == "The device is already prepared and must \
                        be erased to change settings.":

                        # If the device was already prepared, continue on
                        print("\t{}:  Device is supervised and prepared!".format(device['SerialNumber']))

                        # Update status in the database
                        with Query() as run:
                            results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                                ("done", device['ECID']))

                        report_end_time(device)

                    else:

                        # If the device was already prepared, continue on
                        print("\t{}:  Device is not prepared!".format(device['SerialNumber']))

#verbosity for dev
                        print("Error information:")
                        print("Verbose (stdout):  ", results_prepare['stdout'])
                        print("Verbose (stderr):  ", results_prepare['stderr'])

                        # Attempt to Prepare device (again)
                        prepare_device(ECID)

                else:

                    # Error Code 603 / -402653052
                    if json_prepare_results["Message"] == ( "The device is not connected." or
                        "This device is no longer connected." ):

                        # Device may have successfully Prepared, but was unable to capture that accurately
                        print("\t{}:  \u26A0 [WARNING] Unable to ".format(device['SerialNumber']) +
                            "determine device state, it will be checked on its next attach")

                        # Update status in the database
                        with Query() as run:
                            results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                                ("check", device['ECID']))

                    # Error Code 33001 / 607
                    elif json_prepare_results["Message"] == ( "The configuration is not available." or 
                        "The device is not activated" ):

                        # Attempt to Prepare device (again)
                        prepare_device(ECID)

                    else:

                        # If the device failed to prepare, erase and try again
                        print("\t{}:  \u26A0 [WARNING] Failed to prepare the device!".format(
                            device['SerialNumber']))

#verbosity for dev
                        print("Error information:")
                        print("Verbose (stdout):  ", results_prepare['stdout'])
                        print("Verbose (stderr):  ", results_prepare['stderr'])

                        # Add the end time to the database
                        erase_device(device)

            except:

                # Catch all other unknown errors
#verbosity for dev
                print("Error information:")
                print("Verbose (stdout):  ", results_prepare['stdout'])
                print("Verbose (stderr):  ", results_prepare['stderr'])

                # Add the end time to the database
                erase_device(device)

    else:

        # Add the end time to the database
        report_end_time(device)


def erase_device(device):
    """Erases the provided ECID

    Args:
        device:  Object of device's information from the database
    """

    # Erase Device
    print("\t{}:  \u2620 To proceed, the device will be erased!".format(device['serialNumber']))
    print("\t\t\u26A0\u26A0\u26A0 *** {}:  You have five seconds to remove the device before it \
        is wiped! *** \u26A0\u26A0\u26A0".format(device['serialNumber']))

    time.sleep(5)
    print("\t{}:  \U0001F4A3 Erasing device...".format(device['serialNumber']))

    results_erase = utilities.runUtility( "cfgutil --ecid {} erase".format(
        device['ECID']) )

    # Verify success
    if not results_erase['success']:

        if re.match( "cfgutil: error: no devices found", results_erase['stderr'] ):

            print("\t{}:  \U0001F605 Disaster averted, device was not erased!".format(device['serialNumber']))

        else:

            print("\tERROR:  \U0001F6D1 Failed to erase the device")
            print("\tReturn Code {}".format(results_erase['exitcode']))
            print("\t{}".format(results_erase['stderr']))

    else:

        # Update status in the database
        with Query() as run:
            results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                ("erasing", device['ECID']))


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
            ("done", device['ECID']))
        results = run.execute('UPDATE report SET end_time = ? WHERE id = ?', 
            (currentTime, device['id']))

    # Successfully Prepared device
    print("\t{}:  \U0001F7E2 [UNPLUG] Device has been provisioned".format(device['SerialNumber']))


def get_session_info(ECID):
    """Gets the provided ECID's current status

    Args:
        ECID:  Device's ECID
    Returns:
        JSON object of the device's current status
    """

    get_session_info = utilities.runUtility( 
        "cfgutil --ecid {} --format JSON get ".format(ECID) + 
            "activationState bootedState serialNumber isSupervised" )

    # Verify success
    if not get_session_info['success']:
        print("\tERROR:  \u26A0 [WARNING] Unable to obtain device info")
        print("\tReturn Code {}".format(get_session_info['exitcode']))
        print("\t{}".format(get_session_info['stderr']))

        # Try again
        time.sleep(10)
        get_session_info(ECID)

    else:
        # Load the JSON into an Object
        session_info = json.loads(get_session_info['stdout'])

        return session_info


def main():

    # Monitor available disk space
    total, used, free = utilities.get_disk_usage("/")
    print("Monitoring Available Disk Space:  {}".format(free))

    # Get the sessions' device ECID (this will be our primary unique 
    # identifer for this device during for subsequent sessions )
    session_ECID = os.getenv('ECID')

    print("{}:  [ATTACH WORKFLOW]".format(session_ECID))

    # Get the devices' serial number (this will be for user facing content)
    session_info = get_session_info(session_ECID)

#verbosity for dev
    # print(session_info["Output"])
    # print(session_info["Output"]["Errors"][session_ECID]["serialNumber"]["Code"])
    # print(session_info["Output"][session_ECID])

    try:

        if session_info["Output"]["Errors"][session_ECID]["serialNumber"]["Code"] == -402653030:

            print("\t{}:  \u26A0 [WARNING] Unable to pair with device, erasing...".format(session_ECID))

            # Get the device's details
            with Query() as run:
                device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
                        (session_ECID,)).fetchone()

            erase_device(device)

    except:
        pass


    if session_info["Output"][session_ECID]["bootedState"] == "Recovery":

        print("\t{}:  \u26A0 [WARNING] Device currently in Recovery Mode (DFU), restoring...".format(session_ECID))

        # Update status and end time in the database
        with Query() as run:
            results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                ("restoring", session_ECID))

# This needs to be tested further, doesn't seem to successfully complete
        results_restore = utilities.runUtility( "cfgutil --ecid {} restore".format(
            session_ECID) )

        # Verify success
        if not results_restore['success']:

            print("\tERROR:  \U0001F6D1 Failed to restore device from Recovery Mode")
            print("\tReturn Code {}".format(results_restore['exitcode']))
            print("\t{}".format(results_restore['stderr']))

            # Update status in the database
            with Query() as run:
                results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                    ("ERROR", device['ECID']))

        else:

            # Update status in the database
            with Query() as run:
                results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                    ("erased", device['ECID']))


    else:
        # Get the devices' serial number (this will be for user facing content)
        serial_number = session_info["Output"][session_ECID]["serialNumber"]

        # If a device was successfully detected
        if session_ECID:

            # Get the device's details
            with Query() as run:
                device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
                    (session_ECID,)).fetchone()

            # Set the Booted State
            booted_state = session_info["Output"][session_ECID]["bootedState"]

            # Wait for the device to finish booting before continuing...
            # Considering if the attach workflow is running, the device is considered "Booted", 
            # this will likely never come into play.
            while booted_state != "Booted":

                print("\t{}:  \u23F3 Waiting for device to boot...".format(serial_number))
                time.sleep(5)

                # Get the devices' boot state
                results_booted_state = utilities.runUtility( 
                    "cfgutil --ecid {} get bootedState".format(session_ECID) )

                # Verify success
                if not results_booted_state['success']:
                    print("\tERROR:  \U0001F6D1 Failed to get devices boot state!")
                    print("\tReturn Code {}".format(results_booted_state['exitcode']))
                    print("\t{}".format(results_booted_state['stderr']))

                booted_state = results_booted_state['stdout']

            # If a device was retrived
            if device:
                # Device has already started the provisioning process

                # Set the device States
                activation_state = session_info["Output"][session_ECID]["activationState"]
                supervision_state = session_info["Output"][session_ECID]['isSupervised']

                # Check device's current state
                if activation_state == "Unactivated":

                    # Prepare Device
                    prepare_device(session_ECID)

                elif activation_state == "Activated" and supervision_state == True and device['status'] == "check":

                    # If the device was already prepared, continue on
                    report_end_time(device)

                else:

                    if device['status'] != "new":
                        # Unknown device state
                        print("\t{}:  \u26A0 [WARNING] Unknown device state".format(serial_number))

                    # Erase the device
                    erase_device(device)

            else:

                # Device is not in the queue, so needs to be erased.
                print("\t{}:  \u2795 Adding device to queue...".format(serial_number))

                with Query() as run:
                    # Add device to database
                    run.execute("INSERT INTO devices ( status, ECID, SerialNumber, UDID, \
                        deviceType, buildVersion, firmwareVersion, locationID) VALUES (?, ?, ?, ?, \
                        ?, ?, ?, ?)", ( 'new', session_ECID, serial_number, os.getenv("UDID"), 
                            os.getenv("deviceType"), os.getenv("buildVersion"), 
                            os.getenv("firmwareVersion"), os.getenv("locationID") ) )

                    # Get the device's details
                    device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
                        (session_ECID,)).fetchone()

                # Get device's current ID
                identifier = device['id']

                # Get current epoch time
                currentTime = time.time()

                # Update the report table
                with Query() as run:
                    results = run.execute("INSERT INTO report (id, start_time) VALUES (?, ?)", 
                        (identifier, currentTime) )

                # Get the latest firmware this device model supports
                latest_firmware = utilities.firmware_check(device["deviceType"])

                # Check if the current firmware is older than the latest
                if parse_version(device["firmwareVersion"]) < parse_version(str(latest_firmware)) :

                    # Update device using Restore, which will also erase it
                    print("\t{}:  \U0001F4A3 Erasing and updating device...".format(serial_number))

                    results_restore = utilities.runUtility( 
                        "cfgutil --ecid {} restore".format(session_ECID) )

                    # Verify success
                    if not results_restore['success']:
                        print("\tERROR:  \U0001F6D1 Failed to update the device")
                        print("\tReturn Code {}".format(results_restore['exitcode']))
                        print("\t{}".format(results_restore['stderr']))

                    else:

                        # Update status in the database
                        with Query() as run:
                            results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                                ("erased", device['ECID']))

                        # Prepare Device
                        prepare_device(session_ECID)

                else:

                    # Firmware is the latest, so simply erase the device
                    erase_device(device)

        else:

            print("\t{}:  \U0001F6D1 [ERROR] Cannot find device information!".format(serial_number))


    # try:

    # Attempt to clean up the tempory directory so that files are not filling up the hard drive space.
    utilities.clean_configurator_temp_dir()

    # except:

    #     print("\u26A0\u26A0 [WARNING] Failed to clear temporary storage! \u26A0\u26A0")


if __name__ == "__main__":
    main()
