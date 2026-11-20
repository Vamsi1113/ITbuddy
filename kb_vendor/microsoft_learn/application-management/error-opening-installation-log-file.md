<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/application-management/error-opening-installation-log-file -->
# Error opening installation log file error when uninstalling an application

Provides a workaround for the issue where an error occurs when you uninstall an application.

Applies to:   Windows 10 - all editions
_Original KB number:_   2564571

## Summary

When you attempt to uninstall any product in "Programs and Features", a new "Windows Installer" window appears and gives the following error:

> Error opening installation log file. Verify that the specified location exists and is writable.

## More information

This issue occurs if the following conditions are true:

- Windows Installer Logging is enabled.
- The Windows Installer engine can't properly write the uninstallation log file.

These conditions occur if the Windows Installer's application heap becomes freed and loses the information on where to store the log file. In this situation, Windows Installer attempts to write to the location *C:\Windows\System32* and addresses it as a file. Proper behavior would be to write to the following location and file name:

*C:\Users\\\<username>\AppData\Local\Temp\MSIxxxxxx.log*.

Microsoft has confirmed it to be a problem in the operating systems listed in the Applies To section of this article.

To work around this issue, stop and restart the Explorer.exe process using Task Manager.

_Source: Microsoft Learn, licensed CC BY 4.0._
