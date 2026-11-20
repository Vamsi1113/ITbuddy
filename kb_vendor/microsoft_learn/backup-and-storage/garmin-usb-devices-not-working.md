<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/backup-and-storage/garmin-usb-devices-not-working -->
# Garmin isn't compatible with Windows 10

Fixes an issue that prevents Garmin wearable devices from working after you've upgraded your computer or device to Windows 10.

This article provides information on how to fix the problem that Garmin wearable devices aren't recognized on Windows 10.

Applies to:   Windows 10, version 1709, Windows 10, version 1607
_Original KB number:_   3183365

## Symptoms

After you upgrade a computer or device to Windows 10, certain Garmin wearable devices may not work as expected when they're connected to a USB port.

Although the Garmin device shows up in Device Manager and is displayed as a connected drive in File Explorer, it isn't accessible. Attempts to access the drive trigger errors such as the following ones:

> Please insert a disk.

> The directory name is invalid.

## Cause

This problem occurs because Garmin devices formatted with FAT12, FAT16, or FAT32 file systems aren't recognized as mass storage devices by a computer or device that's running Windows 10.

## Resolution

To resolve the issue, download and install the latest version of Garmin Express software. The Garmin Express tool recognizes the connected device and updates its boot code to make it compatible with Windows 10.

This issue is documented by Garmin at the following site:

Device is not detected in Windows 10 after updating to the Anniversary update.

To download the latest Garmin Express tool, go to Garmin Express.

_Source: Microsoft Learn, licensed CC BY 4.0._
