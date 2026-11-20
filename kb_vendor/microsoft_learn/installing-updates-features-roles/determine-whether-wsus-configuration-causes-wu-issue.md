<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/installing-updates-features-roles/determine-whether-wsus-configuration-causes-wu-issue -->
# Determine Whether WSUS Configuration Causes WU Installation Failures

Helps you isolate whether the cause of a WU issue is with the WSUS configuration or the WU service.

Assume that Windows Server Update Service (WSUS) is deployed in an environment. This article helps you determine whether a Windows Update (WU) issue is caused by the WSUS configuration or the WU service.

## Introduction

When WSUS is used to manage Windows updates, it can be difficult to determine the cause of updates not being delivered to the Windows client. The issue can be caused by the WU service subsystem, the WSUS configuration, or the Windows client's ability to sync with the WSUS server.

To help narrow down the cause, a quick and easy test is to try to manually install the update on the client.

- If the update can be installed manually, the problem is likely due to a WSUS configuration or communication error.
- If the update fails to install manually, note the error and follow the guidance in the next section.

## Troubleshooting

To determine whether the update is from WSUS or from WU, see Use Windows Update client policies and WSUS together

To troubleshoot WU issues, see the following articles:

- Troubleshoot problems updating Windows
- Troubleshoot issues with Windows Server Update Services (WSUS) client agents
- How to download updates that include drivers and hotfixes from the Windows Update Catalog
- Microsoft Update Catalog

_Source: Microsoft Learn, licensed CC BY 4.0._
