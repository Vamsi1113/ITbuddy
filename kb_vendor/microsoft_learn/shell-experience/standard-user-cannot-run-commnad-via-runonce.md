<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/standard-user-cannot-run-commnad-via-runonce -->
# Can't execute commands with RunOnce and RunOnceEx

Fixes an issue where standard users can't execute a command set via RunOnce or RunOnceEx.

This article provides help to fix an issue where standard users can't execute a command set via RunOnce or RunOnceEx.

Applies to:   Windows 10 - all editions
_Original KB number:_   2021405

## Symptoms

A command set to execute via RunOnce or RunOnceEx may not execute as expected.
The registry keys affected are:

- `HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce`
- `HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnceEx`
- `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Runonce`
- `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\RunonceEx`

## Cause

This will occur if you log on with a Standard User Account.
This is by design.

## Resolution

To execute commands from those registry keys, you must log in with an Administrator account. This issue effects only users with a Standard User account. If the user has an Administrator or Split Token, the execution proceeds.

_Source: Microsoft Learn, licensed CC BY 4.0._
