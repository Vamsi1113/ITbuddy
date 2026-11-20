<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/windows-10-not-install-specific-drivers-usb-audio-devices -->
# Windows 10 doesn't install specific drivers for USB audio devices on the first connection

Fixes an issue in which device-specific drivers aren't installed for USB audio devices the first time that you connect the device on Windows 10 Version 1703.

This article helps to fix an issue in which Windows 10 doesn't install specific drivers for USB audio devices on the first connection.

Applies to:   Windows 10, version 1703
_Original KB number:_   4021854

## Symptom

When you connect a USB audio device to a Windows 10 Version 1703-based computer the first time, the operating system detects the device but loads the standard USB audio 2.0 driver (usbaudio2.sys) instead of the specific device driver.

## Cause

This issue occurs because the USB audio 2.0 driver (usbaudio2.sys) isn't classified as a generic driver in Windows 10 Version 1703. Therefore, the system assumes that a compatible, nongeneric driver is installed for the device even though the driver is generic.

This issue also causes Windows 10 Version 1703 to postpone the search for other compatible drivers through Windows Update that typically occurs immediately after you install a new device.

## Resolution

To fix this issue, use one of the following methods.

### Method 1

To resolve this issue, install update 4022716.

### Method 2

If the device-specific driver is distributed through Windows Update, you can manually update the driver by using Device Manager. For more information about how to do this, see update drivers in Windows 10.

### Method 3

If the device is not yet connected, first install the device-specific driver, such as by using the appropriate installer. After the device-specific driver is installed, Windows 10 will select that driver instead of the standard USB audio 2.0 driver when you first connect the device.

> [!Note]
> See the device manufacturer's user guide for specific instructions about how to install the driver.

### Method 4

If the driver isn't distributed through Windows Update, you can manually reinstall the driver. To do this, follow these steps:

1. Install the device-specific driver (see Method 2).
2. Open **Device Manager**.
3. Right-click (or tap and hold) the name of the device, and then select **Uninstall**.
4. Restart the computer.

When it restarts, Windows will try to reinstall the device by using the device-specific driver.

## Data collection

If you need assistance from Microsoft support, we recommend you collect the information by following the steps mentioned in Gather information by using TSS for deployment-related issues.

_Source: Microsoft Learn, licensed CC BY 4.0._
