import os
import plistlib
import time

from pkg_resources import parse_version

import requests

from AZTEC import cfgutil
from AZTEC import utilities
from AZTEC.db_utils import Query


def get_session_info(ECID):
    """Gets the provided ECID's current session info.

    Args:
        ECID (str): ECID of a device

    Returns:  
        json_data (dict):  Dict object of the device's current status
    """

    device_logger = utilities.log_setup(log_name=ECID)
    device_logger.debug("Getting session info...")

    results_get_session_info, json_data = cfgutil.execute( ECID,
        "get activationState bootedState isSupervised UDID serialNumber deviceType buildVersion \
            firmwareVersion locationID batteryCurrentCapacity batteryIsCharging" )

    # Verify success
    if results_get_session_info["success"]:
        return json_data

    # device_logger.error(
    #     "\u26A0 Unable to obtain device info\nReturn Code:  {}\nstdout:  {}\nstderr:  {}".format(
    #         results_get_session_info["exitcode"], 
    #         results_get_session_info["stdout"], 
    #         results_get_session_info["stderr"]))

    # Try again
    time.sleep(5)
    get_session_info(ECID)


def create_or_update_record(ECID, status=None):
    """Create or update a record in the database.

    Args:
        ECID (str): ECID of a device
        status (str): The "status" to label a device in the database

    Returns:
        device (dict): Dict object of the devices' record in the database
    """

    device_logger = utilities.log_setup(log_name=ECID)
    session_info_full = get_session_info(ECID)

    activationState = session_info_full["activationState"]
    batteryCurrentCapacity = session_info_full["batteryCurrentCapacity"]
    batteryIsCharging = "True" if session_info_full["batteryIsCharging"] else "False"
    bootedState = session_info_full["bootedState"]
    buildVersion = os.getenv("buildVersion") or session_info_full["buildVersion"]
    deviceType = os.getenv("deviceType") or session_info_full["deviceType"]
    firmwareVersion = os.getenv("firmwareVersion") or session_info_full["firmwareVersion"]
    locationID = os.getenv("locationID") or session_info_full["locationID"]
    isSupervised = "True" if session_info_full["isSupervised"] else "False"
    serial_number = session_info_full["serialNumber"]
    udid = os.getenv("UDID") or session_info_full["UDID"]

    # Check if device has been added to database
    with Query() as run:
        device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
            (ECID,)).fetchone()

    if not device:
        # Device is not in the queue, so needs to be erased.
        device_logger.info("\u2795 Adding device to queue...")

        with Query() as run:
            # Add device to database
            results = run.execute(
                """INSERT INTO devices 
                ( status, ECID, UDID, SerialNumber, deviceType, buildVersion, firmwareVersion, 
                locationID, activationState, bootedState, isSupervised, batteryCurrentCapacity, 
                batteryIsCharging ) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ( "new", ECID, udid, serial_number, deviceType, buildVersion, firmwareVersion, 
                locationID, activationState, bootedState, isSupervised, batteryCurrentCapacity, 
                batteryIsCharging ) 
            )

            # Get current epoch time
            currentTime = time.time()

            # Update the report table
            run.execute("INSERT INTO report (id, start_time) VALUES (?, ?)", 
                (results.lastrowid, currentTime) )

    else:

        # Device is already in the queue.
        device_logger.info("\u2795 Updating queue...")

        if not status or status == "new":
            status = device["status"]

        # Update status in the database
        with Query() as run:
            results = run.execute(
                """UPDATE devices SET 
                status = ?, UDID = ?, SerialNumber = ?, deviceType = ?, buildVersion = ?, 
                firmwareVersion = ?, locationID = ?, activationState = ?, bootedState = ?, 
                isSupervised = ?, batteryCurrentCapacity = ?, batteryIsCharging = ? 
                WHERE ECID = ?""",
                (status, udid, serial_number, deviceType, buildVersion, firmwareVersion, 
                locationID, activationState, bootedState, isSupervised, batteryCurrentCapacity, 
                batteryIsCharging, ECID)
            )

    # Get the device's details
    with Query() as run:
        device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
            (ECID,)).fetchone()

    return device


def report_end_time(device):
    """Updates the database when the device has completed the provisioning process.

    Args:
        device (dict):  Object of device's information from the database
    """

    device_logger = utilities.log_setup(log_name=device["ECID"])

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


def firmware_check(model):
    """Gets the latest compatible firmware version of a iOS, iPadOS, or tvOS Device.

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
    content = plistlib.loads(response.text.encode("utf-8"))

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
