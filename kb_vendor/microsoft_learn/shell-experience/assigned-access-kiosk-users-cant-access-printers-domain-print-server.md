<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/assigned-access-kiosk-users-cant-access-printers-domain-print-server -->
# Assigned Access kiosk users can't access printers that use a domain print server

Discusses an issue in which Assigned Access kiosk users can't access printers that use a domain-joined print server because the print server requires domain authentication.

## Summary

Assigned Access kiosk users can't access printers that use domain-joined print server. This issue occurs because kiosk users typically run under a local account, and a local account can't authenticate against a domain print server. To resolve this issue, configure the kiosk device to connect directly to the printer by using the printer's hostname or IP address.

## Symptoms

To support Assigned Access kiosk users, you deploy printers that use a common domain-joined print server. However, the kiosk users can't access the printers. Users who have regular domain accounts can access the printers.

## Cause

This behavior is by design. It reflects the intended function of domain-level Group Policy scope and domain authentication.

This behavior occurs because the printers use a domain-joined print server. This configuration is typical when you use domain-level or user-level Group Policy to manage printer availability. To see or use a printer in this configuration, a user has to use a domain account to authenticate against the domain print server.

In Assigned Access scenarios, kiosk users typically run under the context of a local account instead of a domain account. Because they don't have domain accounts, kiosk users can't authenticate against the domain print server. Therefore, they can't use the printers.

## Resolution

> Important:
> To change a device's printer setup, you must have the **Manage Printer** permission. Typical kiosk users can't install or configure printers.

To make a printer available to Assigned Access kiosk users, configure the device that supports kiosk users to connect directly to the printer. For example, add the printer to the device by specifying the printer's hostname or IP address, and a Standard TCP/IP port. Make sure that you install the correct printer driver.

In this configuration, the printer is available to all the users on the device, and doesn't require domain authentication.

_Source: Microsoft Learn, licensed CC BY 4.0._
