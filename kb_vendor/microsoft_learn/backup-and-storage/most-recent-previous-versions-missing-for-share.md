<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/backup-and-storage/most-recent-previous-versions-missing-for-share -->
# Most recent previous versions are missing for a share that has Previous Versions enabled in Windows

Works around an issue in which most recent previous versions aren't displayed for a share in Windows that has the Previous Versions feature enabled.

This article provides a workaround for an issue in which most recent previous versions aren't displayed for a share in Windows that has the **Previous Versions** feature enabled.

_Original KB number:_   4032986

## Symptoms

You've modified the **MaxShadowCopies** registry value to a larger value (the default value is 64). The **MaxShadowCopies** registry value specifies the maximum number of snapshots which the Volume Shadow Copy Service (VSS) can retain. When you connect to a share that has the **Previous Versions** feature enabled, you can see only older previous versions. The most recent previous versions are missing for the share.

## Cause

This issue occurs because the VSS and the Server Message Block (SMB) server components have separate limit numbers. The VSS limit number can be modified by the registry, but the SMB server has a fixed limit number that varies in Windows versions. Windows 8, Windows Server 2012, and later Windows versions are limited to view 500 previous versions in the SMB server. If you set the **MaxShadowCopies** registry value to 512, only the oldest 500 previous versions are displayed on the client side. Therefore, you can't see the 12 most recent previous versions.

## Workaround

To work around this issue, limit the number of previous versions that are kept on the server to 500 per volume.

## More Information

> Important:
> Follow the steps in this section carefully. Serious problems might occur if you modify the registry incorrectly. Before you modify it, back up the registry for restoration in case problems occur.

By default, Windows keeps only 64 snapshots per volume for previous versions. You can adjust this limit by creating or changing the following registry key:
`HKEY_LOCAL_MACHINE\System\CurrentControlSet\Services\VSS\Settings\MaxShadowCopies`

See Registry Keys and Values for Backup and Restore for more information.

Setting this key to a value higher than the SMB server can handle prevents users from seeing the most recent previous versions. The SMB server's limit for each operating system is as follows:

- Windows 8, Windows Server 2012, and later versions have a limit of 500.
- Windows Vista, Windows 7, Windows Server 2008, and Windows Server 2008 R2 have a limit of 500 for the SMB version 1 (SMBv1) protocol and 64 for the SMB version 2 (SMBv2) protocol.
- Windows XP and Windows Server 2003 have a limit of 64.

> [!Note]
> The SMB server's limit isn't adjustable. You can only modify the **MaxShadowCopies** registry value to adjust the number of previous versions that are kept.

_Source: Microsoft Learn, licensed CC BY 4.0._
