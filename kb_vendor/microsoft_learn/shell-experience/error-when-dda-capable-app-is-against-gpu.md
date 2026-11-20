<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/error-when-dda-capable-app-is-against-gpu -->
# Error when DDA-capable app is run against GPU

Describes an issue in which an error is generated when a Desktop Duplication API-capable application is run against a discrete GPU on a computer that is running Windows 8.1.

This article provides a solution to an error that occurs when a Desktop Duplication API-capable application is run against a discrete GPU.

Applies to:   Windows 8.1
_Original KB number:_   3019314

## Symptoms

Consider the following scenario:

- You have a computer that is running Windows 8.1.
- You have a Desktop Duplication API (DDA)-capable application, and it calls the DDA to duplicate the desktop image.
- The display adapter on the computer is running under the Microsoft Hybrid system.

In this scenario, when the application tries to duplicate the desktop image against the discrete GPU on a Microsoft Hybrid system, the application may not run correctly, or it may generate one of the following errors:

> Failed to create windows swapchain with 0x80070005
>
> CDesktopCaptureDWM: IDXGIOutput1::DuplicateOutput failed: 0x887a0004

## Cause

This issue occurs because the DDA does not support being run against the discrete GPU on a Microsoft Hybrid system. By design, the call fails together with error code DXGI_ERROR_UNSUPPORTED in such a scenario.

## Resolution

To work around this issue, run the application on the integrated GPU instead of on the discrete GPU on a Microsoft Hybrid system.

## More information

When this issue occurs, the IDXGIOutput1::DuplicateOutput method fails and returns an error code DXGI_ERROR_UNSUPPORTED.

For example, this DXGI desktop duplication sample is affected by this issue.

_Source: Microsoft Learn, licensed CC BY 4.0._
