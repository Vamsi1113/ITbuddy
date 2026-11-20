<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/task-manager-shows-incorrect-cpu-speed -->
# Task Manager shows incorrect CPU speed when Hyper-V is enabled

Discusses that Windows Task Manager shows an incorrect CPU speed when Hyper-V is enabled in Windows Server 2012 R2. Provides a workaround.

This article provides a workaround for an issue where Windows Task Manager shows incorrect CPU speed when Hyper-V is enabled.

Applies to:   Windows 10 - all editions, Window Server 2012 R2
_Original KB number:_   3003081

## Symptoms

If the Hyper-V role is enabled in any of the products that are listed at the beginning of this article, the **CPU Frequency** speed value that is displayed in Task Manager is not the current speed, as expected. When the Hyper-V Role is not enabled, Task Manager correctly displays the current speed for this value.

## Workaround

To work around this issue, use the built-in Performance Monitor tool (perfmon.exe), and add the "\\Hyper-V Hypervisor Logical Processor\\Frequency" performance counter.

## Status

This is a known issue in the product versions that are listed at the beginning of this article.

_Source: Microsoft Learn, licensed CC BY 4.0._
