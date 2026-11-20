<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/installing-updates-features-roles/common-windows-update-errors -->
# Common Windows Update errors

Discusses some common Windows Update issues that you might experience, and provides steps to resolve them.

<p class="alert is-flex is-primary"><span class="has-padding-left-medium has-padding-top-extra-small"><a class="button is-primary" href="https://vsa.services.microsoft.com/v1.0/?partnerId=7d74cf73-5217-4008-833f-87a1a278f2cb&flowId=DMC&initialQuery=31806295" target='_blank'>Try our Virtual Agent</a></span><span class="has-padding-small"> - It can help you quickly identify and fix common Windows Update issues.</span>

The following tables provide information about common Windows Update-related errors that you might encounter, and include steps to help you mitigate the errors.

Applies to:   Windows 10, Windows 11

## 0x8024402F

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_PT_ECP_SUCCEEDED_WITH_ERRORS | External .cab file processing completed with some errors | This error might be caused by the Lightspeed Rocket for web filtering software. Add the IP addresses of the devices that you want to receive updates to the exceptions list of Lightspeed Rocket. |

## 0x80242006

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_UH_INVALIDMETADATA | A handler operation couldn't be completed because the update contains invalid metadata. | Rename the software redistribution folder, and try to download the updates again: Rename the following folders to \*.BAK: -*%systemroot%\\system32\\catroot2* Type the following commands at a command prompt. Press ENTER after you type each command.`Ren %systemroot%\SoftwareDistribution\DataStore DataStore.bak``Ren %systemroot%\SoftwareDistribution\Download Download.bak``Ren %systemroot%\system32\catroot2 catroot2.bak` |

## 0x80070BC9

| Message | Description | Mitigation |
|---------|-------------|------------|
| ERROR_FAIL_REBOOT_REQUIRED | The requested operation failed. Restart the system to roll back changes made. | Make sure that you don't have any policies that control the start behavior of the Windows Installer service. This service should be managed by the operating system. The default **Startup type** of the Windows Installer service is **Manual**.|

## 0x80200053

| Message | Description | Mitigation |
|---------|-------------|------------|
| BG_E_VALIDATION_FAILED | NA | Make sure that there are no firewalls that might filter downloads. Such filtering could cause incorrect responses to be received by the Windows Update client.|

## 0x80072EFD or 0x80072EFE or 0x80D02002

| Message | Description | Mitigation |
|---------|-------------|------------|
| TIME_OUT_ERRORS | The operation timed out | Make sure that no firewall rules or proxies block Microsoft download URLs. Take a network monitor trace to understand the situation better. \<Refer to Firewall Troubleshooting scenario> |

## 0X8007000D

| Message | Description | Mitigation |
|---------|-------------|------------|
| ERROR_INVALID_DATA | Indicates data that isn't valid was downloaded or corruption occurred.| Try to redownload the update, and then start the installation. |

## 0x8024A10A

| Message | Description | Mitigation |
|---------|-------------|------------|
| USO_E_SERVICE_SHUTTING_DOWN | Indicates that the Windows Update Service is shutting down. | This error can occur after a long time of inactivity. The system doesn't respond, causing the service to be idle and, eventually, shut down. Make sure that the system remains active, and the connections remain established to complete the installation. |

## 0x80240020

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_NO_INTERACTIVE_USER | The operation didn't finish because no interactive user is signed in. | Sign in to the device to start the installation, and allow the device to restart. |

## 0x80242014

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_UH_POSTREBOOTSTILLPENDING | The post-restart operation for the update is still in progress. | Some Windows updates require the device to be restarted. Restart the device to complete update the installation. |

## 0x80246017

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_DM_UNAUTHORIZED_LOCAL_USER | The download failed because the local user was denied authorization to download the content. | Ensure that the user attempting to download and install updates has been provided with sufficient privileges to install updates (Local Administrator). |

## 0x8024000B

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_CALL_CANCELLED | Operation was canceled. | The operation was canceled by the user or service. You might also receive this error message if we can't filter the results. |

## 0x8024000E

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_XML_INVALID | Windows Update Agent found information in the update's XML data that isn't valid. | Certain drivers contain more metadata information in Update.xml. Orchestrator might interpret that condition as data that isn't valid. Make sure that you have the latest Windows Update Agent installed on the device. |

