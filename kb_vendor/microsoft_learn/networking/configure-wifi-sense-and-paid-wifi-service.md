<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/networking/configure-wifi-sense-and-paid-wifi-service -->
# Configure Wi-Fi Sense and Paid Wi-Fi Services

Discusses the methods to configure Wi-Fi Sense and Paid Wi-Fi Services on Windows 10 Version 1607 computers that are deployed in an enterprise.

This article discusses the methods to configure Wi-Fi Sense and Paid Wi-Fi Services in Windows 10.

Applies to:   Windows 10 - all editions
_Original KB number:_   3085719

## Summary

Wi-Fi Sense can automatically make Wi-Fi connections on your computer so that you can go online quickly in more locations. Wi-Fi Sense can connect you to open Wi-Fi hotspots that are collected through crowdsourcing, or to Wi-Fi networks that your contacts share with you through Wi-Fi Sense.

Paid Wi-Fi Services enable you to get online by buying Wi-Fi at the hotspot through Microsoft Store. Windows will temporarily connect to open hotspots to see if paid Wi-Fi services are available.

## More information

To disable Wi-Fi Sense and Paid Wi-Fi Services on computers in the enterprise, use the following methods, as appropriate for your device management process:

Configuring through the Windows Provisioning framework

Configuring through legacy Unattended Windows setup (if the enterprises use unattended setup for provisioning)

IT administrators can also use Group Policy to disable Wi-Fi Sense and Paid Wi-Fi Services.

### For Windows 10 Version 1511 or later versions of Windows

Configure the Group Policy Object **Allow Windows to automatically connect to suggested open hotspots, to networks shared by contacts, and to hotspots offering paid services** under **Computer Configuration\\Administrative Templates\\Network\\WLAN Service\\WLAN Settings\\**.

### For earlier versions of Windows than Windows 10 Version 1511

Configure the Group Policy to create and set the following DWORD registry value to **0** to disable Wi-Fi Sense:

`HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\config\AutoConnectAllowedOEM`

> Note:
> If you use Group Policy to disable Wi-Fi Sense, this also disables the following related Wi-Fi Sense features:

- Connect automatically to open hotspots
- Connect automatically to networks shared by my contacts
- Allow me to select networks to share my contacts

More information is available on TechNet: Registry Extension.

_Source: Microsoft Learn, licensed CC BY 4.0._
