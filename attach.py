import os
import random
import re
import sqlite3
import sys
import time
import utilities
from pkg_resources import parse_version


def get_db_connection():
    """Opens a connection to the database"""

    db_connection = sqlite3.connect('devices.db', timeout=15)
    db_connection.isolation_level = None
    db_connection.row_factory = sqlite3.Row
    return db_connection


def get_device(ECID):
    """Gets the device's record from the database given the provided ECID

    Args:
        ECID:  Device's ECID

    Returns:
        object:  sqlite record object
    """

    db_connection = get_db_connection()
    device = db_connection.execute('SELECT * FROM devices WHERE ECID = ?', (ECID,)).fetchone()
    db_connection.close()
    return device


def prepare_device(serial_number, ECID):
    """Prepares the provided ECID

    Args:
        ECID:  Device's ECID
        serial_number:  Device' serial number (just to print to stdout)
    """

    print("\t{}:  Preparing".format(serial_number))

    # Get DB Connection
    db_connection = get_db_connection()

    # Check if the device already exists in the table
    device = get_device(ECID)

    results_prepare = utilities.runUtility( "cfgutil --ecid {} --timeout 60 prepare --dep \
    --language en --locale en_US".format(ECID) )

    # Verify success
    if not results_prepare['success']:

        if re.match( "cfgutil: error: The device is already prepared and must be \
        erased to change settings.", results_prepare['stderr'] ):

            # If the device was already prepared, continue on
            print("\t{}:  Device is prepared!".format(serial_number))

            if db_connection.in_transaction:
                print("Sleep")
                time.sleep(random.uniform(1, 3))

            # Update status in the database
            db_connection.execute('UPDATE devices SET status = ? WHERE ECID = ?',
                ("done", ECID))

            db_connection.commit()

            report_end_time(device['id'])

        else:
            # If the device failed to prepare, erase and try again
            print("\t{}:  [ERROR] Failed to prepare the device!".format(serial_number))

            # Add the end time to the database
            erase_device(serial_number, ECID)

    else:

        # Successfully Prepared device
        # print("\t{}:  [COMPLETE]".format(serial_number))
        print("\t{}:  Device has been provisioned".format(serial_number))

        if db_connection.in_transaction:
            print("Sleep")
            time.sleep(random.uniform(1, 3))

        # Update status in the database
        db_connection.execute('UPDATE devices SET status = ? WHERE ECID = ?',
            ("done", ECID))

        db_connection.commit()

        # Add the end time to the database
        report_end_time(device['id'])


def erase_device(serial_number, ECID):
    """Erases the provided ECID

    Args:
        ECID:  Device's ECID
        serial_number:  Device' serial number (just to print to stdout)
    """

    # Erase Device
    print("\t{}:  Erasing device...".format(serial_number))

    results_erase = utilities.runUtility( "cfgutil --ecid {} erase".format(ECID) )

    # Verify success
    if not results_erase['success']:
        print("\tERROR:  Failed to erase the device")
        print("\tReturn Code {}".format(results_erase['exitcode']))
        print("\t{}".format(results_erase['stderr']))


def report_end_time(device_id):
    """Updates the database when the device has completed the provisioning process

    Args:
        device_id:  Device's record ID in the table

    """

    # Get DB Connection
    db_connection = get_db_connection()

    # Get current epoch time
    currentTime = time.time()

    if db_connection.in_transaction:
        print("Sleep")
        time.sleep(random.uniform(1, 3))

    # Update the report table
    db_connection.execute("UPDATE report SET end_time = ? WHERE id = ?", (currentTime, device_id))

    db_connection.commit()


def main():

    # Get the sessions' device ECID (this will be our primary unique 
    # identifer for this device during for subsequent sessions )
    session_ECID = os.getenv('ECID')

    print("{}:  [ATTACH WORKFLOW]".format(session_ECID))

    # Get the devices' serial number (this will be for user facing content)
    results_serial_number = utilities.runUtility( "cfgutil --ecid {} get serialNumber".format(session_ECID) )

    # Verify success
    if not results_serial_number['success']:
        print("\tERROR:  Failed obtain devices' serial number")
        print("\tReturn Code {}".format(results_serial_number['exitcode']))
        print("\t{}".format(results_serial_number['stderr']))

    serial_number = results_serial_number['stdout']

    if session_ECID:

        # Check if the device already exists in the table
        device = get_device(session_ECID)

        # Get DB Connection
        db_connection = get_db_connection()

        if device:

            # Device is has already started the provisioning process
            print("\t{}:  Continuing provisioning process...".format(serial_number))

            # Check device's current state
            if device['status'] == "erased":

                # Sleep while the device erases and starts back up
                time.sleep(60)

                # Prepare Device
                prepare_device(serial_number, session_ECID)

            elif device['status'] == "done":

                # If the device was already prepared, continue on
                print("\t{}:  Device has been provisioned".format(serial_number))
                # print("\t{}:  [COMPLETE]".format(serial_number))

                report_end_time(device['id'])

        else:

            # Device is not in the queue, so needs to be erased.
            print("\t{}:  Adding device queue...".format(serial_number))

            if db_connection.in_transaction:
                print("Sleep")
                time.sleep(random.uniform(1, 3))

            # Add device to database
            result = db_connection.execute("INSERT INTO devices ( \
                status, ECID, SerialNumber, UDID, deviceType, buildVersion, firmwareVersion, \
                locationID) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ( 'erasing', session_ECID, serial_number, os.getenv("UDID"), 
                    os.getenv("deviceType"), os.getenv("buildVersion"), 
                    os.getenv("firmwareVersion"), os.getenv("locationID") 
                    )
                )

            db_connection.commit()

            # Get device's current ID
            identifier = result.lastrowid

            # Get current epoch time
            currentTime = time.time()

            if db_connection.in_transaction:
                print("Sleep")
                time.sleep(random.uniform(1, 3))

            # Update the report table
            db_connection.execute("INSERT INTO report (id, start_time) VALUES (?, ?)",
                (identifier, currentTime) )

            db_connection.commit()

            # Get the latest firmware this device model supports
            latest_firmware = utilities.firmware_check(os.getenv("deviceType"))

            # Check if the current firmware is older than the latest
            if parse_version(os.getenv("firmwareVersion")) < parse_version(str(latest_firmware)) :

                # Update device using Restore, which will also erase it
                print("\t{}:  Erasing and updating device...".format(serial_number))

                results_restore = utilities.runUtility( "cfgutil --ecid {} restore".format(session_ECID) )

                # Verify success
                if not results_restore['success']:
                    print("\tERROR:  Failed to update the device")
                    print("\tReturn Code {}".format(results_restore['exitcode']))
                    print("\t{}".format(results_restore['stderr']))

                # Prepare Device
                prepare_device(serial_number, session_ECID)

            else:

                # Firmware is the latest, so simply erase the device
                erase_device(serial_number, session_ECID)

        # Close database connection
        db_connection.close()

    else:

        print("\t{}:  [ERROR] Cannot find device information!".format(serial_number))


if __name__ == "__main__":
    main()
