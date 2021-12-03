import os

import utilities
from db_utils import Query


def main():

    # Get the sessions' device ECID (this will be our primary unique 
    # identifer for this device during for subsequent sessions )
    session_ECID = os.getenv('ECID')

    utilities.verbose_output("{}:  [DETACH WORKFLOW]".format(session_ECID), False)

    # If a device was successfully detected
    if session_ECID:

        # Get the device's details
        with Query() as run:
            device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
                (session_ECID,)).fetchone()

        # If a device was retrived
        if device:

            # Get the devices' serial number (this will be for user facing content)
            serial_number = device["SerialNumber"]

            # Check device's current state
            if device['status'] == "erasing":

                utilities.verbose_output("{} | \U0001F4A5 Erased device!".format(serial_number))

                # Update status in the database
                with Query() as run:
                    results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                        ("erased", session_ECID))

            # # Check device's current state
            # elif device['status'] == "reviving":
            #     utilities.verbose_output("{} | \U0001F4A5 Device is rebooting after attempting to revive it from recovery mode...".format(serial_number))

            #     # Update status in the database
            #     with Query() as run:
            #         results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
            #             ("erased", session_ECID))

            # Check device's current state
            elif device['status'] == "done":

                utilities.verbose_output("{} | \u2796 Removing device from queue...".format(serial_number))

                # Delete device's record in the devices table
                with Query() as run:
                    results = run.execute("DELETE FROM devices WHERE ECID = ?", 
                        (session_ECID,))

                utilities.verbose_output("{} | \U0001F44C Device removed from queue".format(serial_number))

                # Get device's current ID
                identifier = device['id']

                # Get the time from the report table
                with Query() as run:
                    report = run.execute("SELECT * FROM report WHERE id = ?", 
                        (identifier,)).fetchone()

                try:
                    # Get the difference in the start and end times
                    difference = int(report["end_time"]) - int(report["start_time"])

                    # Build readable output
                    hours, remainder = divmod(int(difference), 3600)
                    minutes, seconds = divmod(remainder, 60)

                    utilities.verbose_output("{} | \u2705 [COMPLETE] Device reprovisioned in "
                        "Hours: {:02}  Minutes: {:02}  Seconds: {:02}".format(
                            serial_number, int(hours), int(minutes), int(seconds)))

                except:
                    utilities.verbose_output("{} | \u26A0 [WARNING] Error in timing mechanism!".format(serial_number))

        else:
            utilities.verbose_output("{} | \U0001F6D1 [ERROR] Device is not in the queue!".format(session_ECID))

    else:
        utilities.verbose_output("\U0001F6D1 [ERROR] Unable to detect connect device details!")


if __name__ == "__main__":
    main()