## 0x8024D009

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_SETUP_SKIP_UPDATE | An update to the Windows Update Agent was skipped due to a directive in the Wuident.cab file. | You might encounter this error if WSUS isn't sending the self-update to the clients.For more information to resolve the issue, see KB920659. |

## 0x80244007

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_PT_SOAPCLIENT_SOAPFAULT | SOAP client failed because there was a SOAP fault for reasons of `WU_E_PT_SOAP_*` error codes. | This issue occurs because Windows can't renew the cookies for Windows Update.  For more information to resolve the issue, see 0x80244007 error when Windows tries to scan for updates on a WSUS server. |

## 0x80070422

| Message | Description | Mitigation |
|---------|-------------|------------|
| ERROR_SERVICE_DISABLED| This issue occurs when the Windows Update service stops working or isn't running. | Check whether the Windows Update service is running. |

## 0x800f0821

| Message | Description | Mitigation |
|---------|-------------|------------|
| CBS_E_ABORT; client abort, IDABORT returned by `ICbsUIHandler` method except Error() | CBS   transaction timeout exceeded. | A servicing operation is taking a long time to finish. The servicing stack watchdog timer expires. Extending the timeout mitigates the issue. Increase the resources on the device. If it's a virtual machine, increase virtual CPU and memory to speed up operations. Make sure that the device has installed the update in KB4493473 or later. |

## 0x800f0825

| Message | Description | Mitigation |
|---------|-------------|------------|
| CBS_E_CANNOT_UNINSTALL; Package can't be uninstalled. | Typically this error occurs because of component store corruption that was caused by a component in a partially installed state. | Repair the component store by using the `Dism RestoreHealth` command, or manually repair by using a payload from the partially installed component. In an elevated Command Prompt window, run these commands:`Dism.exe /Online /Cleanup-Image /Restorehealth``Sfc.exe /Scannow` Restart the device. |

## 0x800F0920

| Message | Description | Mitigation |
|---------|-------------|------------|
| CBS_E_HANG_DETECTED; A failure to respond was detected while processing the operation. | Subsequent error logged after getting 0x800f0821 | A servicing operation is taking a long time to finish. The servicing stack watchdog timer expires and assumes that the system stopped responding. Extending the timeout value mitigates the issue. Increase the resources on the device. If it's a virtual machine, increase virtual CPU and memory to speed up operations. Make sure that the device has update KB4493473 or later installed.|

## 0x800f081f

| Message | Description | Mitigation |
|---------|-------------|------------|
| CBS_E_SOURCE_MISSING; source for package or file not found, ResolveSource() unsuccessful | Component Store corruption | Repair the component store by running the `Dism RestoreHealth` command, or manually repair by using the payload from the partially installed component. In an elevated Command Prompt window, run these commands:`Dism.exe /Online /Cleanup-Image /Restorehealth``Sfc.exe /Scannow` Restart the device. |

## 0x800f0831

| Message | Description | Mitigation |
|---------|-------------|------------|
| CBS_E_STORE_CORRUPTION; CBS store is corrupted. | Corruption in the Windows Component Store. | Repair the component store by runnning `Dism RestoreHealth` or manually repair by using the payload from the partially installed component. In an elevated Command Prompt window, run these commands:`Dism.exe /Online /Cleanup-Image /Restorehealth``Sfc.exe /Scannow` Restart the device.  |

## 0x80070005

| Message | Description | Mitigation |
|---------|-------------|------------|
| E_ACCESSDENIED; General access denied error | File system or registry key permissions have been changed and the servicing stack doesn't have the required level of access. | This error generally means that access was denied. Go to *%Windir%\\logs\\CBS*, open the last *CBS.log*, search for `, error`, and match with the timestamp. After you find the error, scroll up, and try to determine what caused the access denial. It could be access denied to a file, registry key. Determine which object needs the right permissions, and change the permissions as appropriate. For more information, see Troubleshoot Windows Update error 0x80070005. |

## 0x80070570

| Message | Description | Mitigation |
|---------|-------------|------------|
| ERROR_FILE_CORRUPT; The file or directory is corrupted and unreadable. | Component Store corruption | Repair the component store by running `Dism RestoreHealth`, or manually repair by using the payload from the partially installed component. In an elevated Command Prompt window, run these commands:`Dism.exe /Online /Cleanup-Image /Restorehealth``Sfc.exe /Scannow` Restart the device. For more information, see Troubleshoot Windows Update error 0x80070570. |

## 0x80070003

