<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/error-0x113-intel-amd-graphics-adapters -->
# Computer crashes with error code 0x113

Resolves an issue in which the computer crashes with error code 0x113. This issue occurs if the computer has hybrid graphic cards installed.

This article provides a workaround for an issue where a computer crashes with error code 0x113.

Applies to:   Windows 8.1
_Original KB number:_   2990029

## Symptoms

Assume that you have a Windows 8.1-based computer that has a hybrid graphics configuration that uses both Intel and AMD graphics adapters. In this situation, the computer occasionally crashes when it tries to resume from standby, and you receive the following error message: Bug Check 0x113 (VIDEO_DXGKRNL_FATAL_ERROR)

## Cause

This issue occurs because the AMD driver does not support Runtime Power Management (RTPM), but the Intel driver does support RTPM.

## Workaround

To work around this issue, disable RTPM in the Intel driver.

## Status

Microsoft has confirmed that this is a problem in the Microsoft products that are listed in the "Applies to" section.

_Source: Microsoft Learn, licensed CC BY 4.0._
