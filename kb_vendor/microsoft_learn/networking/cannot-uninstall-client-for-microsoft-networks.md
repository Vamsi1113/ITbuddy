<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/networking/cannot-uninstall-client-for-microsoft-networks -->
# Error 0x80071779 when removing network components

Address an issue in which you receive error 0x80071779 when removing Client for Microsoft Networks.

This article helps fix an error 0x80071779 that occurs when you uninstall the **Client for Microsoft Networks** or other network components.

Applies to:   Window 10 – all editions
_Original KB number:_   4340181

## Symptoms

Starting with Windows 10, version 1803 and newer based device or computer, you can't uninstall the **Client for Microsoft Networks** or other network components. You receive the following error message:

> Could not uninstall the Client for Microsoft Networks feature.
>
> The error is 0x80071779.

## Cause

This behavior is by design.

## Resolution

Microsoft doesn't support using this GUI or **netcfg** to uninstall protocols or built-in drivers. Instead, you can unbind the driver from Network Adapters either by using this GUI or the PowerShell cmdlet `Disable-NetAdapterBinding`. This is effectively the same as uninstalling the driver.

## More information

If there are specific drivers that you want to remove but that are currently not part of an optional feature, file a feature request in the Feedback Hub.

_Source: Microsoft Learn, licensed CC BY 4.0._
