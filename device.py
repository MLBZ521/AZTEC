import os
import time

import utilities
from db_utils import Query


def get_session_info(ECID):
    """Gets the provided ECID's current status

    Args:
        ECID:  Device's ECID
    Returns:  
        JSON object of the device's current status
    """

    device_logger = utilities.log_setup(log_name=ECID)
    device_logger.debug("Getting session info...")

    results_get_session_info, json_data = utilities.execute_cfgutil( ECID,
        "get activationState bootedState isSupervised UDID serialNumber deviceType buildVersion \
            firmwareVersion locationID batteryCurrentCapacity batteryIsCharging" )

    # Verify success
    if results_get_session_info["success"]:
        # Load the JSON into an Object
        # print("\tReturning session info:  {}".format(results_get_session_info["stdout"]))
        
        return json_data

    # print("\tERROR:  \u26A0 Unable to obtain device info")
    # print("\tReturn Code:  {}".format(results_get_session_info["exitcode"]))
    # print("\tstdout:  {}".format(results_get_session_info["stdout"]))
    # print("\tstderr:  {}".format(results_get_session_info["stderr"]))

    # Try again
    time.sleep(5)
    # print("get_session_info > get_session_info")
    get_session_info(ECID)


def create_or_update_record(ECID, status=None):
    """Create or update a record in the database.

    Args:
        ECID (str): The ECID of a device
        status (str): The "status" to label a device in the database

    Returns:
        dict: An object of the devices' record in the database
    """

    device_logger = utilities.log_setup(log_name=ECID)
    session_info_full = get_session_info(ECID)

    activationState = session_info_full["activationState"]
    batteryCurrentCapacity = session_info_full["batteryCurrentCapacity"]
    batteryIsCharging = session_info_full["batteryIsCharging"]
    bootedState = session_info_full["bootedState"]
    buildVersion = os.getenv("buildVersion") or session_info_full["buildVersion"]
    deviceType = os.getenv("deviceType") or session_info_full["deviceType"]
    firmwareVersion = os.getenv("firmwareVersion") or session_info_full["firmwareVersion"]
    locationID = os.getenv("locationID") or session_info_full["locationID"]
    isSupervised = session_info_full["isSupervised"]
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
            run.execute("INSERT INTO devices ( status, ECID, UDID, SerialNumber, \
                deviceType, buildVersion, firmwareVersion, locationID, activationState, \
                bootedState, isSupervised, batteryCurrentCapacity, batteryIsCharging) \
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ( status, ECID, udid, serial_number, deviceType, buildVersion, firmwareVersion, 
                locationID, activationState, bootedState, isSupervised, batteryCurrentCapacity, 
                batteryIsCharging) )

        # Get current epoch time
        currentTime = time.time()

        # Update the report table
        run.execute("INSERT INTO report (id, start_time) VALUES (?, ?)", 
            (device["id"], currentTime) )

    else:

        if not status:
            status = device["status"]

        # Update status in the database
        with Query() as run:
            results = run.execute('UPDATE devices ( status, UDID, SerialNumber, \
                deviceType, buildVersion, firmwareVersion, locationID, activationState, \
                bootedState, isSupervised, batteryCurrentCapacity, batteryIsCharging) \
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?), WHERE ECID = ?', 
                (status, udid, serial_number, deviceType, buildVersion, firmwareVersion, 
                locationID, activationState, bootedState, isSupervised, batteryCurrentCapacity, 
                batteryIsCharging, ECID))

    # Get the device's details
    return run.execute('SELECT * FROM devices WHERE ECID = ?', 
        (ECID,)).fetchone()
