<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/networking/error-open-files-offline-offline-files-wip -->
# Can't open files offline when you use Offline Files and Windows Information Protection

Describes an issue that prevents you from opening files offline when you're using the Offline Files feature together with Windows Information Protection. Occurs in Windows 10 Anniversary Edition. Workarounds are provided.

This article provides workarounds for an issue that prevents you from opening files offline when you're using the Offline Files feature together with Windows Information Protection.

Applies to:   Windows 10 - all editions
_Original KB number:_   3187045

## Symptoms

Consider the following scenario:

- You have Windows 10 installed.
- Special folders (for example, Documents or Favorites) are redirected to a file share.
- User data in the redirected folders is cached locally through the Offline Files feature.
- Windows Information Protection (also known as Enterprise Data Protection) is enabled on the system.
- You're using an application that's managed by Windows Information Protection.

If you try to open a file while working offline in this scenario, the attempt fails. The error message that's displayed in this situation varies, depending on the application. Word and Excel fail with the following error:
> Sorry, we couldn't open '\\\severname\fileshare\filename'

## Cause

This issue occurs because the Offline Files feature doesn't support Windows Information Protection.

## Workaround

To work around this issue, use one of the following methods:

- Open the file by using an application that's not managed by Windows Information Protection.
- Open the file while you're working online (connected to your corporate network).

## More information

There are no plans to update Offline Files to support Windows Information Protection. We recommend that you migrate to a modern file sync solution such as Work Folders or OneDrive for Business.

For information about how to migrate from Offline Files to Work Folders see the following TechNet site:

Offline Files (CSC) to Work Folders Migration Guide

_Source: Microsoft Learn, licensed CC BY 4.0._
