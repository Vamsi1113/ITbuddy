<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/group-policy/scenario-guide-wallpaper-gpo-does-not-apply-on-some-client-computers -->
# Scenario guide: Wallpaper GPO doesn't apply on some client computers

This article introduces a troubleshooting scenario in which the Wallpaper GPO doesn't apply on some client computers.

This scenario guide explains how to use TroubleShootingScript (TSS) to collect data to troubleshoot an issue in which the wallpaper Group Policy Object (GPO) doesn't apply on some client computers.

## How Group Policy is applied on client computers

1. The Group Policy service on the client computer enumerates the distinguished name (DN) of the user account.
2. The Group Policy service enumerates the **GPLINK** and **GPOptions** attributes of the user account in the order of local GPO, site GPO, domain, and organizational unit (OU).
3. The Group Policy service makes a list of GPOs to apply or deny.

For more information, see Applying Group Policy and Filtering the Scope of a GPO.

## Troubleshooting guide

Before you proceed, refer to the Applying Group Policy troubleshooting guidance.

## Environment

- Domain name: `contoso.com`
- Active Directory sites: four sites (two domain controllers per site) (Phoenix, London, Tokyo, and Mumbai)
- Number of domain controllers: eight
- Domain controller operating system: Windows Server 2019
- Client computer operating system: Windows 11, version 22H2

## In this scenario

Before we start troubleshooting, here are some scoping questions that can help us understand the situation and narrow down the cause of the issue:

1. What are the client and server operating systems?
   **Answer**: Windows Server 2019 domain controllers and Windows 11, version 22H2 client computers.

2. Are all users experiencing the issue or only some users?
   **Answer**: The issue occurs when a user signs in to a client computer on the Tokyo site. However, if the same user signs in from a client computer on the Phoenix site, the wallpaper policy applies fine.

3. What settings are configured by using the **Wallpaper-GPO-Tokyo** GPO?
   **Answer**: There are some settings, and the most important one is a user-side setting with the following configuration:

   - Path: *User Configuration\Administrative templates\Desktop\Desktop\Desktop Wallpaper*
   - GPO setting: **Enabled**
   - Wallpaper location: *\contoso.com\netlogon\home.jpg*
   - Wallpaper style: **Fit**

4. Is the **Wallpaper-GPO-Tokyo** GPO a new GPO or an old GPO in the scope of the Tokyo OU?
   **Answer**: This is a new GPO that we configured on the Phoenix site, and this GPO was created a couple of days ago.

5. When you run `gpupdate /force /target:user`, do you observe any error messages on the working and failing computers?
   **Answer**: No error occurs when we run `gpupdate /force` on the working or the failing client computer.

6. Are the old GPOs applied and only this GPO isn't?
   **Answer**: We observe that the old GPOs are applied, and only this new wallpaper GPO isn't applied.

7. Do you observe that all users under the scope of this GPO from Tokyo aren't applied, or is this problem observed only for some subset of users?
   **Answer**: All users in the scope of this GPO from the Tokyo site are experiencing this issue, but the same users, if they sign in from a client machine on the Phoenix site, don't experience the issue.

## Troubleshooting

First, we need to collect data on both a client computer on Phoenix and a client computer on Tokyo. Follow these steps on each computer:

1. Download TSS and extract the ZIP file to the *C:\temp* folder. Create the folder if it doesn't exist.
2. Sign in with the user account that's experiencing the issue.
3. Open an elevated PowerShell command and run the command:

   ```powershell
   Set-ExecutionPolicy unrestricted
   ```

4. Go to *c:\temp\TSS*, where you have extracted the TSS Zip file.
5. Run `.\TSS.ps1 -Start -Scenario ADS_GPOEx`. Accept the agreement, and wait until the TSS starts collecting data.

6. Open a normal command prompt as user and run `gpupdate /force /target:user`
7. When the processing is complete, press Y on the PowerShell command where you're running TSS.

8. TSS will stop collecting data, and the collected data will be located in the *C:\MSDATA* folder as a Zip file or a folder named *TSS_\<Machinename\>_\<Time\>_ADS_GPOEx*.

For more information about TSS, see Introduction to TroubleShootingScript toolset (TSS).

### Compare GPResult

On both computers, go to the *c:\msdata* folder where TSS has saved all the reports, and then extract the contents of the ZIP file. Review the file named *\<Clientmachinename\>_\<Time\>GPResult-H_Stop.html*.

Go to the **User details** section. The GPO in question, **Wallpaper-GPO-Tokyo**, is in the applied list on the working machine and not present in the broken machine.

> Note:
> There are other GPOs like **Mapped-Drive** and **Phoenix-SiteGPO** on the applied machines. However, these two GPOs are site-level GPOs and only apply when the Group Policy client detects the client machine is on the Phoenix site. Therefore, they aren't relevant to our troubleshooting scope.

### Compare event logs

Group Policy operational logs provide more information about the processing. Open both the GPO operational logs to compare the *\<Machinename\>-Microsoft-Windows-GroupPolicy-Operational.evtx* file from the TSS output.

> Tip:
> The Group Policy starting event ID is 4116, and the Group Policy ending event is 8005.

Sort the event logs in chronological order. Search for event 4116 and walk some important events in the upward direction. When reviewing the working and the failing clients, the only difference is that the failing client machine gets its Group Policy from DC6.contoso.com on the Tokyo site.

Event ID 5312 indicates that the Group Policy service detected that it has to process five GPOs on the working computer and three GPOs on the failing computer. As we have already discussed, the **Phoenix-SiteGPO** and **Mapped-Drive** GPOs are site-level GPOs, and the only difference is that the **Wallpaper-GPO-Tokyo** GPO isn't applied.

## Summary

When we compare event ID 5312 from the working computer to the failing computer, we observe that the Group Policy client service didn't enumerate the **Wallpaper-GPO-Tokyo** when it connected to DC6. We also confirm that the GPO scope is correct. Therefore, the cause of the above scenario can be an issue with Active Directory (AD) replication.

The Distributed File System Replication (DFSR) engine is dependent on the AD replication. If AD replication breaks, the DFSR replication also breaks. This could lead to the issue in our scenario where the GPO isn't in either the "Applied" or "Denied" list.

> Note:
> If AD replication works fine and DFSR breaks, we might encounter another issue where the GPO is in the Deny list.

To troubleshoot the AD replication issue, see Active Directory replication error 1722: The RPC server is unavailable. In this scenario guide, we discovered a bad router that blocks the RPC port to the Tokyo site, which caused an AD replication issue.

_Source: Microsoft Learn, licensed CC BY 4.0._
