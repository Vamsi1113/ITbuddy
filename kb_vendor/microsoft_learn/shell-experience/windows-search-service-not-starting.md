<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/windows-search-service-not-starting -->
# Cannot start Windows Search service

The Windows Search service on local computer started and then stopped. Some services stop automatically if they aren't in use by other services or programs. This error occurs when you try to start the Windows Search service. Provides a resolution.

This article provides a resolution to solve the error that occurs when you try to start the Windows Search Service.

Applies to:   Windows 10 - all editions
_Original KB number:_   2484025

## Symptoms

Windows Search service doesn't start and when you try to start the service manually, you receive this error message:

> ========
Services
\========
"The Windows Search service on local computer started and then stopped. Some services stop automatically if they are not in use by other services or programs"
\===
OK
\===

## Cause

You may see this issue if there are missing subkeys or registry entries under the following registry location:

`HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows Search\CrawlScopeManager\Windows\SystemIndex`

Or if there are corrupted log files at the following location:

C:\windows\system32\config\TxR

> Note:
> The above regisrty key is unique to each machine, so should not be replaced manually.

## Resolution

To resolve this issue, delete all files with `.BLF` and `.REGTRANS-MS` extension in the following directory:

C:\windows\system32\config\TxR

> Note:
> The files in the folder location above are hidden and will thus not be visible unless you set the system to not Hide Protected Operating System Files under **Tools** > **Folder Options**.

Once these files are deleted, reboot the machine. Once rebooted, observe that the Windows Search service has already started and is in process of rebuilding the Index.

> Important:
You may observe High CPU while the Search Index is being rebuilt.

_Source: Microsoft Learn, licensed CC BY 4.0._
