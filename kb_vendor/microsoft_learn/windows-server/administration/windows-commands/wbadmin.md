<!-- source: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/wbadmin -->
# wbadmin

Reference article for the wbadmin commands, which lets you back up and restore your operating system, volumes, files, folders, and applications from a command prompt.

Enables you to back up and restore your operating system, volumes, files, folders, and applications from a command prompt.

To configure a regularly scheduled backup using this command, you must be a member of the **Administrators** group. To perform all other tasks with this command, you must be a member of the **Backup Operators** group or the **Administrators** group, or you must have been delegated the appropriate permissions.

You must run **wbadmin** from an elevated command prompt, by right-clicking **Command Prompt**, and then selecting **Run as administrator**.

## Parameters

| Parameter | Description |
|--|--|
| wbadmin delete catalog | Deletes the backup catalog on the local computer. Use this command only if the backup catalog on this computer is corrupted and you have no backups stored at another location that you can use to restore the catalog. |
| wbadmin delete systemstatebackup | Deletes one or more system state backups. |
| wbadmin disable backup | Disables your daily backups. |
| wbadmin enable backup | Configures and enables a regularly scheduled backup. |
| wbadmin get disks | Lists disks that are currently online. |
| wbadmin get items | Lists the items included in a backup. |
| wbadmin get status | Shows the status of the currently running backup or recovery operation. |
| wbadmin get versions | Lists details of backups recoverable from the local computer or, if another location is specified, from another computer. |
| wbadmin restore catalog | Recovers a backup catalog from a specified storage location in the case where the backup catalog on the local computer has been corrupted. |
| wbadmin start backup | Runs a one-time backup. If used with no parameters, uses the settings from the daily backup schedule. |
| wbadmin start recovery | Runs a recovery of the volumes, applications, files, or folders specified. |
| wbadmin start sysrecovery | Runs a recovery of the full system (at least all the volumes that contain the operating system's state). This command  is only available if you are using the Windows Recovery Environment. |
| wbadmin start systemstatebackup | Runs a system state backup. |
| wbadmin start systemstaterecovery | Runs a system state recovery. |
| wbadmin stop job | Stops the currently running backup or recovery operation. |

## Related links

- Command-Line Syntax Key

- Windows Server Backup Cmdlets in Windows PowerShell

- Windows Recovery Environment (WinRE)

_Source: Microsoft Learn, licensed CC BY 4.0._
