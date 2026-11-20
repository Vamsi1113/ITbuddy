<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/certificates-and-public-key-infrastructure-pki/integrated-unblock-screen-not-displayed-smart-card-pin-blocked -->
# Integrated Unblock screen not displayed when smart card PIN is blocked

Provides several methods to resolve the issue which Integrated Unblock screen is not displayed when smart card PIN is blocked.

Applies to:   Windows 10

Assume that the **Allow Integrated Unblock screen to be displayed at the time of logon** group policy is enabled in Windows 10. After several failed logon attempts because of an incorrect PIN, the smart card is blocked and you receive this error message:

> The smart card is blocked. Please contact your administrator for instructions on how to unblock your smart card.

In this scenario, the Integrated Unblock screen isn't displayed.

To fix this issue, use one of the following methods and then try again to sign in to Windows by using the blocked smart card.

- Restart the computer.
- Use another method to sign in to Windows (such as username and password).
- Use another account to sign in to Windows and then sign out.
- Use the blocked smart card to sign in to another computer.

_Source: Microsoft Learn, licensed CC BY 4.0._
