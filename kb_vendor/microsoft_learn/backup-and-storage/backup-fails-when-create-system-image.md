<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/backup-and-storage/backup-fails-when-create-system-image -->
# Backup fails when you create system image

Resolves an issue where backup fails when you create a system image.

This article provides a solution to an issue where backup fails when you try to create a system image.

Applies to:   Windows 7 Service Pack 1
_Original KB number:_   2696906

## Symptoms

Consider the following scenario:

- You are running Windows 7 Service Pack 1.
- In the Backup and Restore Control Panel applet, you click on the link to "Create a system image".
- The source volume that you are imaging is 2 terabytes in size or larger.

In this scenario, after the backup process has started, you may see an error similar to the following:

> The backup failed.
>
> Volumes larger than 2088958 megabyes cannot be protected. (0x807800B4)

The only option is to close the dialog box and exit out of the **Create a system image** wizard.

## Cause

When creating a system image in Windows 7 Service Pack 1 by using the **Create a system image** wizard, a virtual hard disk (.vhd) is created and the system image is written to it. The current virtual hard disk specification limits the size of a virtual hard disk to be 2040 GB, which can fit a volume size of 2040 GB - 2 MB (that is, 2088958 MB). Due to this limitation, the source volume size must be 2,088,958 MB or less for the system image to be created.

> Note:
> All of the above values are slightly under 2 TB in size (2 TB = 2048 GB = 2097152 MB).

## Resolution

To work around this limit, shrink your volume size to 2,088,958 MB or less prior to creating the system image. More information on shrinking a basic volume can be found in the following article:

Shrink a Basic Volume)

_Source: Microsoft Learn, licensed CC BY 4.0._
