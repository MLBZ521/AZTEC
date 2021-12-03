import sqlite3
import sys


class Query():
    """A Class that creates a Context Manager to interact with a sqlite database"""

    def __init__(self, database="devices.db", timeout=10):
        self.database = database
        self.timeout = timeout

    def __enter__(self):
        """Opens a connection to the database"""

        self.db_connection = sqlite3.connect(self.database, timeout=self.timeout)
        self.db_connection.isolation_level = None
        self.db_connection.row_factory = sqlite3.Row

        # Check if there is a ongoing transaction
        if self.db_connection.in_transaction:
            print("Sleep")
            time.sleep(random.uniform(1, 3))

        return self.db_connection.cursor()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Commits and closing connection to the database"""
        # Commit the transaction
        self.db_connection.commit()

        # Close the connection
        self.db_connection.close()


def init_db(database):
    """
    A helper function to initialize a database

    Args:
        database:  The name of the database file to create
    """

    devices_table = """ CREATE TABLE devices (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            "status" TEXT,
                            ECID TEXT NOT NULL,
                            SerialNumber TEXT,
                            UDID TEXT NOT NULL,
                            deviceType TEXT NOT NULL,
                            buildVersion TEXT NOT NULL,
                            firmwareVersion TEXT NOT NULL,
                            locationID TEXT NOT NULL
                        ); """

    report_table = """ CREATE TABLE IF NOT EXISTS report (
                            id INTEGER,
                            start_time INTEGER,
                            end_time INTEGER
                        ); """

    print("Initalizing the database...\n")

    # Check if the tables exist
    with Query() as run:
        result_devices = run.execute( 
            "SELECT count(name) FROM sqlite_master WHERE type='table' AND name='devices'" 
                ).fetchone()
        result_report = run.execute( 
            "SELECT count(name) FROM sqlite_master WHERE type='table' AND name='report'" 
                ).fetchone()

    # 1 = exists
    if result_devices[0] != 1:

        # Create the devices table
        with Query() as run:
            results = run.execute(devices_table)

    else:

        # Purge the devices table
        with Query() as run:
            run.execute( "DELETE FROM devices" )

    # 1 = exists
    if result_report[0] != 1:
        
        # Create the report table
        with Query() as run:
            results = run.execute(report_table)


if __name__ == "__main__":
    init_db(sys.argv[1])
