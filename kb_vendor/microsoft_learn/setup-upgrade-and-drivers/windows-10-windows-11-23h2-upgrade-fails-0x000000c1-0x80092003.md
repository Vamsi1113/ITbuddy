<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/windows-10-windows-11-23h2-upgrade-fails-0x000000c1-0x80092003 -->
# Error 0x000000c1 or 0x80092003 CRYPT_E_FILE_ERROR Stops In-place Upgrade from Windows 10 to Windows 11

Discusses an issue in which an in-place upgrade to Windows 11, version 23H2 fails and rolls back on a Windows 10 device that has the UEFI CA 2023 signed bootloader installed.

This article discusses an issue in which an in-place upgrade to Windows 11, version 23H2 fails and rolls back on a Windows 10 device that has the UEFI CA 2023 signed bootloader installed.

## Symptoms

Consider the following scenario:

- You have a Windows 10 device that uses the UEFI CA 2023 signed bootloader that was provided in an update on or after July 9, 2024.
- By using Windows Update (or media that you downloaded from Windows Update), you perform an in-place upgrade to upgrade the device from Windows 10 to Windows 11, version 23H2.

After the upgrade reaches the OOBE restart phase, the upgrade fails, rolls back to Windows 10, and generates one of the following error codes:

- 0x80092003 (CRYPT_E_FILE_ERROR)
- 0x000000c1

If you upgrade the device by using the latest Windows 11 23H2 ISO image as source media, the upgrade succeeds. Similarly, if you upgrade the device to Windows 11 24H2 by using the Windows 11 Installation Assistant, the upgrade succeeds.

## Cause

Windows updates that were released on or after July 9, 2024, contain protections for a publicly disclosed Secure Boot security feature bypass. These updates install the UEFI CA 2023-signed bootloader, %systemdrive%\bootmgfw_2023.efi. For more information about this vulnerability and its fix, see the following articles:

- Secure Boot Security Feature Bypass Vulnerability, CVE-2023-24932
- How to manage the Windows Boot Manager revocations for Secure Boot changes associated with CVE-2023-24932

The issue occurs because this file wasn't part of the original Windows 11 23H2 upgrade media or Safe OS Dynamic Update (SafeOS DU) media. The upgrade process uses the Windows Recovery Environment (WinRE) while it validates or updates startup files. Because the bootloader on the device is newer than the bootloader in the Windows 11 upgrade media, the upgrade process can't update startup information on the WinRE image under %systemroot%\~BT\Sources\Rollback\EFI\Microsoft\Recovery. Therefore, the upgrade fails and rolls back.

This issue doesn't affect the latest version of the Windows 11, version 23H2 media; the Windows 11, version 24H2 media; or media for later versions.

## Resolution

The fix for this issue was released on February 11, 2025. To implement this fix during your in-place upgrade, use one of the following methods:

- Upgrade directly to Windows 11, version 24H2 or a later version. Use either Windows Update or media that was created after February 11, 2025.
- Upgrade to the latest release of Windows 11, version 23H2. Use either Windows Update or media that was created after February 11, 2025.
- If you have to upgrade to an earlier version of Windows 11, use one of the following methods:

  - During the upgrade process, allow the device to connect to Windows Update to automatically download and install KB5052424: Safe OS Dynamic Update for Windows 11, version 22H2 and 23H2: February 11, 2025 - Microsoft Support.
  - Modify the installation media image to slipstream the KB5052424 update.

_Source: Microsoft Learn, licensed CC BY 4.0._
