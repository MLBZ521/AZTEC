DROP TABLE IF EXISTS devices;

CREATE TABLE devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    "status" TEXT,
    ECID TEXT NOT NULL,
    SerialNumber TEXT NOT NULL,
    UDID TEXT NOT NULL,
    deviceType TEXT NOT NULL,
    buildVersion TEXT NOT NULL,
    firmwareVersion TEXT NOT NULL,
    locationID TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report (
    id INTEGER,
    start_time INTEGER,
    end_time INTEGER
);
