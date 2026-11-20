<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/system-management-components/rsat-client-missing-dns-server-tool -->
# DNS server tool is missing for RSAT client

This article addresses an issue in which DNS server tools are missing for RSAT client in Windows 10.

This article provides help to solve an issue where DNS server tools are missing after you install the Remote Server Administration Tools for Windows 10 (RSATClient).

Applies to:   Windows 10, version 2004, Windows 10, version 1909, Windows 10, version 1803, Windows 10, version 1709
_Original KB number:_   4055558

## Symptom

After you install the RSATClient (WindowsTH-RSAT_WS_1709-x64.msu) by double-clicking the package, the DNS server tools are missing.

This article provides alternative steps to install the RSATClient so that all tools are installed correctly.

## Workaround

1. Make sure that update KB 2693643 isn't already installed on the computer. If the update is installed, uninstall the update by using these steps:
    1. Press Win key+R, type *appwiz.cpl* and then press Enter.
    2. Select **View Installed Updates**.
    3. Locate and uninstall the update.
    4. Restart the computer if it prompts.

2. Create a new directory. For example, **temp**.

3. For x64 versions of Windows, create files unattend_x64.xml and installx64.bat. For x86 versions of Windows, create files unattend_x86.xml and installx86.bat.

4. Download the WindowsTH-RSAT_WS_1709-x64.msu package for x64 versions of Windows or the WindowsTH-RSAT_WS_1709-x86.msu package for x86 versions of Windows, and save the package in the new directory.

5. Start a command prompt with administrative permissions and browse to the temp directory.

6. Run installx64.bat for x64 versions of Windows or run installx86.bat for x86 versions of Windows.

> Note:
>
> - After installation, you can clear the contents of the temp directory.
> - No restart is required unless you are prompted.

## The installx64.bat file contents

```console
@echo off
md ex
expand -f:* WindowsTH-RSAT_WS_1709-x64.msu ex\
cd ex
md ex
copy ..\unattend_x64.xml ex\
expand -f:* WindowsTH-KB2693643-x64.cab ex\
cd ex
dism /online /apply-unattend="unattend_x64.xml"
cd ..\
dism /online /Add-Package /PackagePath:"WindowsTH-KB2693643-x64.cab"
cd ..\
rmdir ex /s /q
```

## The unattend_x64.xml file contents

```xml
<?xml version="1.0" encoding="UTF-8"?>
<unattend xmlns="urn:schemas-microsoft-com:setup" description="Auto unattend" author="pkgmgr.exe">
    <servicing>
        <package action="stage">
            <assemblyIdentity buildType="release" language="neutral" name="Microsoft-Windows-RemoteServerAdministrationTools-Client-Package-TopLevel" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" version="10.0.16299.2"/>
            <source location="." permanence="temporary"/>
        </package>
    </servicing>
</unattend>
```

## The installx86.bat file contents

```console
@echo off
md ex
expand -f:* WindowsTH-RSAT_WS_1709-x86.msu ex\
cd ex
md ex
copy ..\unattend_x86.xml ex\
expand -f:* WindowsTH-KB2693643-x86.cab ex\
cd ex
dism /online /apply-unattend="unattend_x86.xml"
cd ..\
dism /online /Add-Package /PackagePath:"WindowsTH-KB2693643-x86.cab"
cd ..\
rmdir ex /s /q
```

## The unattend_x86.xml file contents

```xml
<?xml version="1.0" encoding="UTF-8"?>
<unattend xmlns="urn:schemas-microsoft-com:setup" description="Auto unattend" author="pkgmgr.exe">
    <servicing>
        <package action="stage">
            <assemblyIdentity buildType="release" language="neutral" name="Microsoft-Windows-RemoteServerAdministrationTools-Client-Package-TopLevel" processorArchitecture="x86" publicKeyToken="31bf3856ad364e35" version="10.0.16299.2"/>
            <source location="." permanence="temporary"/>
        </package>
    </servicing>
</unattend>
```

_Source: Microsoft Learn, licensed CC BY 4.0._
