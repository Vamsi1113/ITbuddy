<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/kiosk-mode-known-issues -->
# Kiosk mode known issues

Learn about known issues for devices that run in single-app kiosk mode or restricted user experience mode.

This article discusses known problems for devices that run in single-app kiosk mode or restricted user experience (multi-app kiosk) mode. You can often resolve these issues by making configuration changes or installing cumulative updates. Future releases should automatically resolve some of these issues.

## Restrictions dialog box on sign-in if Microsoft Edge is an allowed app

On kiosks that have Microsoft Edge as an allowed app, a **Restrictions** dialog box appears during sign-in and displays the following message:

> This operation is canceled due to restrictions in effect on this computer. Please contact your system administrator.

This issue is fixed in Windows builds 26100.7705, 26200.7705, and later builds. To put these fixes into effect, redeploy the kiosk configuration.

## Kiosk policies don't deploy, and you receive error code 0x86000005

When you use certain mobile device management (MDM) providers, kiosk policies don't deploy, and you receive error code `0x86000005`. This issue occurs on builds between build 26100.4484 and build 26100.7705.

This issue is fixed in Windows builds 26100.7705, 26200.7705, and later builds.

## File Explorer shows a blocked location dialog box

You have a kiosk that uses File Explorer restrictions and has the Shared PC mode feature configured. When you open File Explorer, you see the following message:

> We can't open This PC. To help you keep your data safe, the location is blocked.

This issue is fixed in Windows builds 26100.8524, 26200.8524, and later builds.

## Packaged apps don't start when Microsoft Edge is an allowed app

On kiosks that have Microsoft Edge as an allowed app, packaged apps (apps that are installed from an MSIX or APPX package) don't start.

To work around this issue, find the name of the .exe file that the packaged app starts. To find the .exe file name, open the app's installation folder, locate and open the AppxManifest.xml file, and then look for the `Executable` attribute of the `Application` element.

In the allowed apps list in your Assigned Access configuration file, add the .exe file name, and specify the `DesktopAppPath` attribute for the file.

_Source: Microsoft Learn, licensed CC BY 4.0._
