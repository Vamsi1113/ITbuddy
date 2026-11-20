<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/disable-and-re-enable-hibernation -->
# How to disable and re-enable hibernation

Explains how to turn off the hibernation feature in Windows.

This article describes how to disable and then re-enable hibernation on a computer that is running Windows.

_Original KB number:_   920730

> Warning:
> You may lose data if you make hibernation unavailable and a power loss occurs while the hybrid sleep setting is turned on. When you make hibernation unavailable, hybrid sleep does not work.

## How to make hibernation unavailable

1. Press the Windows button on the keyboard to open Start menu or Start screen.
2. Search for **cmd**. In the search results list, right-click **Command Prompt**, and then select **Run as Administrator**.
3. When you are prompted by User Account Control, select **Continue**.
4. At the command prompt, type `powercfg.exe /hibernate off`, and then press Enter.
5. Type *exit*, and then press Enter to close the **Command Prompt** window.

## How to make hibernation available

1. Press the Windows button on the keyboard to open Start menu or Start screen.
2. Search for **cmd**. In the search results list, right-click **Command Prompt**, and then select **Run as Administrator**.
3. When you are prompted by User Account Control, select **Continue**.
4. At the command prompt, type `powercfg.exe /hibernate on`, and then press Enter.
5. Type *exit*, and then press Enter to close the Command Prompt window.

## More information

The Hiberfil.sys hidden system file is located in the root folder of the drive where the operating system is installed. The Windows Kernel Power Manager reserves this file when you install Windows. The size of this file is approximately equal to how much random access memory (RAM) is installed on the computer.

The computer uses the Hiberfil.sys file to store a copy of the system memory on the hard disk when the hybrid sleep setting is turned on. If this file is not present, the computer cannot hibernate.

## Reference

To add the Hibernate option to Start menu, see the Hibernate section of Shut down, sleep, or hibernate your PC.

## Data collection

If you need assistance from Microsoft support, we recommend you collect the information by following the steps mentioned in Gather information by using TSS for deployment-related issues.

_Source: Microsoft Learn, licensed CC BY 4.0._
