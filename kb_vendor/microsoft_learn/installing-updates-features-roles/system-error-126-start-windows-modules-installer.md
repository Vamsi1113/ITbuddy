<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/installing-updates-features-roles/system-error-126-start-windows-modules-installer -->
# System Error 126 when you start TrustedInstaller

Fixes the System Error 126 that occurs when you start the Windows Modules Installer service.

This article helps fix the System Error 126 that occurs when you start the Windows Modules Installer service.

Applies to:   Windows 7 Service Pack 1, Windows Server 2008 R2 Service Pack 1
_Original KB number:_   959077

## Symptoms

When you start the Windows Modules Installer service, you receive the following error message:

You also receive an error message at the command prompt:

## Cause

This issue occurs if the following registry subkey is changed:

`HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\Version`

## Resolution

To resolve this issue, you have to re-create the expandable string value of the registry subkey that is mentioned in the Cause section.

First, you have to check whether the registry subkey exists. To do this, start Registry Editor, and then browse to the subkey that is mentioned in the Cause section. If the subkey does not exist, you must create it. To do this, follow these steps:

1. Locate the `C:\Windows\Servicing\Version` directory, and note the name of the subfolder in this directory. It will be named something like *6.1.7600.16385*. This is your TrustedInstaller ID.

2. Copy the subfolder name to the clipboard, and then paste it into Notepad for safekeeping.

    > Note:
    > In this example, the TrustedInstaller ID is 6.1.7601.17592.

3. In the `C:\Windows\WinSxS` directory, find a subfolder whose name begins with one of the following strings. (In the following subfolder names, the placeholder **TrustedInstaller ID** represents your TrustedInstaller ID.)

    For 32-bit Windows: x86_microsoft-windows-servicingstack_31bf3856ad364e35_ **TrustedInstaller ID** _none

    For 64-bit Windows: amd64_microsoft-windows-servicingstack_31bf3856ad364e35_ **TrustedInstaller ID** _none

4. Copy the subfolder name to the clipboard, and then paste it into Notepad for safekeeping.

5. Create the registry subkey `HKLM\Software\Microsoft\Windows\CurrentVersion\Component Based Servicing\Version`.

    > Note:
    > To create this key, you have to be an owner of the **Component Based Servicing** key. Then, you have to then give yourself full access permissions.

6. On the **Version** key that you created in step 5, create an expandable string value (or edit it if it already exists). To do this, use the TrustedInstaller ID as your name, and use the full path of the folder that you identified in step 3 as the value.

    > Note:
    > In the full path, you must use `%SystemRoot%\WinSxS\folder_name` instead of `C:\Windows\WinSxS\folder_name`.

7. Click **OK**, and then exit Registry Editor.

You can now start the Windows Modules Installer (TrustedInstaller) service as usual.

## Data collection

If you need assistance from Microsoft support, we recommend you collect the information by following the steps mentioned in Gather information by using TSS for deployment-related issues.

_Source: Microsoft Learn, licensed CC BY 4.0._
