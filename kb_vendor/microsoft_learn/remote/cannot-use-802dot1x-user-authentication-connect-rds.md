<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/remote/cannot-use-802dot1x-user-authentication-connect-rds -->
# 802.1x user authentication fails when an RDS connection comes in

Fix an issue that occurs when end user uses remote desktop connection to log on to a 802.1x secured Windows 7, Windows 8 or Windows 10 machine that is configured user authentication only.

This article helps fix an issue that occurs when end user uses remote desktop connection to log on to a 802.1x secured Windows 7, Windows 8 or Windows 10 machine that is configured user authentication only.

Applies to:   Windows 7 Service Pack 1, Windows 8, Windows 10
_Original KB number:_   2820847

## Symptoms

End user uses remote desktop connection to log on to a 802.1x secured Windows 7, Windows 8 or Windows 10 machine that is configured user authentication only. After about one minute, the connection is lost, and the user are unable to re-establish the remote connection. A local (console) logon may resolve the issue.

## Cause

When 802.1x authentication mode is configured to user authentication, the supplicant fails to query the user token in the remote desktop session.

## Resolution

To make remote desktop connection works with 802.1x authentication, we must use computer authentication or "User or computer authentication"

_Source: Microsoft Learn, licensed CC BY 4.0._
