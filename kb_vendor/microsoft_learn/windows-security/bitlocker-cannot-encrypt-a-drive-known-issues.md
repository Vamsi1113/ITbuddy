<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/windows-security/bitlocker-cannot-encrypt-a-drive-known-issues -->
# BitLocker cannot encrypt a drive: known issues

Provides guidance for troubleshooting known issues that may prevent BitLocker Drive Encryption from encrypting a drive.

This article describes common issues that prevent BitLocker from encrypting a drive. This article also provides guidance to address these issues.

> Note:
> If it is determined that the BitLocker issue involves the trusted platform module (TPM), see BitLocker cannot encrypt a drive: known TPM issues.

## Error 0x80310059: BitLocker drive encryption is already performing an operation on this drive

When BitLocker Drive Encryption is turned on a computer that is running Windows 10 Professional or Windows 11, the following message may appear:

> ERROR: An error occurred (code 0x80310059): BitLocker Drive Encryption is already performing an operation on this drive. Please complete all operations before continuing. NOTE: If the -on switch has failed to add key protectors or start encryption, you may need to call manage-bde -off before attempting -on again.

### Cause of Error 0x80310059

This issue may be caused by settings that are controlled by group policy objects (GPOs).

### Resolution for Error 0x80310059

> Important:
> Follow the steps in this section carefully. Serious problems might occur if the registry is modified incorrectly. Before modifying the registry, back up the registry for restoration in case problems occur.

To resolve this issue, follow these steps:

1. Start Registry Editor, and navigate to the following subkey:

   **`HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\FVE`**

2. Delete the following entries:

   - **`OSPlatformValidation_BIOS`**
   - **`OSPlatformValidation_UEFI`**
   - **`PlatformValidation`**

3. Exit registry editor, and turn on BitLocker drive encryption again.

_Source: Microsoft Learn, licensed CC BY 4.0._
