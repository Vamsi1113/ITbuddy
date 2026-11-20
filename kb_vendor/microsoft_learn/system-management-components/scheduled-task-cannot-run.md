<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/system-management-components/scheduled-task-cannot-run -->
# Scheduled Task Can't Run an Exe File on a Share Folder

Provides a workaround to an issue in which scheduled task can't run an .exe file on a share folder in Windows.

## Summary

Consider the following scenario:

- You set up a share folder in a domain environment.
- You configure the share or New Technology File System (NTFS) level permission settings on the share folder.
- You set up a task schedule on a client computer. The task runs an .exe file on the share folder.
- Only the user account that is used to run the task has the access permission to the share folder.

In this scenario, the task can't run. You receive an access denied or a not found error.

## More Information

To work around this issue, use one of the following steps:

1. Assign the access permission for the share folder to the client computer.
2. Configure the task to run `cmd /c \\share\name.exe` instead of `\\share\name.exe`.

> Note:
> `\\share\name.exe` is the placeholder of the path of the share folder.

_Source: Microsoft Learn, licensed CC BY 4.0._
