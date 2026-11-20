<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/windows-security/requested-key-id-is-invalid -->
# The requested Key ID is invalid

Provides a solution to an error that occurs when you try to retrieve BitLocker Recovery Key using MBAM 2.0 Self Service Portal (SSP).

This article provides a solution to an error that occurs when you try to retrieve BitLocker Recovery Key using MBAM 2.0 Self Service Portal (SSP).

_Original KB number:_   2870853

## Summary

When a user tries to retrieve BitLocker Recovery Key using MBAM 2.0 Self Service Portal (SSP), it may give you the following error message:

> The requested Key ID is invalid for the current user.

## More information

In MBAM 2.0, the Recovery Key ID is only shown to the user, if the user who is requesting the key has logged on to the machine at least once. Also, in MBAM 2.0, SQL database maintains the list of logon user after MBAM 2.0 agent is installed and always verifies if the user has logged in to the machine or not.

For example:

- User A logins to Computer A.
- Computer A asks for BitLocker Recovery Key due to some changes done on the machine.
- User A goes to Computer B and logins to Windows.
- Open MBAM 2.0 Self Service Portal (`https://mbamserver/selfservice`).
- Enter the first eight digits of recovery key ID and MBAM 2.0 SSP page will show the user the recovery key.
- Let's say if user A never logged in to computer A, then we won't show the user the key and will throw the above message.

_Source: Microsoft Learn, licensed CC BY 4.0._
