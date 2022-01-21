# **A**utomated **Z**ero **T**ouch **E**nrollment **C**onfigurator
======

AZTEC utilizes the Apple Configurator Automation Tools (`cfgutil`) to automate the provisioning process of Apple Devices.

## About

AZTEC is a Python3 application that utilizes `cfgutil` to execute workflows when a device is connected (attached) or disconnected (detached) from a Mac.  This process was written to be able to quickly provision large batches (hundreds) of devices in a short amount of time.  Apple Configurator, as of July 2020, is limited to 64 devices connected at one time, I do not know if `cfgutil` has the same limitation, but you'll also be limited to the power requirements of each device and each hub on each USB port of the host Mac.

While Apple and every MDM vendor boast "Zero Touch Enrollment," that's technically mis-leading.  Yes, it does _now_ exist with macOS 11+ on Macs and Apple TVs, however, on devices running iOS/iPadOS, this not the case.  A human has to connect the device to the internet and complete the Setup Assistant.  The Apple Configurator Automation Tools provide a method get this experience.

There are a few other tools out there that do something similar; mainly, AZTEC differs by being simple -- it doesn't try to configure the device, instead AZTEC attempts to provide a zero touch method to wipe and perform an Automated Device Enrollment while being MDM agnostic.  So all the MDM admin has to do is configure the MDM side with how the device should be setup (enrollment settings, Configuration Profiles, VPP Apps, etc.) and AZTEC will essentially "push the buttons" for the admin during Setup Assistant.

Executing AZTEC simply launches `cfgutil` to monitor for devices being attached and detached from the host Mac.  From there, AZTEC _attempts_ to keep track of the progress of the device while performing a (re-)provisioning workflow.  I say _attempts_ because after running, for example, an erase command with `cfgutil`, the device will reboot, which causes it to become "detached" and then once it boots, it will be "attached" again.  So `cfgutil` itself does not track and is unable to determine what previous action was taken on a device.

Several iterations of this script have been used and improved upon and I've attempted to account for the quirks experienced.  Known errors are checked and handled if possible, while some others....I haven't been able to find a reliable solution for yet...so a device may end up in an erase loop.


## Details

### How it works

On device attach, device details are gathered and the database is checked to see if it has been attached before.  If it has not, it's details are written to the database and from there the device's firmware is checked to see if it is the latest version, if not the latest firmware is download and installed on the device, which will will perform an erase as well.  If the device is running the latest firmware, it will be erased as well.  Upon rebooting, the device will be told to perform an automated device enrollment.

**Note:**  You are given five seconds to remove a device before an erase command is executed on the device.

Another benefit of utilizing this workflow is it allows the host Mac to cache firmware versions for use by all connected devices, so each device does not have to download the firmware separately and also transfer the firmware via a physical connection instead of downloading it over your network.  The only gotcha currently with this is that each time the firmware, it is extracted by `cfgutil` for each device and `cfgutil` does not perform clean up on its own.  With the firmware being 5GB+ and running through potentially hundreds of devices, you can quickly run out of drive space.  To prevent this, a separate thread is ran in the background every five minutes, to check for and delete those extract firmware versions.

### Verbosity / Logging

Each action is simultaneously written to stdout (Terminal) and to a log file when it is executed.  All INFO and higher-level log entires are written to the "main.log" file while a separate log is tracked for each and every individual device which also contains DEBUG entires.  This is to be able to more easily determine what actions are taken on a single device when reviewing or troubleshooting potential logic issues.

I have included emojis in the log entries to mainly for the console output to make it easier and more obvious to the admin what action is being taken and when a device is "done" and can be unplugged.

### Tracking Re-provisions

Time stamps are added to a reports table in the database for when a device is first attached and when it removed after being provisioned so that calculations can be performed to quickly show how long it took to re-provision each device (averages could also be calculated) which could potentially be provided to the admins management to show how much time is saved from having a human setup each device by hand.


## Contributing

Feel free to contribute!  Feature Requests and Pull Requests are welcome.


## Planned Features

These are the current items I plan to add:
  * Prevent endless looping is a device fails to provision
  * Support Supervision Identity
  * Support optionally upgrading the OS
    * currently upgrading is the default action if a device is out of date and it will take longer to perform

Lofty goals:
  * Wrap a GUI around this process


##  Requirements

Software:
  * Python3 and the below libraries are required on any system that runs this script.
    * The latest version of the script was tested using Python 3.9.2, but I believe most Python3 versions should be supported.
  * Non-standard libraries that are used in this project:
    * requests
  * Apple Configurator
    * Apple Configurator Automation Tools

Hardware:
  * A host Mac with available USB Ports
  * Optionally, though highly recommended, is a powered USB Hub capable of charging _and_ data
    * Finding a reliable hub seems to be the biggest issue
  * Plenty of USB ports _and_ cables to connect up to as many devices as you'd like to re-provision at once (max 64)


## How to setup and run

Download Apple Configurator and then install the Apple Configurator Automation Tools ( Menu > Apple Configurator 2 > Install Automation Tools... ).

If devices are WiFi only, you'll need to enable the host Mac to share its internet connection in some form.  The most simipliest way to provide internet access is desribed below.

**Note:**  802.1x enabled networks _cannot_ be shared; the host Mac will need to be on a non-802.1x enabled network for this to work.

macOS 10.15 and later:
  * System Preferences > Sharing > 
    * Enable `Content Caching`
    * Within Content Caching, enable `Share: Internet Connection`

macOS 10.14 and earlier
  * System Preferences > Sharing > Internet Sharing
    * Do not enable it yet, first it needs to be configured
  * Select the network interface the Mac is currently using in the `Sharing your connection from:` dropdown menu
  * Select iPad USB (or iPhone/iPod USB) in the `To computers using:` box

To run:
  * `/path/to/AZTEC/main.py [-h] [--database DATABASE] [--reset {true,false,yes,y,no,n}]`

**Note:**  If your Python3 framework is in a different location than what is listed in the shebang (`#!`) in `main.py`, you'll need to prepend the above command with the path to your Python3 framework (or edit the shebang).

Optional Parameters:
  * `[ --help | -h ]`
    * Show help message
  * `[ --database | -d ] DATABASE`
    * Specify a database file to create or use if it already exists
  * `[ --reset | -r ] {true,false,yes,y,no,n}`
    * If the specified database already exists, optionally purge the devices table.


## Licensing Information

MIT License
