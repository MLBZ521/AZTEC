# from distutils import util
import os
# import random
# import re
# import sys
from pkg_resources import parse_version

import utilities
from actions import erase_device, has_not_booted, prepare_device, restore_device
from device import create_or_update_record
from db_utils import Query






# def get_serial_number(ECID):

#     # Get the devices' serial number
#     results_serial_number = utilities.run_utility( 
#         "cfgutil --ecid {} get serialNumber".format(ECID) )

#     serial_number = results_serial_number["stdout"]

#     # Update status in the database
#     with Query() as run:
#         results = run.execute('UPDATE devices SET SerialNumber = ? WHERE ECID = ?', 
#             (serial_number, ECID))

#         # Get the device's details
#         device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
#             (ECID,)).fetchone()

#     return device







def main():

    main_logger = utilities.log_setup()

    # Monitor available disk space
    total, used, free = utilities.get_disk_usage("/")
    main_logger.debug("Monitoring Available Disk Space:  {}".format(free))

    # Get the sessions' device ECID (this will be our primary unique 
    # identifier for this device during for subsequent sessions )
    session_ECID = os.getenv('ECID')

    if not session_ECID:

        # If a device was not successfully detected
        main_logger.error(
            "\U0001F6D1 Unable to determine device information for an attached device!")

    else:

        device_logger = utilities.log_setup(log_name=session_ECID)

        # If a device was successfully detected
        device_logger.info("[ATTACH WORKFLOW]")

        device = create_or_update_record(session_ECID, "new")

        # check_state = dict
        # check_state = { "ECID": session_ECID }
        while has_not_booted(device):
            device = create_or_update_record(device["ECID"])


# Get the devices' serial number (this will be for user facing content)
# print("main > get_session_info")
# session_info_full = get_session_info(session_ECID)

    # try:

    #     session_info_error = session_info_full["Errors"][session_ECID]

    #     if session_info_error["serialNumber"]["Code"] == -402653030:

    #         device_logger.warning("\u26A0 Unable to pair with device, erasing...")

    #         # Get the device's details
    #         with Query() as run:
    #             device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
    #                 (session_ECID,)).fetchone()

    #         erase_device(device)

    # except:
    #     pass


        # session_info = session_info_full[session_ECID]

        # # if session_info["bootedState"] == "Recovery":
        # #     device_logger.warning("\u26A0 Device is currently booted to Recovery Mode (DFU)...")
        # #     # restore_device(device)
        # #     device_logger.error("\U0001F6D1 NEED TO FIGURE OUT HOW TO HANDLE AT THIS POINT!")
        # #     sys.exit(0)

        # # else:

            # Get the devices' serial number (this will be for user facing content)
            # device = get_serial_number(device["ECID"])

            # Wait for the device to finish booting before continuing...
            # Considering if the attach workflow is running, the device is considered "Booted", 
            # # this will likely never come into play.
            # while actions.has_not_booted(device):
            #     pass

        if device["status"] in { "new", "error" }:

            # Get the latest firmware this device model supports
            latest_firmware = utilities.firmware_check(device["deviceType"])

            # Check if the current firmware is older than the latest
            if parse_version(device["firmwareVersion"]) < parse_version(str(latest_firmware)):
                # Restore the device
                restore_device(device)

            else:
                # Firmware is the latest, so simply erase the device
                erase_device(device)

        else:
            # Device has already started the provisioning process

            # Set the device States
            activation_state = device["activationState"]
            supervision_state = device["isSupervised"]

            # Check device's current state
            if activation_state == "Unactivated":
                # print("main > unactivated")
                # Prepare Device
                prepare_device(device)

            elif ( activation_state == "Activated" and supervision_state == True ):

                if device["status"] == "check":
                    # Add the end time to the database
                    # print("main > report_end_time:  reboot check")
                    utilities.report_end_time(device)

                elif device["status"] == "done":
                    device_logger.info(
                        "\U0001F7E2 [UNPLUG] MDM configuration likely initiated a reboot, it is safe to unplug.")

                else:

                    # Unknown device state
                    device_logger.warning("\u26A0 Unknown device state")

                    # Erase the device
                    erase_device(device)

            else:

                # if device["status"] != "new":
        # ^^^ Maybe check against a [ list of known device states] ?

                # Unknown device state
                device_logger.warning("\u26A0 Unknown device state")

                # Erase the device
                erase_device(device)


    # try:
        # Attempt to clean up the temporary directory so that files are not filling up the hard drive space.
    utilities.clean_configurator_temp_dir()

    # except:
    #     print("\u26A0\u26A0 Failed to clear temporary storage! \u26A0\u26A0")


if __name__ == "__main__":
    main()
