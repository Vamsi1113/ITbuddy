<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/windows-10-upgrade-issues-troubleshooting -->
# Windows 10 upgrade issues troubleshooting

Understanding the Windows 10 upgrade process can help you troubleshoot errors when something goes wrong. Find out more with this guide.

<p class="alert is-flex is-primary"><span class="has-padding-left-medium has-padding-top-extra-small"><a class="button is-primary" href="https://vsa.services.microsoft.com/v1.0/?partnerId=7d74cf73-5217-4008-833f-87a1a278f2cb&flowId=DMC&initialQuery=31806293" target='_blank'>Try our Virtual Agent</a></span><span class="has-padding-small"> - It can help you quickly identify and fix common Windows boot issues</span>

> Note:
> This is a 300 level topic (moderately advanced).
>
> For IT professionals, check more information in Resolve Windows upgrade errors: Technical information for IT Pros.

If a Windows 10 upgrade isn't successful, it can be helpful to understand when an error occurred in the upgrade process.

> Important:
> Use the SetupDiag tool before you begin manually troubleshooting an upgrade error. SetupDiag automates log file analysis, detecting and reporting details on many different types of known upgrade issues.

Applies to:   Windows 10

## Actions performed during upgrade processes

Briefly, the upgrade process consists of four phases that are controlled by Windows Setup: Downlevel, SafeOS, First boot, and Second boot. The computer will reboot once between each phase. Note: Progress is tracked in the registry during the upgrade process using the following key: `HKLM\System\Setup\mosetup\volatile\SetupProgress`. This key is volatile and only present during the upgrade process; it contains a binary value in the range 0-100.

These phases are explained in greater detail below. First, let's summarize the actions performed during each phase because this affects the type of errors that can be encountered.

1. Downlevel phase: Because this phase runs on the source OS, upgrade errors aren't typically seen. If you do encounter an error, ensure the source OS is stable. Also ensure the Windows setup source and the destination drive are accessible.

2. SafeOS phase: Errors most commonly occur during this phase due to hardware issues, firmware issues, or non-microsoft disk encryption software.

    Since the computer is booted into Windows PE during the SafeOS phase, a useful troubleshooting technique is to boot into Windows PE using installation media. You can use the media creation tool to create bootable media, or you can use tools such as the Windows ADK, and then boot your device from this media to test for hardware and firmware compatibility issues.

    > Tip:
    > If you attempt to use the media creation tool with a USB drive and this fails with error 0x80004005 - 0xa001a, this is because the USB drive is using GPT partition style. The tool requires that you use MBR partition style. You can use the `DISKPART` command to convert the USB drive from GPT to MBR. For more information, see Change a GUID Partition Table Disk into a Master Boot Record Disk).

    Don't proceed with the Windows 10 installation after booting from this media. This method can only be used to perform a clean install, which won't migrate any of your apps and settings, and you'll be required reenter your Windows 10 license information.

    If the computer doesn't successfully boot into Windows PE using the media that you created, this is likely due to a hardware or firmware issue. Check with your hardware manufacturer and apply any recommended BIOS and firmware updates. If you're still unable to boot to installation media after applying updates, disconnect or replace legacy hardware.

    If the computer successfully boots into Windows PE, but you are not able to browse the system drive on the computer, it's possible that non-Microsoft disk encryption software is blocking your ability to perform a Windows 10 upgrade. Update or temporarily remove the disk encryption.

3. First boot phase: Boot failures in this phase are relatively rare, and almost exclusively caused by device drivers.  Disconnect all peripheral devices except for the mouse, keyboard, and display. Obtain and install updated device drivers, then retry the upgrade.

4. Second boot phase: In this phase, the system is running under the target OS with new drivers. Boot failures are most commonly due to anti-virus software or filter drivers. Disconnect all peripheral devices except for the mouse, keyboard, and display. Obtain and install updated device drivers, temporarily uninstall anti-virus software, then retry the upgrade.

If the general troubleshooting techniques described above or the quick fixes detailed below don't resolve your issue, you can attempt to analyze log files and interpret upgrade error codes. You can also Submit Windows 10 upgrade errors using Feedback Hub so that Microsoft can diagnose your issue.

## The Windows 10 upgrade process

The Windows Setup application is used to upgrade a computer to Windows 10, or to perform a clean installation. Windows Setup starts and restarts the computer, gathers information, copies files, and creates or adjusts configuration settings.

When performing an operating system upgrade, Windows Setup uses phases described below. A reboot occurs between each of the phases. After the first reboot, the user interface will remain the same until the upgrade is completed. Percent progress is displayed and will advance as you move through each phase, reaching 100% at the end of the second boot phase.

1. Downlevel phase: The downlevel phase is run within the previous operating system. Windows files are copied and installation components are gathered.

2. Safe OS phase: A recovery partition is configured, Windows files are expanded, and updates are installed. An OS rollback is prepared if needed. Example error codes: 0x2000C, 0x20017.

3. First boot phase: Initial settings are applied. Example error codes: 0x30018, 0x3000D.

4. Second boot phase: Final settings are applied. This is also called the OOBE boot phase. Example error codes: 0x4000D, 0x40017.

    At the end of the second boot phase, the **Welcome to Windows 10** screen is displayed, preferences are configured, and the Windows 10 sign-in prompt is displayed.

5. Uninstall phase: This phase occurs if upgrade is unsuccessful (image not shown). Example error codes: 0x50000, 0x50015.

    Figure 1: Phases of a successful Windows 10 upgrade (uninstall isn't shown):

    DU = Driver/device updates.
    OOBE = Out of box experience.
    WIM = Windows image (Microsoft)

## Data collection

If you need assistance from Microsoft support, we recommend you collect the information by following the steps mentioned in Gather information by using TSS for deployment-related issues.

## More information

- Windows 10 FAQ for IT professionals
- Windows 10 Enterprise system requirements
- Windows 10 Specifications
- Windows 10 IT pro forums
- Fix Windows Update errors by using the DISM or System Update Readiness tool

_Source: Microsoft Learn, licensed CC BY 4.0._
