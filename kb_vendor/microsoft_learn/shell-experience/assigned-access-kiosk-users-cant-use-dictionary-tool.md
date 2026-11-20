<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/assigned-access-kiosk-users-cant-use-dictionary-tool -->
# Assigned access kiosk users can't use the Japanese User Dictionary Tool

Discusses an issue in which assigned access kiosk users can't use the Japanese User Dictionary Tool because the tool isn't on the list of allowed applications.

## Summary

By default, when you configure a Windows 11 multi-app kiosk for assigned access users, the allowed applications list doesn't include the Japanese User Dictionary Tool. This article describes the issue and explains how to to enable the tool for assigned access users by adding the tool's files to your assigned access configuration XML file.

## Symptoms

In a Windows 11 multi-app kiosk environment (also referred to as a restricted user experience), an assigned access user tries to open the Japanese User Dictionary Tool. The tool doesn't open, and the user receives the following message:

> This operation has been cancelled due to restrictions in effect on this computer. Please contact your system administrator.

## Cause

AppLocker generates this message because the Japanese User Dictionary Tool isn't one of the allowed applications for the multi-app kiosk.

## Resolution

To include the Japanese User Dictionary Tool as one of the kiosk apps, add the following XML elements to the `<AllowedApps>` section of the assigned access configuration XML file:

```xml
<App DesktopAppPath="C:\Windows\System32\IME\IMEJP\IMJPDCT.EXE"/>
<App DesktopAppPath="C:\Windows\System32\IME\IMEJP\IMJPSET.EXE"/>
<App DesktopAppPath="C:\Windows\System32\IME\IMEJP\IMJPUEX.EXE"/>
<App DesktopAppPath="C:\Windows\System32\IME\IMEJP\IMJPUEXC.EXE"/>
```

For more information, see the AllAppList section of "Create an Assigned Access configuration XML file."

## References

- Create an Assigned Access configuration XML file
- Configure a restricted user experience (multi-app kiosk) with Assigned Access
- Assigned Access examples
- Assigned Access policy settings

_Source: Microsoft Learn, licensed CC BY 4.0._
