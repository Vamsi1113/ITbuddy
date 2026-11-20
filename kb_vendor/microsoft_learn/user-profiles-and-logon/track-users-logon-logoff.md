<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/user-profiles-and-logon/track-users-logon-logoff -->
# How to track users logon/logoff

Describes how to track users logon/logoff.

This article describes how to track users logon/logoff.

Applies to:   Windows Server 2003
_Original KB number:_   556015

This article was written by Yuval Sinay, Microsoft MVP.

## Summary

The following article will help you to track users logon/logoff.

## Tips

### Option 1

1. Enable Auditing on the domain level by using Group Policy:

   **Computer Configuration/Windows Settings/Security Settings/Local Policies/Audit Policy**

   There are two types of auditing that address logging on, they are **Audit Logon Events** and **Audit Account Logon Events**.

   Audit "logon events" records logons on the PC(s) targeted by the policy and the results appear in the Security Log on that PC(s).

   Audit "Account Logon" Events tracks logons to the domain, and the results appear in the Security Log on domain controllers only.

2. Create a logon script on the required domain/OU/user account with the following content:

   `echo %date%,%time%,%computername%,%username%,%sessionname%,%logonserver% >>`

3. Create a logoff script on the required domain/OU/user account with the following content:

   `echo %date%,%time%,%computername%,%username%,%sessionname%,%logonserver% >>`

> [!Note]
> Please be aware that unauthorized users can change this scripts, due the requirement that the SHARENAME$ will be writeable by users.

### Option 2

Use WMI/ADSI to query each domain controller for logon/logoff events.

_Source: Microsoft Learn, licensed CC BY 4.0._
