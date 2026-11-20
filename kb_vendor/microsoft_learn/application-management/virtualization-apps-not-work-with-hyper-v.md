<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/application-management/virtualization-apps-not-work-with-hyper-v -->
# Virtualization applications can't run alongside Hyper-V and its dependent features

Learn why virtualization applications don't work alongside Hyper-V, Device Guard, and Credential Guard, and how to resolve the issue.

_Original KB number:_   3204980

## Summary

Third-party virtualization applications, such as VMware and VirtualBox, can't run alongside Hyper-V, Memory Integrity, or Credential Guard. This article explains why this issue occurs, and how to disable Hyper-V and its dependent security features so that your third-party virtualization software can work correctly.

## Symptoms

When Hyper-V is running, the third-party virtualization applications might not start virtual machines (VMs), or they might fall back to a slower, emulated mode.

## Cause

This behavior is by design.

Many virtualization applications depend on hardware virtualization extensions. Most modern processors, such as Intel VT-x and AMD-V, provide these extensions. However, only one software component at a time can use this hardware. Virtualization applications can't share the hardware.

## Workaround

To use third-party virtualization applications, disable  Hyper-V.

> Important:
> Some Windows security technologies depend on Hyper-V, including the following Windows features:
>
> - Memory Integrity (originally released as part of Device Guard)
> - Credential Guard
>
> When you disable Hyper-V, also disable these dependent features.

### How to determine whether the Hyper-V hypervisor is running

To determine whether the Hyper-V hypervisor is running, follow these steps:

1. In the search box, enter *msinfo32.exe*.
1. Select **System Information**.
1. On the **Details** pane, locate the following entry:

   > A hypervisor has been detected. Features required for Hyper-V will not be displayed.

### How to disable Hyper-V

#### Control Panel

To disable Hyper-V in Control Panel, follow these steps:

1. In Control Panel, select the **Programs and Features** item.
1. Select **Turn Windows features on or off**.
1. Expand **Hyper-V**, expand **Hyper-V Platform**, and then clear the **Hyper-V Hypervisor** checkbox.

#### PowerShell

To disable Hyper-V by using Windows PowerShell, follow these steps:

1. Open an administrative PowerShell window.
1. Run the following command:

    ```powershell
    Disable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-Hypervisor
    ```

#### DISM

To disable Hyper-V by using DISM, follow these steps:

1. Open an administrative Command Prompt window.
1. Run the following command:

   ```console
   DISM /Online /Disable-Feature /FeatureName:Microsoft-Hyper-V-Hypervisor
   ```

---

### How to disable Memory Integrity and Credential Guard

You can disable Memory Integrity and Credential Guard by using Microsoft Intune, Group Policy, or registry entries. For more information, see the following articles:

- Configure Credential Guard
- Enable virtualization-based protection of code integrity

## More information

_Source: Microsoft Learn, licensed CC BY 4.0._
