<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/group-policy/archived-application-cant-be-restored -->
# Archived application can't be restored

Group Policy settings may block automatic application updates. Blocked on-demand applications must be updated by other means before they can be used.

This article provides a solution to an issue that archived application can't be restored because of app update policies.

Applies to:   Windows 10 - all editions
_Original KB number:_   4571552

## Summary

To reduce disk space usage, Windows automatically archives applications that you don't use frequently. On a new Windows device, some applications are archived out-of-the-box. The first time you start an archived application, the application has to be restored. To do it, it connects to the internet to download and install the full version.

In some environments, Group Policy Objects (GPOs) may block applications from automatically downloading in this manner. When you start such a blocked application, you receive a message that resembles the following.

> Voice Recorder needs an update, but we're unable to apply the update right now.

In these cases, you have to contact your system administrator to obtain an updated version of the application. The information in this article helps you to do this.

## More information

The following GPOs prevent archived applications from restoring full versions:

- UpdateServiceUrl
- AllowUpdateService

If either or both of these GPOs are enabled in your environment, your system administrator can use one of the following methods to push the full version of the application to the device:

- If your organization uses Microsoft Store for Business to manage applications, the system administrator can push the application to the business store.
- If your organization uses Microsoft Intune to manage devices, the system administrator can package the application and push the package to managed devices.
- If your organization uses custom Windows images to provision devices, the system administrator can use the DISM App Package tool to add the full resource packages for the application to the image. By using `dism /StubPackageOption:installfull`, the system administrator can make sure that the device is provisioned by using the full version of the application instead of the archived version.

_Source: Microsoft Learn, licensed CC BY 4.0._
