<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/devices-connected-via-thunderbolt-dock-not-work -->
# Devices connected through a Thunderbolt Dock stop working

Describes an issue in which devices that are connected through a Thunderbolt Dock stop working after the computer resumes from a power state. Provides a workaround.

This article provides a workaround for an issue in which devices that are connected through a Thunderbolt Dock stop working after the computer resumes from a power state.

Applies to:   Windows Client
_Original KB number:_   4532436

## Symptoms

Consider the following scenario:

- On a computer that's running any version of Windows 10 or Windows 11, you enable Fast Startup.
- On a Thunderbolt Dock, several devices are attached. For example, a keyboard, mouse, and USB encryption key are attached.
- You repeatedly do the following steps:
  - You connect the Thunderbolt Dock to the computer so that devices on the Thunderbolt Dock are enumerated.
  - The system enters or resumes from a Modern Standby, Hibernate (S4), or Soft Off (S5) power state. During this activity, you plug or unplug the dock.

In this scenario, the devices stop working. Device Manager might show yellow exclamation points and **Code 10**, **Code 24**, or **Code 43** for those devices.

## Workaround

When the issue occurs, the functionality of the devices can be restored by reattaching the Thunderbolt Dock. If this doesn't work, restart the computer.

## References

For more information about Windows power states, see System Power States.

## Data collection

If you need assistance from Microsoft support, we recommend you collect the information by following the steps mentioned in Gather information by using TSS for deployment-related issues.

_Source: Microsoft Learn, licensed CC BY 4.0._
