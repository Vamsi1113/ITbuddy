<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/networking/network-gets-disconnected-computer-not-used-after-sign-in -->
# Network gets disconnected when computer isn't used after you sign in to Windows 10

Provides resolutions for the issue where network gets disconnected for several seconds if the computer isn't used after you sign in to Windows 10.

Applies to:   Windows 10

## Symptoms

When you sign in to a computer running Windows 10 and leave it unused for more than 10 minutes, the network gets disconnected for several seconds.

Applications and services that communicate with the computer through LAN will get disconnected from the computer during that period.

> [!Note]
> This is a common scenario in Windows 10 IoT.

## Cause

The Logon pre-scheduled task starts the ProvTool.exe file. This file processes provisioning packages on the system. The ndisuio.sys driver is loaded when the ProvTool.exe starts the DMWapPushService service for the process. When the ndisuio.sys driver binds to the network, the existing connection is interrupted and resumes after a few seconds.

## Resolution

### Method1: Change the loading time of the ndisuio.sys driver

Here's how to change the loading time of ndisuio.sys driver:

1. Open **Registry Editor**.
2. Go to `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Ndisuio`.
3. Double-click **Start** and change the value data to **1**.

    > Note:
    > The value data **1** represents starting the driver when the system starts.
4. Close **Registry Editor**.
5. Restart the system.

### Method 2: Change the start timing of the DMWapPushSvc service

Here's how to change the start timing of the DMWapPushSvc service:

1. Open **Registry Editor**.
2. Go to `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\dmwappushservice`.
3. Double-click **Start** and change the value data to **2**.

    > Note:
    > The value data **2** represents setting the service to start automatically.
4. Close **Registry Editor**.
5. Restart the system.

_Source: Microsoft Learn, licensed CC BY 4.0._
