<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/networking/network-connectivity-lost -->
# Network connectivity is lost

Information about Microsoft Defender Antivirus antimalware platform update to solve problem of vpn users losing network connectivity.

This article provides a solution to an error that occurs when you use the Network Protection feature in Windows Defender Exploit Guard in Audit or Block mode and a virtual private network (VPN).

Applies to:   Windows 10 - all editions
_Original KB number:_   4560203

## Symptoms

When using the Network Protection feature in Windows Defender Exploit Guard in Audit or Block mode and a virtual private network (VPN), you lose network connectivity and receive the **General Failure** error message when pinging an IP address.

## Cause

This issue occurs because the current (4.12.x.x) antimalware platform update supporting the Network Protection feature is missing.

## Solution

Install the latest (4.18.x.x) antimalware platform update as described here:

- Update for Windows Defender antimalware platform.
- Manage Windows Defender Antivirus updates and apply baselines.
- SCCM-Endpoint Protection: Enabling "Platform Update" for Microsoft Defender AV via SCCM ADR (Part 4).

## Workaround

Set the following  Group Policy to **Not Configured**:

Computer Configuration > Administrative Templates > Windows components > Windows Defender Antivirus > Windows Defender Exploit Guard > Network protection > Prevent users and apps from accessing dangerous websites

_Source: Microsoft Learn, licensed CC BY 4.0._
