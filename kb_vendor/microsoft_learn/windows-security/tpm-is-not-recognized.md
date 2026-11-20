<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/windows-security/tpm-is-not-recognized -->
# Trusted Platform Module (TPM) isn't recognized

TPM isn't recognized on some Windows 7 devices. Provides a resolution.

This article solves the issue that a TPM isn't recognized as a compatible device on some Windows 7 devices.

Applies to:   Windows 10 - all editions
_Original KB number:_   2895212

## Symptoms

On some Windows 7 devices, a TPM isn't recognized as a compatible device. And it can't be used for certain applications, such as BitLocker Drive Encryption and Virtual Smart Card. Additionally, if you check the status of the TPM by using Windows TPM Management Console, you receive a **Compatible TPM cannot be found** message.

Also, you may experience the same behavior on some Windows-based devices when you do an in-place upgrade from Windows XP or Windows Vista to Windows 7.

## Cause

This issue occurs because the TPM is using the OEM driver and not the Windows built-in Trusted Platform Module driver.

> Note:
> When you open Device Manager on some devices, the TPM is listed under **System Devices** and not under **Security Devices**.

## Resolution

To resolve this issue, open Device Manager on the device on which you're experiencing the issue, and then uninstall the Trusted Platform Module driver.

If you do a hardware scan, the TPM will be detected as a security device and will use the Microsoft driver. Additionally, the TPM will now be listed under **Security Devices** as Trusted Platform Module 1.2.

## More information

For more information, see:

- Trusted Platform Module Technology Overview)
- Initialize and Configure Ownership of the TPM)

_Source: Microsoft Learn, licensed CC BY 4.0._
