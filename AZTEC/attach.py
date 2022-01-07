import os

from distutils.util import strtobool
from pkg_resources import parse_version

from AZTEC import utilities
from AZTEC.actions import erase_device, has_not_booted, prepare_device, restore_device
from AZTEC.device import create_or_update_record, firmware_check, report_end_time


def main():
    """Handles the attach logic; called from cfgutil --on-attach."""

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

        device = create_or_update_record(session_ECID)

        while has_not_booted(device):
            device = create_or_update_record(device["ECID"])

        if device["status"] in { "new", "error" }:

            # Get the latest firmware this device model supports
            latest_firmware = firmware_check(device["deviceType"])

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
            supervision_state = strtobool(device["isSupervised"])

            # Check device's current state
            if activation_state == "Unactivated":
                # Prepare Device
                prepare_device(device)

            elif ( activation_state == "Activated" and supervision_state == True ):

                if device["status"] == "check":
                    # Add the end time to the database
                    report_end_time(device)

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
                device_logger.warning("\u26A0 Current device status:  {}".format(device["status"]))

                # Erase the device
                erase_device(device)


if __name__ == "__main__":
    main()
