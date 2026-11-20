<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/remote/local-computer-behaves-as-if-windows-logo-key-pressed -->
# Local computer behaves as if the Windows logo key is pressed after you switch from a Remote Desktop session

Fixes an issue in which the Windows logo key is displayed as pressed after you use an RDP session in Windows.

This article provides a workaround for an issue where your local computer behaves as if you are always pressing and holding the Windows logo key after you start a Remote Desktop Protocol (RDP) session to a remote computer.

_Original KB number:_   4467266

## Symptoms

After you start a RDP session to a remote computer, your local computer behaves as if you are always pressing and holding the Windows logo key. For example, when you press the R key, the **Run** box opens. When you press the E key, File Explorer starts.

## Cause

This issue occurs if you use particular settings for your Remote Desktop connection and you take the following steps:

1. Before you connect to the remote computer, open the **Local Resources** tab of the **Remote Desktop Connection** dialog box, and set **Apply Windows key combinations** to either **On the remote computer** or **Only when using the full screen**.

2. To start the Remote Desktop session, select **Connect**.
3. If you selected **Only when using the full screen** in step 1, expand the Remote Desktop session window to full screen. If you selected **On the remote computer**, go to step 4.
4. Do the following key sequence:
    1. Press and hold the L key.
    2. Press and hold the Windows logo key.
    3. Release the L key.
    4. Release the Windows logo key.
5. Disconnect the Remote Desktop session, or switch from the Remote Desktop session window to a window on the local computer.

## Workaround

To work around this issue, press and release the Windows logo key again after you return to the local computer.

_Source: Microsoft Learn, licensed CC BY 4.0._
