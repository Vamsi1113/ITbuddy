<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/assigned-access-kiosk-users-cant-use-quick-settings-menu -->
# Assigned access kiosk users can't use the quick settings

Kiosk or assigned access users don't have access to quick settings.

## Summary

Assigned access users can't use the quick settings feature of Windows. By default, this feature is disabled in assigned access environments (also known as kiosk environments).

> Note:
>
> - In earlier versions of Windows, the quick settings feature was referred to as Quick Actions or Control Center.
> - The quick settings area is immediately to the left of the clock display in the taskbar. Typically, the quick settings area displays system icons such as the network, volume, and battery icons.

## Symptoms

You apply an assigned access configuration to a set of users to designate them as kiosk users. Afterward, when one of those users selects the quick settings area of the Windows taskbar, nothing occurs.

## Cause

This behavior is by design for assigned access users. Quick settings contains configuration and personalization settings that aren't appropriate for a kiosk experience (volume, Wi-Fi connection, Focus Assist, and so on).

## More information

The following policy settings control quick settings:

- Configuration Service Provider (CSP) setting:
  - **Name:** Taskbar: Remove Quick Settings
  - **Path:** `./User/Vendor/MSFT/Policy/Config/Start/DisableControlCenter`

- Group Policy Object (GPO) setting:
  - **Name:** Remove quick settings
  - **Path:** **User Configuration\Administrative Templates\Start Menu and Taskbar\Remove quick settings**

> Important:
> If you change the CSP or GPO setting, you have to restart the device to make the change take effect.

For more information about the settings that apply to assigned access users, see Assigned Access policy settings.

## References

- Assigned Access policy settings
- Remove quick settings
- Policy CSP - Start

_Source: Microsoft Learn, licensed CC BY 4.0._
