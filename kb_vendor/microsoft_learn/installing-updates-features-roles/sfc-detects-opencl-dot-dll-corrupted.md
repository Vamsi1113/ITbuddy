<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/installing-updates-features-roles/sfc-detects-opencl-dot-dll-corrupted -->
# SFC detects Opencl.dll as corrupted

Fixes an issue that causes SFC to detect Opencl.dll as corrupted in Windows 10.

This article provides a solution to an issue that causes SFC to detect Opencl.dll as corrupted in Windows 10.

Applies to:   Windows 10, version 1809
_Original KB number:_   3178332

## Symptoms

After you run the `SFC /scannow` command in Windows 10, it detects a corrupted system file. The cbs.log file shows that %windir%\syswow64\opencl.dll is detected to be corrupted.

For more information about how to analyze the `SFC /scannow` result, see Analyze the log file entries that SFC.exe generates in Windows Vista.

## Resolution

To fix this issue, run the following command:

```console
Dism /online /cleanup-image /restorehealth
```

## Data collection

If you need assistance from Microsoft support, we recommend you collect the information by following the steps mentioned in Gather information by using TSS for deployment-related issues.

_Source: Microsoft Learn, licensed CC BY 4.0._
