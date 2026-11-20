<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/windows-security/specified-account-not-exist-enable-bitlocker -->
# The specified account does not exist when you try to enable BitLocker

Provides a resolution for the issue that the Specified Account does not exist when you try to enable BitLocker

This article provides a resolution to an error (the specified account doesn't exist) that occurs when you try to enable BitLocker.

Applies to:   Windows Server 2012 R2, Windows Server 2008 R2 Service Pack 1, Windows 7 Service Pack 1
_Original KB number:_   2665635

## Symptoms

When a new user logs in to a machine and attempts to enable BitLocker, the following error occurs:

> The specified account does not exist.

## Cause

When the current user account isn't recognized by the AD, BitLocker receives a standard error code - ERROR_NO_SUCH_USER, which is converted to the standard error message: The specified account does not exist.

One reason this error message can be thrown is, if the BitLocker wizard failed to back up the recovery password to Active Directory because the account is not fully replicated to all domain controllers, in particular the one the client connected to.

## Resolution

Wait for AD replication to complete for the account and try again.

_Source: Microsoft Learn, licensed CC BY 4.0._
