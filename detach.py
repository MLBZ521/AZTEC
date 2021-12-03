import datetime
import os
import random
import sqlite3
import time


# def get_db_connection():
#     """Opens a connection to the database"""

#     db_connection = sqlite3.connect('devices.db', timeout=15)
#     db_connection.isolation_level = None
#     db_connection.row_factory = sqlite3.Row
#     return db_connection


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



class Transaction:
    """"""

    def __init__(self, query):
        self.database = "devices.db"
        self.query = query
        # self.params = params
        self.timeout = 15

    # Opens a connection to the database
    db_connection = sqlite3.connect(self.database, timeout=self.timeout)
    db_connection.isolation_level = None
    db_connection.row_factory = sqlite3.Row


    def query(self, query):

        # Check if there is a ongoing transaction
        if db_connection.in_transaction:
            print("Sleep")
            time.sleep(random.uniform(1, 3))

        # Update status in the database
        results = db_connection.execute(query)

        # Commit the transaction
        db_connection.commit()

        return results


    def get_device(self, ECID):
        """Gets the device's record from the database given the provided ECID

        Args:
            ECID:  Device's ECID

        Returns:
            object:  sqlite record object
        """

        # Check if there is a ongoing transaction
        if db_connection.in_transaction:
            print("Sleep")
            time.sleep(random.uniform(1, 3))

        # Update status in the database
        device = db_connection.execute('SELECT * FROM devices WHERE ECID = ?', (ECID,)).fetchone()

        # Commit the transaction
        db_connection.commit()

        return device



# def transaction(query):

#     # Get DB Connection
#     db_connection = get_db_connection()

#     # Check if there is a ongoing transaction
#     if db_connection.in_transaction:
#         print("Sleep")
#         time.sleep(random.uniform(1, 3))

#     # Update status in the database
#     db_connection.execute(query)

#     # Commit the transaction
#     db_connection.commit()


def main():

    # Get the sessions' device ECID (this will be our primary unique 
    # identifer for this device during for subsequent sessions )
    session_ECID = os.getenv('ECID')

    print("{}:  [DETACH WORKFLOW]".format(session_ECID))

    if session_ECID:

        # Check if the device already exists in the table
        # device = get_device(session_ECID)

        with Transaction() as tx:
            device = tx.get_device(session_ECID)

        if device:

            # Get the devices' serial number (this will be for user facing content)
            serial_number = device["SerialNumber"]

            # Get DB Connection
            # db_connection = get_db_connection()

            # Check device's current state
            if device['status'] == "erasing":

                print("\t{}:  Erased device!".format(serial_number))


                with Transaction() as tx:
                    results = tx.query('UPDATE devices SET status = ? WHERE ECID = ?', ("erased", session_ECID))


                # if db_connection.in_transaction:
                #     print("Sleep")
                #     time.sleep(random.uniform(1, 3))

                # Update status in the database
                # db_connection.execute('UPDATE devices SET status = ? WHERE ECID = ?',
                #     ("erased", session_ECID))

                # db_connection.commit()

            # Check device's current state
            elif device['status'] == "done":

                print("\t{}:  Removing device from queue...".format(serial_number))

                # if db_connection.in_transaction:
                #     print("Sleep")
                    # time.sleep(random.uniform(1, 3))

                # Delete device's record in the devices table
                # db_connection.execute("DELETE FROM devices WHERE ECID = ?", (session_ECID,))

                # db_connection.commit()

                with Transaction() as tx:
                    results = tx.query("DELETE FROM devices WHERE ECID = ?", (session_ECID,))


                print("\t{}:  Device removed from queue".format(serial_number))

                # Get device's current ID
                identifier = device['id']

                # Get the time from the report table
                report = db_connection.execute("SELECT * FROM report WHERE id = ?", (identifier,)).fetchone()

                # Get the difference in the start and end times
                difference = int(report["end_time"]) - int(report["start_time"])

                # Build readable output
                hours, remainder = divmod(int(difference), 3600)
                minutes, seconds = divmod(remainder, 60)

                print("\t{}:  [COMPLETE] Device reprovisioned in Hours: {:02}  Minutes: {:02}  Seconds: {:02}".format(serial_number, int(hours), int(minutes), int(seconds)))

            db_connection.close()

    else:

        print("\t{}:  [ERROR] Cannot find device information!".format(serial_number))


if __name__ == "__main__":
    main()
