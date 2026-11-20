<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/dism-apply-image-command-fails-error-code-5 -->
# DISM /Apply-Image command fails with error code 5 (ERROR_ACCESS_DENIED)

Works around an issue that causes the DISM apply image command to fail with error code 5 (ERROR_ACCESS_DENIED). Occurs when you try to apply a Windows 10 1607 image by using the Windows Subsystem for Linux (WSL) feature.

This article provides a workaround for an issue where `DISM /Apply-Image` command fails with error code 5 (ERROR_ACCESS_DENIED).

Applies to:   Windows 10 - all editions
_Original KB number:_   3179598

## Symptoms

Consider the following scenario:

- You have a Windows 10 image.
- You enable the Windows Subsystem for Linux (WSL) feature.
- You download and install Ubuntu package by using the command that's documented here.
- You capture the Windows 10 image by using the `DISM /Capture-Image` command.
- You try to apply the captured Windows 10 image by using the `DISM /Apply-Image` command.

In this scenario, the `DISM /Apply-Image` command fails with error code 5 (ERROR_ACCESS_DENIED).

## Cause

The files that are installed by the Ubuntu package may cause `DISM /Apply-Image` to fail.

## Workaround

Do not download and install the Ubuntu package before you capture the Windows 10 image by using the `DISM /Capture-Image` command. The Ubuntu package can be downloaded and installed after the Windows 10 image is applied to a device. You can install the Ubuntu package by following the steps in this installation guide.

## More Information

For more information about Windows Subsystem for Linux, see Frequently Asked Questions.

For more information about DISM imaging commands, see DISM Image Management command-line options.

## Data collection

If you need assistance from Microsoft support, we recommend you collect the information by following the steps mentioned in Gather information by using TSS for deployment-related issues.

_Source: Microsoft Learn, licensed CC BY 4.0._
