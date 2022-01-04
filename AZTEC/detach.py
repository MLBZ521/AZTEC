import os

from AZTEC import utilities
from AZTEC.db_utils import Query


def main():
    """Handles the detach logic; called from cfgutil --on-detach."""

    main_logger = utilities.log_setup()

    # Get the sessions' device ECID (this will be our primary unique 
    # identifier for this device during for subsequent sessions )
    session_ECID = os.getenv('ECID')

    if not session_ECID:

        main_logger.error("\U0001F6D1 Unable to detect connect device details!")

    else:

        device_logger = utilities.log_setup(log_name=session_ECID)

        # If a device was successfully detected
        device_logger.info("[DETACH WORKFLOW]")

        # Get the device's details
        with Query() as run:
            device = run.execute('SELECT * FROM devices WHERE ECID = ?', 
                (session_ECID,)).fetchone()

        # If a device was retrived
        if device:

            # Check device's current state
            if device['status'] == "erasing":

                device_logger.info("\U0001F4A5 Erased device!")

                # Update status in the database
                with Query() as run:
                    results = run.execute('UPDATE devices SET status = ? WHERE ECID = ?', 
                        ("erased", session_ECID))

            # Check device's current state
            elif device['status'] == "done":

                device_logger.info("\u2796 Removing device from queue...")

                # Delete device's record in the devices table
                with Query() as run:
                    run.execute("DELETE FROM devices WHERE ECID = ?", (session_ECID,))

                device_logger.info("\U0001F44C Device removed from queue")

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

                    device_logger.info("\u2705 [COMPLETE] Device reprovisioned in "
                        "Hours: {:02}  Minutes: {:02}  Seconds: {:02}".format(
                            int(hours), int(minutes), int(seconds)))

                except:
                    device_logger.warning("\u26A0 [WARNING] Error in timing mechanism!")

        else:
            device_logger.error("\U0001F6D1 [ERROR] Device is not in the queue!")


if __name__ == "__main__":
    main()
