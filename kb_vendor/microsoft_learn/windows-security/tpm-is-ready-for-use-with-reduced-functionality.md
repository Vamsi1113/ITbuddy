<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/windows-security/tpm-is-ready-for-use-with-reduced-functionality -->
# Error when BIOS is in legacy mode with TPM 2.0

Describes an issue that triggers an error (TPM is ready for use, with reduced functionality) when the BIOS is in legacy mode with TPM 2.0.

This article helps fix an error that occurs when you have the operating system installed in Legacy MBR mode (PC/AT) with Trusted Platform Module (TPM) version 2.0.

_Original KB number:_   3123365

## Symptoms

On a Windows Server-based operating system, you have the operating system installed in Legacy MBR mode (PC/AT) with Trusted Platform Module (TPM) version 2.0. In this situation, you receive a message in the TPM user interface stating that "The TPM is ready for use, with reduced functionality."

## Resolution

On the operating systems that are listed in the Applies To section, TPM 2.0 is supported in UEFI mode only.

## More information

TPM 2.0 is designed to be fully functional in UEFI mode. Systems must be in UEFI mode with TPM enabled and secure boot configured and enabled in order to attain the security status that's described in the following TechNet article:

Secure the Windows 8.1 boot process

For more information about secure boot and TPM, see the following resources:

Windows hardware certification requirements for Client and Server systems

Trusted computing group

_Source: Microsoft Learn, licensed CC BY 4.0._
