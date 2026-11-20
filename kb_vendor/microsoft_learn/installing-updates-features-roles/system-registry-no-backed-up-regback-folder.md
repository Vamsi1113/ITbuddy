<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/installing-updates-features-roles/system-registry-no-backed-up-regback-folder -->
# The system registry is no longer backed up to the RegBack folder starting in Windows 10 version 1803

Starting in Windows 10, version 1803, Windows no longer automatically backs up the system registry to the RegBack folder. System restore points include registry information.

This article discusses a by-design behavior where Windows no longer automatically backs up the system registry to the RegBack folder starting in Windows 10, version 1803.

Applies to:   Windows 10 - all editions
_Original KB number:_   4509719

## Summary

Starting in Windows 10, version 1803, Windows no longer automatically backs up the system registry to the RegBack folder. If you browse to the \\Windows\\System32\\config\\RegBack folder in Windows Explorer, you will still see each registry hive, but each file is 0 kb in size.

## More information

This change is by design, and is intended to help reduce the overall disk footprint size of Windows. To recover a system with a corrupt registry hive, Microsoft recommends that you use a system restore point.

If you have to use the legacy backup behavior, you can re-enable it by configuring the following registry entry, and then restarting the computer:

- Path: `HKLM\System\CurrentControlSet\Control\Session Manager\Configuration Manager\EnablePeriodicBackup`
- Type: REG_DWORD
- Value: 1

Windows backs up the registry to the RegBack folder when the computer restarts, and creates a RegIdleBackup task to manage subsequent backups. Windows stores the task information in the Scheduled Task Library, in the Microsoft\\Windows\\Registry folder. The task has the following properties:

## Data collection

If you need assistance from Microsoft support, we recommend you collect the information by following the steps mentioned in Gather information by using TSS for deployment-related issues.

_Source: Microsoft Learn, licensed CC BY 4.0._
