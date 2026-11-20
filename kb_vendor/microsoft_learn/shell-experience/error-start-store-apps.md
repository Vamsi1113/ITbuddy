<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/error-start-store-apps -->
# Fail to start Microsoft Store apps

You receive an error message when you try to start a Windows Store app in Windows 8 or Windows Server 2012.

This article helps fix an error (This app has been blocked by your system administrator) that occurs when you to start Microsoft Store apps.

_Original KB number:_   2750770

## Symptoms

When you try to start a Microsoft Store app in Windows 8 or in Windows Server 2012, the operation fails. Additionally, you receive the following error message:

> This app has been blocked by your system administrator.

## Cause

This issue occurs because an administrator has deployed an application control policy (AppLocker) on the computer. By design, all Microsoft Store apps are blocked if an AppLocker policy is applied.

## Resolution

To allow the Microsoft Store app to run, a domain administrator can use AppLocker to edit application control policies. To do so, use one of the following methods, whichever is most appropriate to their situation:

1. Create a default rule that allows all Microsoft Store apps.
2. Create rules that allow individual Microsoft Store apps.

> Note:
> The rules must be edited from a Windows Server 2012-based domain controller or from a Windows 8-based computer that has the Remote Server Administration Tools installed.

## More information

For more information about AppLocker, see the following articles:

- AppLocker overview)

- Create a rule for packaged apps)

_Source: Microsoft Learn, licensed CC BY 4.0._
