<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/user-profiles-and-logon/hold-shift-key-shutting-down-not-disable-automatic-logon -->
# Holding Shift key while shutting down or logging off may not disable automatic logon

Resolves an issue where you can't disable automatic logon by holding the Shift key while shutting down or logging off from a computer.

This article helps resolve an issue where you can't disable automatic logon by holding the Shift key while shutting down or logging off from a computer.

Applies to:   Windows 10 – all editions
_Original KB number:_   2840544

## Symptoms

Consider the following scenario:

- You connect a USB keyboard to a computer that is running Windows.
- Automatic logon is enabled.
    > [!Note]
    > To enable automatic logon, set the AutoAdminLogon registry value to 1 by using Registry Editor. For more information, see the More information section at the end of this KB article.
- You log off from the computer to log on with a different user account, holding down the Shift key on the USB keyboard after logging off to override the automatic logon setting.

In this scenario, the Secure Attention Sequence (logon) dialog box doesn't appear.

## Resolution

To resolve this issue, be sure to hold down the Shift key before choosing to log off or restart the system. Alternatively, you can try pressing the Shift key multiple times.

## More information

For more information about how to enable automatic logon in Windows, click the following article number to view the article in the Microsoft Knowledge Base:

310584 How to enable automatic logon in Windows

_Source: Microsoft Learn, licensed CC BY 4.0._
