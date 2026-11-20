<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/windows-security/mbam-client-fails-event-id-4-0x8004100e -->
# MBAM client fails with error 0x8004100E

Fixes the error 0x8004100E that occurs when Microsoft BitLocker Administration and Monitoring (MBAM) client fails.

This article helps fix the error 0x8004100E that occurs when Microsoft BitLocker Administration and Monitoring (MBAM) client fails.

Applies to:   Windows 7 Service Pack 1
_Original KB number:_   2756402

## Symptoms

When an MBAM agent running on Windows 7 computer tries to communicate to MBAM server, it may fail to send the encryption status data. Additionally, you may receive the following event error message logged in the Event Viewer:

> Log Name: Microsoft-Windows-MBAM/Admin
Source: Microsoft-Windows-MBAM
Event ID: 4
Task Category: None
Level: Error
Keywords:
User: SYSTEM
Computer: `<computername.domain.com>`
Description: An error occurred while sending encryption status data. Error code: 0x8004100e

> Note:
> Error code 0x8004100e translates to WBEM_E_INVALID_NAMESPACE.

## Cause

This problem occurs if the BitLocker WMI class (win32_encryptablevolume) is not registered or missing registration.

## Resolution

To resolve this problem, re-register the BitLocker WMI (win32_encryptablevolume) class.

Open an elevated command prompt and type the following command:

`mofcomp.exe c:\windows\system32\wbem\win32_encryptablevolume.mof`

If the file successfully compiles, you will receive the following message:

> Microsoft (R) MOF Compiler Version 6.1.7600.16385
Copyright (c) Microsoft Corp. 1997-2006. All rights reserved.
Parsing MOF file: win32_encryptablevolume.mof
MOF file has been successfully parsed
Storing data in the repository...
Done!

MBAM can now send encryption status data to MBAM Compliance Database on SQL Server.

## More information

To view MBAM event logs on a Windows 7 client machine browse to:

1. Click the Start button, type "event viewer" in search box, then click on Event Viewer that will be displayed above.
2. Click on Application and Services Logs
3. Select Microsoft
4. Expand Windows
5. Expand MBAM and then select Admin Logs.

> Note:
> BitLocker WMI Provider interface, for example Win32_EncryptableVolume WMI provider class is used to manage and configuring BitLocker Drive Encryption (BDE) on Windows Server 2008 R2, Windows Server 2008, and only specific versions of Windows 7, Windows Vista Enterprise, and Windows Vista Ultimate. MBAM client and manage-bde.exe command use this WMI class to administer and capture the current status of BDE on a volume. In case the namespace for this class is missing/corrupt, administrative tools including MBAM and manage-bde.exe will fail with errors. Additionally, you may get below error message if you run the manage-bde command:

Also, see following MSDN article for: Running the MOF Compiler on a File

_Source: Microsoft Learn, licensed CC BY 4.0._
