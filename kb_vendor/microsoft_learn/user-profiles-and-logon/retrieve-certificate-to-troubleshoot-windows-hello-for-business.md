<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/user-profiles-and-logon/retrieve-certificate-to-troubleshoot-windows-hello-for-business -->
# Retrieve Certificate to Troubleshoot Windows Hello for Business Logon Failures

This article introduces a solution to retrieve certificate information from Active Directory.

Applies to:   Windows Server (All supported versions), Windows client (All supported versions)

This article introduces how to troubleshoot Windows Hello for Business (WHfB) logon failures in a hybrid environment.

## Scenario

After deploying WHfB to a key trust hybrid environment, you encounter one of the following issues:

- Users can't log on to a hybrid joined device by using WHfB.
- Single sign-on (SSO) to on-premises resources fails after logging on to a Microsoft Entra ID joined device by using WHfB.

## Analysis

To fix these issues, you need to review the certificate used for authentication.

The **msDS-KeyCredentialLink** attribute of the Active Directory user object contains information on the certificate used for authentication. This certificate is created during the user's WHfB provisioning and uploaded to Microsoft Entra ID. This information should then be synchronized from Microsoft Entra ID to on-premises Active Directory through Microsoft Entra Connect. If this attribute isn't properly synchronized, you might see WHfB logon failures, or SSO failures to on-premises resources.

## Resolution

To troubleshoot this issue, we recommend using the script in Scripts: View the certificate information in the msDS-KeyCredentialLink attribute from AD user objects to retrieve and analyze the certificate information.

_Source: Microsoft Learn, licensed CC BY 4.0._
