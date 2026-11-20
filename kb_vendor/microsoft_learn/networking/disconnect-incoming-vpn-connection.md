<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/networking/disconnect-incoming-vpn-connection -->
# Disconnect incoming VPN connection

Describes how to disconnect an incoming VPN connection when an option to disconnect the incoming VPN connection is not displayed in the View Available Networks dialog box.

This article describes how to disconnect an incoming VPN connection when an option to disconnect the incoming VPN connection is not displayed in the View Available Networks dialog box.

_Original KB number:_   2737610

> Note:
> When you right-click an incoming VPN connection in Windows Server 2012 and then click **Connect/Disconnect**, the **View Available Networks**  dialog box appears. However, an option to disconnect the incoming VPN connection is not displayed.

## More information

To disconnect an incoming VPN connection, follow these steps:

1. Open Network Connections. To do this, use either of the following methods:
   - Swipe in from the right edge of the screen, or point to the lower-right corner of the screen, and then click **Search.** Then, type ncpa.cpl, and then click the **Ncpa.cpl** icon.

   - Press Win+R to open the **Run** window, type ncpa.cpl, and then click **OK**.

2. Right-click the incoming VPN connection that you want to disconnect, and then click **Status**.

3. On the **General** tab, click **Disconnect**.

4. Close Network Connections.

_Source: Microsoft Learn, licensed CC BY 4.0._
