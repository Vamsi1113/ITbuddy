<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/group-policy/cannot-disable-microsoft-store -->
# Can't disable Microsoft Store via Group Policy

Describes an issue that prevents you from using Group Policy to disable the Windows Store app on a computer that's running Windows 10 Pro.

This article describes an issue that prevents you from using Group Policy to disable the Windows Store app on a computer that's running Windows 10 Pro.

Applies to:   Windows client (All supported versions)
_Original KB number:_   3135657

## Symptoms

On a computer that's running Windows 10 Pro, you upgrade to Windows 10, version 1511, Windows 10, version 1809 or Windows 10, version 1903. After the upgrade, you notice that the following Group Policy settings to disable Microsoft Store are not applied, and you cannot disable Microsoft Store:

- **Computer Configuration** > **Administrative Templates** > **Windows Components** > **Store** > **Turn off the Store application**

- **User Configuration** > **Administrative Templates** > **Windows Components** > **Store** > **Turn off the Store**

## Cause

This behavior is by design. In Windows 10, version 1511, Windows 10, version 1809, and Windows 10, version 1903, these policies are applicable to users of the Enterprise and Education editions only.

_Source: Microsoft Learn, licensed CC BY 4.0._
