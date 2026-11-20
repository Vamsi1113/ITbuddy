<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/incomplete-list-modes-in-duplicate-mode -->
# List All Modes displays incomplete list of modes

Provides a solution to an issue where the list of available modes is different than the list displayed in Windows 7 when you use multiple displays in duplicate mode in Windows 8.

This article provides a solution to an issue where the list of available modes is different than the list displayed in Windows 7 when you use multiple displays in "Duplicate" mode in Windows 8.

Applies to:   Windows 8
_Original KB number:_   2813712

## Symptoms

Consider the following scenario:

The operating system is Windows 8 and you are using multiple displays in "Duplicate" mode. When selecting **Advanced Settings** in the Screen Resolution Control Panel and then selecting the **List All Modes** button on the **Adapter** tab of the monitor and display driver dialog box, the list of available modes is different than the list that is displayed in Windows 7.

## Cause

This behavior is by design. The list of display modes available when "Duplicate" mode is selected on a Windows 8 client is based upon the selected primary monitor at the time of selecting Duplicate mode. In Windows 7, all display modes are displayed regardless of the primary monitor selection.

## Resolution

If the desired display mode is not available in "Duplicate" mode, select a different monitor as the primary monitor prior to selecting "Duplicate" display mode.

_Source: Microsoft Learn, licensed CC BY 4.0._
