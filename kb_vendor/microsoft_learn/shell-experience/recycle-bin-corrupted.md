<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/recycle-bin-corrupted -->
# The Recycle Bin is corrupted

Provides a solution to an issue where the Recycle Bin is corrupted.

This article provides a solution to an issue where the Recycle Bin is corrupted.

When you sign in to the system or try to delete a file, you receive this error message:

> The Recycle Bin on \<Drive\> is corrupted. Do you want to empty the Recycle Bin for this drive?

> Note:
> \<Drive\> might be a logical volume or a mounted volume.

This issue occurs because of a corrupted *$Recycle.bin* file.

To resolve the issue, run the following command from an elevated command prompt and then restart the system.

```console
RD <Drive>$Recycle.bin /s /q
```

_Source: Microsoft Learn, licensed CC BY 4.0._
