<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/cannot-set-timezone-automatically -->
# Can't set time zone automatically

Provides several methods to resolve the issue in which you cannot set the time zone automatically.

Applies to:   Windows 10

> Note:
> If you're not a support agent or IT professional, you'll find more helpful information in How to set your time and time zone.

Non-administrator users cannot change or interact with the **Set time zone automatically** setting. The setting is either not visible or is "greyed out" in the **Settings** app. This is by design as the **Set time zone automatically** setting is a system wide setting that applies to all user profiles on a machine.

To resolve this issue, the IT administrators should make sure the setting **Set time zone automatically** is enabled before deployment of a device. If the device is already deployed, you can use one of the following methods mentioned below to enable the setting.

## Use Registry Editor

Run **Registry Editor** as an administrator and follow these steps:

1. <a id="1"></a>Change the **Set time zone automatically** setting and set the data value of the registry entry `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\tzautoupdate\Start` as follows:

    |Value data  |Result  |
    |---------|---------|
    |3     |Enable Set time zone automatically         |
    |4     |Disable Set time zone automatically         |

2. Change the location setting and set the value of the registry entry `HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location\Value` as follows:

    |Value string  |Result  |
    |---------|---------|
    |Allow     |On         |
    |Deny     |Off         |

    > Note:
    > If the **Location** setting is turned off by a group policy, you must reverse the policy otherwise it will override the manual editing of the entry.

## Use Group Policy

To change the registry settings, use Group Policy Preferences) to enable the **Set the time zone automatically** setting. Next, follow these steps to enable the **Location** setting in **Local Group Policy Editor**.

1. Go to **Computer Configuration** > **Administrative Templates** > **Windows Components** > **Location and Sensors** > **Windows Location Provider** > **Turn off Windows Location Provider**.
2. Set the value of the **Turn off Windows Location Provider** setting to **Not Configured** as follows:

## Use MDM policy

Run a PowerShell script to change the registry settings in Microsoft Intune. Next, use the mobile device management (MDM) policy Privacy/LetAppsAccessLocation to enable the **Location** setting as follows:

|Value  |Result  |
|---------|---------|
|0     |User in control         |
|1     |Force allow         |
|2     |Force deny         |

> Note:
> The recommended value is *0*, but setting the value to *1* ensures that automatic time zone gets the correct location.

For more information about other options to control applications access to the location, see Privacy/LetAppsAccessLocation_ForceAllowTheseApps, Privacy/LetAppsAccessLocation_ForceDenyTheseApps and Privacy/LetAppsAccessLocation_UserInControlOfTheseApps.

_Source: Microsoft Learn, licensed CC BY 4.0._
