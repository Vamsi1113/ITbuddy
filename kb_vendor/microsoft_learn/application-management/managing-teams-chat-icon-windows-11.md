<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/application-management/managing-teams-chat-icon-windows-11 -->
# Managing the Teams Chat icon on Windows 11

This article helps you to manage the Chat icon on Windows 11.

This article describes how to manage the Chat icon on Windows 11.

Applies to:   Windows 11

## Introduction to Teams Chat icon on Windows 11

> Note:
> This article is intended for use by IT professionals who want to manage the Chat icon on Windows 11. If you're looking for more information about Chat in Windows 11, see Get started with Chat in Windows 11.

There are two different versions of Teams on Windows 11:

- The first is installed by default and is intended for personal use through a Microsoft account.
- The second is for an enterprise environment in which the Teams app and infrastructure will be managed by an administrator. This version is intended to be used through a work or school account.

After Windows 11 is installed, you can start using the default version of Teams Chat. By default, Chat is pinned to the taskbar, and you can use your personal account to start a call or a chat session with your colleagues or friends. To use a work or school account, you must have the Teams version installed for the work environment.

> Note:
> The Teams for work app is not included in the Windows 11 installer and will not be installed until you set it up. Before you install the Teams app, there will be an app icon (small camera) on the taskbar.

### Scenario 1: Chat icon is present on the Taskbar, but Teams isn't installed.

If you see the Chat icon on the Taskbar but you don't see the Teams app, select the **Chat** icon, and then check whether the following screen appears.

If you see this screen, select **Continue** to set up Teams.

> Note:
> This indicates that Teams is not installed. Select **Continue** to proceed with installing the app for the logged-on user.

Run the following PowerShell cmdlet to check whether the Windows 11-based device has Teams installed:

```PowerShell
Get-AppxPackage -name '*teams'
```

If this command displays no results, the Teams app isn't installed.

### Scenario 2: Chat icon is turned on, but Teams isn't configured.

If you see the Chat icon on the taskbar, select the **Chat** icon, and then check whether the following screen appears.

This screen indicates that Teams is installed, but not configured for the logged-on user. To configure Teams, select **Get Started**.

Alternatively, users can also run the following PowerShell cmdlet to confirm the installation status of Teams:

```PowerShell
Get-AppxPackage -name '*teams'
```

If this command returns the installation status, the Teams app is installed.

You'll see the same results when you configure Teams. Also, you should see a list of contacts in the Chat window.

> Note:
> When you select **Get Started** and complete the configuration of Teams, a list of contacts appears in place of the Get Started screen which means that Teams is installed and fully configured.

### Scenario 3: Chat icon is turned off and Teams app is installed.

Admins can choose to disable the Chat icon on the taskbar. If the Teams app is installed, the app will appear on **Start > All apps > Microsoft Teams**.

You can also verify the installation by running the following PowerShell cmdlet:

```PowerShell
Get-AppxPackage -name '*teams'
```

To turn on Chat, right-click the taskbar, select **Taskbar settings**, and then move the Chat slider to **On**.

## Using Group Policy settings

Admins can customize Group Policy settings, such as Show, Hide, and Disabled, for the Chat icon.

> Note:
> The **Disabled** option is available on the **Enabled > State list**. Do not confuse this command with setting the policy to **Disabled**. The policy is located under *Computer Configuration\\Administrative Templates\\Windows Components\\Chat\\*.

You can configure the Chat icon on the taskbar using the following dialog box.

## Removing the Chat icon using Intune

Use the new CSP setting, "Experience/ConfigureChatIcon", which removes the Chat icon. This requires the Enterprise or Education edition. For more information, see Policy CSP – Experience.

Create a new Configuration Profile for Windows 10 and later, type *Custom* and use the following setting:

`OMA-URI = ". /Device/Vendor/MSFT/Policy/Config/Experience/ConfigureChatIcon"`

The values for this policy are 0, 1, 2, and 3. This policy defaults to 0 if not enabled.

- **0 – Not Configured**: The Chat icon follows the default configuration for your Windows edition.
- **1 – Show**: The Chat icon appears on the taskbar by default. You can show or hide it in Settings.
- **2 – Hide**: The Chat icon doesn't appear by default. You can show or hide it in Settings.
- **3 – Disabled**: The Chat icon doesn't appear on the taskbar. Settings are not available to show or hide the icon.

## Removing the Chat icon using Intune – Settings Catalog

To remove the Chat icon using Intune – Settings Catalog, do the following steps:

1. Create a new Configuration Policy.
1. Search for Experience.
1. Select **Configure Chat icon**.

## Frequently asked questions (FAQ)

### As an admin, how do I uninstall the Teams app if users have installed it?

If Teams was installed, use this PowerShell cmdlet to uninstall it:

```PowerShell
remove-appxpackage -package "MicrosoftTeams_21302.202.1065.6968_x64__8wekyb3d8bbwe"
```

### Can I remove the Teams app from the default Windows image?

The default Windows image doesn't include the Teams app.

_Source: Microsoft Learn, licensed CC BY 4.0._