| Message | Description | Mitigation |
|---------|-------------|------------|
| ERROR_PATH_NOT_FOUND; The system can't find the path specified. | The servicing stack can't access a specific path. | Indicates an invalid path to an executable. Go to *%Windir%\\logs\\CBS*, open the last *CBS.log*, and search for `, error`. Then, match the results to the timestamp. |

## 0x80070020

| Message | Description | Mitigation |
|---------|-------------|------------|
| ERROR_SHARING_VIOLATION | Numerous causes. CBS log analysis required. | This error is caused by non-Microsoft filter drivers, such as antivirus.  1. Perform a clean restart, and retry the installation   2. Download the sysinternal tool Process Monitor.  3. Run *Procmon.exe*. The tool starts data capture automatically.  4. Install the update package again.  5. Keep the Process Monitor main window in focus, and press CTRL+E or select the magnifying glass to stop data capture.  6. Select **File** > **Save** > **All Events** > **PML**, and choose a path to save the `.PML` file.  7. Go to *%windir%\\logs\\cbs*, open the last *Cbs.log* file, and search for the error entry. After you locate the error line, you should see which file is accessed during the installation and is causing the sharing violation error.  8. In Process Monitor, filter for path, and insert the file name (it should resemble "path" "contains" "filename from CBS").  9. Try to stop or uninstall the process that's causing the error. |

## 0x80073701

| Message | Description | Mitigation |
|---------|-------------|------------|
| ERROR_SXS_ASSEMBLY_MISSING; The referenced assembly couldn't be found. | Typically, a component store corruption caused when a component is in a partially installed state. | Repair the component store by running `Dism RestoreHealth command`, or manually repair it by using the payload from the partially installed component. In an elevated Command Prompt window, run these commands:`Dism.exe /Online /Cleanup-Image /Restorehealth``Sfc.exe /Scannow` Restart the device. |

## 0x8007371b

| Message | Description | Mitigation |
|---------|-------------|------------|
| ERROR_SXS_TRANSACTION_CLOSURE_INCOMPLETE; One or more required members of the transaction aren't present. | Component Store corruption. | Repair the component store by running the `Dism RestoreHealth` command, or manually repair it by using the payload from the partially installed component. In an elevated Command Prompt window, run these commands:`Dism.exe /Online /Cleanup-Image /Restorehealth``Sfc.exe /Scannow` Restart the device. |

## 0x80072EFE

| Message | Description | Mitigation |
|---------|-------------|------------|
| WININET_E_CONNECTION_ABORTED; The connection with the server was closed abnormally | BITS is unable to transfer the file successfully. | Encountered if BITS is broken or if the file that's being transferred can't be written to the destination folder on the client. This error is caused by connection errors while checking or downloading updates. At a command prompt, run: `BITSADMIN /LIST /ALLUSERS /VERBOSE`  Search for the 0x80072EFE error code. You should see a reference to an HTTP code and a specific file. Using a browser, try to download the file manually. Make sure that you use your organization's proxy settings. If the download fails, work with your proxy manager to achieve successful communication. Also, check with your network team for this specific URL access. |

## 0x80072F8F

| Message | Description | Mitigation |
|---------|-------------|------------|
| WININET_E_DECODING_FAILED; Content decoding has failed | TLS 1.2 isn't configured correctly on the client. | This error generally means that the Windows Update Agent can't decode the received content. Install and configure TLS 1.2 by installing the update that's provided in KB3140245.

## 0x80072EE2

| Message | Description | Mitigation |
|---------|-------------|------------|
| WININET_E_TIMEOUT; The operation timed out | Unable to scan for updates due to a connectivity issue to Windows Update, Configuration Manager, or WSUS. | This error generally means that the Windows Update Agent was unable to connect to the update servers or your own source, such as WSUS, Configuration Manager, or Microsoft Intune.  Check with your network team to ensure that the device can reach the update sources. For more info, see Troubleshoot software update scan failures in Configuration Manager.  If you're using the public Microsoft update servers, check that your device can access the following Windows Update endpoints:  `http://windowsupdate.microsoft.com`  `https://*.windowsupdate.microsoft.com`  `https://update.microsoft.com`  `https://*.update.microsoft.com`  `https://windowsupdate.com`  `https://*.windowsupdate.com`  `https://download.windowsupdate.com`  `https://*.download.windowsupdate.com`  `https://download.microsoft.com`  `https://*.download.windowsupdate.com`  `https://wustat.windows.com`  `https://*.wustat.windows.com`  `https://ntservicepack.microsoft.com` |

