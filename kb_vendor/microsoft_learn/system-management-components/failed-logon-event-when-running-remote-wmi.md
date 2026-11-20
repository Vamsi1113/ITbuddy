<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/system-management-components/failed-logon-event-when-running-remote-wmi -->
# Failed logon event when running remote WMI

Describes an issue where a failed logon event is generated when you run remote WMI command.

This article describes an issue where a failed logon event is generated when you run remote WMI command.

Applies to:   Windows 7 Service Pack 1, Windows Server 2012 R2
_Original KB number:_   2816192

## Symptoms

Consider the following scenario:

- You've two or more computers running Windows.
- The computers are set up in a workgroup or domain environment.
- You run a remote WMI query using an application that makes WMI calls from one computer to another computer.

In this scenario, if you review the Security log on the remote computer, you'll notice an Event ID 4625 that's for a failed logon with bad username or password. You'll also note then there's a successful logon with the credentials specified on the remote WMI query.

## Cause

The pass-through authentication is always attempted first, even if specific credentials are specified in the tool being used.

## Resolution

You can safely ignore the error message.

## Data collection

If you need assistance from Microsoft support, we recommend you collect the information by following the steps mentioned in Gather information by using TSS for User Experience issues.

_Source: Microsoft Learn, licensed CC BY 4.0._