## 0x80240022

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_ALL_UPDATES_FAILED; Operation failed for all the updates. | Multiple root causes for this error.| The most common issue is that antivirus software is blocking access to certain folders (like SoftwareDistribution). CBS.log analysis has to determine the file or folder that's being protected. |

## 0x8024401B

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_PT_HTTP_STATUS_PROXY_AUTH_REQ; Same as HTTP status 407 - proxy authentication is required. | Unable to authenticate through a proxy server. | Either the Winhttp proxy or WinInet proxy settings aren't configured correctly. This error generally means that the Windows Update Agent can't connect to the update servers or your own update source, such as WSUS, Configuration Manager, or Microsoft Intune, due to a proxy error.  Verify the proxy settings on the client. The Windows Update Agent uses WinHTTP to scan for available updates. When there's a proxy server between the client and the update source, the proxy settings must be configured correctly on the clients to enable them to communicate by using the source's FQDN.  Check with your network and proxy teams to verify that the device can access the update source without the proxy requiring user authentication. |

## 0x80244022

| Message | Description | Mitigation |
|---------|-------------|------------|
| WU_E_PT_HTTP_STATUS_SERVICE_UNAVAILABLE; Same as HTTP status 503 - the service is temporarily overloaded. | Unable to connect to the configured update source. | Network troubleshooting is needed to resolve the connectivity issue. Check with your network and proxy teams to verify that the device can access the update source without the proxy requiring user authentication. |

## 0x80070490

| Message | Description | Mitigation |
|---------|-------------|------------|
|ERROR_NOT_FOUND|This error occurs during driver installation as part of the update.|This issue occurs because details such as the architecture for a driver that's being updated are missing in the registry. Manually add the missing inf file **Arch** value in the Driver operations registry by following these steps:1. Open *regedit*, and navigate to `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\ComponentBasedServicing\DriverOperations\0\2(SequenceID)`2. Review the **Identity** value to determine the value that's missing.3. Manually add the missing value by referring to the information in the **Identity** value. For example, Name: Arch; Type: REG_SZ (String Value); Data: amd64.4. Proceed with installing the failing update.|

## 0x800f0922

| Message | Description | Mitigation |
|---------|-------------|------------|
|CBS_E_INSTALLERS_FAILED|The July cumulative update failed to be installed on Windows Server 2016|In the CBS.log, you might find that updates sometimes roll back when License and Product key tokens fail to be updated. This issue can be resolved by adding write permissions for the "User" and "Network Service" accounts to the _C:\\Windows\\System32\\spp\\_ folder.|

## 0x80070bc9

| Message | Description | Mitigation |
|---------|-------------|------------|
|ERROR_FAIL_REBOOT_REQUIRED|The TrustedInstaller service startup type is set to **Manual** by a Group Policy Object (GPO). Group Policy prevented the startup to complete pending operations.|The TrustedInstaller service changes the startup type from **Manual** to **Automatic** if it encounters an update that has to process a transaction after a restart. If the value is reverted to **Manual** before the restart, the transaction can't be applied. This transaction will be pending and block all other update installations.To fix this issue, change the TrustedInstaller policy to **Automatic**, and restart the computer. If this change doesn't fix the issue, start the computer to WinRE to revert the pending actions. For example, `dism /Image:C:\ /Cleanup-Image /RevertPendingActions`. If this action also has no effect, start the computer to WinRE, rename *\WinSxS\Pending.xml*, and then remove the PendingXMLIdentifier from COMPONENTS Hive.|

## 0x800706be

| Message | Description | Mitigation |
|---------|-------------|------------|
|Failed to install cumulative updates|Windows Server 2016 Std failed to install cumulative packages by using the .msu package. No error is returned. When installing the packages with dism.exe, it returned the error 0x800706be.|The last cumulative update didn't install, and it was corrupted. To resolve this issue, navigate to the registry key for the corrupted update package. Change the "current state" value to 000020 hex (32 dec) - resolved, or 000040 hex (64 dec) - staged, or 000070 hex (112 dec) - installed.|

## Data collection

If you need assistance from Microsoft support, we recommend that you collect the information by following the steps that are provided in Gather information by using TSS for deployment-related issues.

_Source: Microsoft Learn, licensed CC BY 4.0._
