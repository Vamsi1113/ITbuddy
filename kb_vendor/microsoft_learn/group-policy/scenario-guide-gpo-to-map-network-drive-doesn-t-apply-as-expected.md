<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/group-policy/scenario-guide-gpo-to-map-network-drive-doesn-t-apply-as-expected -->
# Scenario guide: GPO to map network drive doesn't apply as expected

This article introduces a troubleshooting scenario in which network drives can't be mapped by using GPOs.

This scenario guide explains how to use TroubleShootingScript (TSS) to collect data to troubleshoot an issue in which a Group Policy Object (GPO) to map a network drive doesn't apply as expected.

## Troubleshooting guide

Before you proceed, refer to the Applying Group Policy troubleshooting guidance.

## Environment

- Domain name: `contoso.com`
- Active Directory sites: four sites (two domain controllers per site) (Phoenix, London, Tokyo, and Mumbai)
- Number of domain controllers: eight
- Domain controller operating system: Windows Server 2019
- Client machine operating system: Windows 11, version 22H2

## In this scenario

Before we start troubleshooting, here are some scoping questions that can help us understand the situation and narrow down the cause of the issue:

1. What are the client and server operating systems?
   **Answer**: The client machines are Windows 11, version 22H2, and the File server where the mapped drive is located is on the Linux Server.

2. How do you configure the Group Policy preferences?
   **Answer**: We have a GPO named **Mapped-Drive** and this GPO is configured by using Group Policy preferences mapped drives extension.

3. Are all users under the scope of the GPO **Mapped-Drive** impacted?
   **Answer**: We have configured this GPO to the "IT Users" organizational unit (OU). We tested it with four to five users. For all of them, drive Z isn't mapped.

4. What happens if you manually map the drive instead of using Group Policy preferences?
   **Answer**: We can successfully map drive Z by using the `net use` command to the same file server.

5. Is this GPO a new GPO, or did the GPO work before?
   **Answer**: This GPO was working earlier and was used by all users to get mapped drives. Since the last couple of days, the mapped drives aren't working.

6. When you run `gpresult /h` and review the output, do you observe that the GPO **Mapped-Drive** is in the applicable list?
   **Answer**: Yes, we do observe that the **Mapped-Drive** GPO is applied in the applicable list.

7. Have you configured any security filtering, WMI filter, or set up any Deny (Apply) settings for the user or a group?
   **Answer**: The GPO is set up with default settings and no changes are made to the GPO from the perspective of security filtering, WMI filter, or setup of any Deny permissions.

## Troubleshooting

First, collect the following data for troubleshooting. Because we need to trace the logon or sign-in, we need to perform the following tasks as a local administrator or any other user account with local administrator credentials.

> Note:
> These steps require fast user switching to be enabled. If you encounter problems when trying to switch users, check if the following policy or registry value is set:
>
> - Group Policy: The **Hide entry points for Fast User Switching** Group Policy under _Computer Configuration\\Administrative Templates\\System\\Logon_.
> - Registry key: `HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System`.
> - Registry value: `HideFastUserSwitching`

1. Download TSS and extract the ZIP file to the _C:\\temp_ folder. Create the folder if it doesn't exist.
2. Open an elevated PowerShell command and run the command:

   ```powershell
   Set-ExecutionPolicy unrestricted
   ```

3. Go to _c:\\temp\\TSS_, where you have extracted the TSS Zip file.
4. Run `.\TSS.ps1 -Start -Scenario ADS_GPOEx -Procmon`. Accept the agreement, and wait until the TSS starts collecting data.

5. Switch the user, and then sign in with the user account that doesn't see drive Z mapped.
6. Once the sign-in is successful, open a command prompt and run `gpresult /h appliedgpo.htm`. Confirm that the GPO **Mapped-Drive** is in the applicable list.
7. Switch the user again, and then sign in with the user account that has started the TSS Logging. Press Y.
8. TSS will stop collecting data, and the collected data will be located in the _C:\\MSDATA_ folder as a Zip file or a folder named *TSS_\<Machinename\>_\<Time\>_ADS_GPOEx*.

For more information about TSS, see Introduction to TroubleShootingScript toolset (TSS).

## Data analysis

Go to the *c:\msdata* folder where TSS has saved all the reports, and then extract the contents of the ZIP file. Review the file named *\<Client_machinename\>-\<Time\>_Microsoft-Windows-GroupPolicy-Operational.evtx*.

### Starting event 4001

### Event 5017 showing the "Users" OU

The GPO **Mapped-Drive** is linked to the "Users" OU.

### Event 5312 showing the list of applicable GPOs

We do see that the GPO **Mapped-Drive** is in the applicable list.

### Event 4016 showing the Group Policy Drive Maps extension was processed and successful

### Group Policy preferences tracing

From the Group Policy operational logs, we observe that the Group Policy was processed and the Group Policy preferences were applied successfully. In addition to the above, we can also review the Group Policy preferences logging/tracing collected by the TSS tool.

Group Policy preferences tracing is an extra logging that we can enable for any Group Policy preferences client-side extension. The TSS GPOEx tracing is enabled by default.

> Note:
> If you wish to manually enable the GPSVC logging, follow Enabling Group Policy Preferences Debug Logging using the RSAT.

Here, we introduce how to review and search the GPSVC log to confirm the Group Policy was applied to the client successfully.

In *\<Clientmachinename\>_\<Date_Time\>_GPPREF_User.txt*, we observe that the GPP Mapped Drives extension is starting the processing.

> Note:
> For brevity and readability purposes, the analysis only contains snippets of relevant troubleshooting data and not all data in the log.

```output
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] Entering ProcessGroupPolicyExDrives()
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] SOFTWARE\Policies\Microsoft\Windows\Group Policy\{aaaabbbb-0000-cccc-1111-dddd2222eeee}
```

The Group Policy Mapped Drives extension identified a GPO that's configured with this extension, and the name is **Mapped-Drive**:

```output
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] GPC : LDAP://CN=User,cn={aaaabbbb-0000-cccc-1111-dddd2222eeee},cn=policies,cn=system,DC=contoso,DC=com
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] GPT : \\contoso.com\SysVol\contoso.com\Policies\{aaaabbbb-0000-cccc-1111-dddd2222eeee}\User
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] GPO Display Name : Mapped-Drive
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] GPO Name : {aaaabbbb-0000-cccc-1111-dddd2222eeee}
```

We observe that drive Z is successfully mapped:

```output
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] Starting class <Drive> - Z:.
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] Policy is not flagged for removal.
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] Completed class <Drive> - Z:.
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] Completed class <Drives>.
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] EVENT : The user 'Z:' preference item in the 'Mapped-Drive {aaaabbbb-0000-cccc-1111-dddd2222eeee}' Group Policy Object applied successfully.
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] Completed class <Drive> - Z:.
yyyy-mm-dd hh:mm::ss:sss [pid=0x3134,tid=0x4fc] Completed class <Drives>
```

## Use procmon to find the process removing drive Z

At this moment, we know that the Group Policy preferences are applied, but drive Z isn't visible. We can manually map the drive, but the drive will be deleted during sign-in or logon. Therefore, there are some other settings that delete drive Z on the computer during logon.

Next, we need to analyze the procmon trace to observe what deleted the mapped drive. The TSS tool also collects the procmon trace with the `-Procmon` switch that we used to collect the data.

The procmon trace can be overwhelming. Follow these steps to set up a filter to view the data. The filter can be used to troubleshoot any issues related to mapped drives.

1. Open the file *\<Clientmachinename\>_\<date_time\>_Procmon_0.pml*.
2. Select **Filter** - **Filter**.
3. Add the filter: **Detail** - **Contains** - **Z:**.

4. The output of the filter shows two processes: *cmd.exe* and *net.exe*.

5. Double-click *net.exe* and go to the **Process** tab that includes the following parameters:

   - Command line: The deletion operation of the mapped drive.
   - Parent PID: The parent process of *net.exe* is 13436.
   - User: The name of the user in whose context this process was run. In our example, it's the user account itself.

Then, set up another filter to identify who spawned *net.exe* using the parent process filter.

1. Go to **Filter** - **Filter** and select **Reset**.
2. Now apply the following filter using the PID of the parent.

We observe that the PID is *cmd.exe*, and it appears it's processing a GPO with the following parameters:

- Command line: `C:\Windows\system32\cmd.exe /c "\contoso.com\SysVol\contoso.com\Policies{E347CA05-D21D-433D-9BCA-2FE555336749}\User\Scripts\Logon\deletedrives.bat"`
- Parent PID: The parent process of *cmd.exe* is 14900.
- User: The name of the user in whose context this process was run. In our example, it’s the user itself.

Now, use the same mechanism and the PID filter again by going to **Filter** - **Filter**, selecting **Reset**, and applying the following filter:

We observe that *GPScrpit.exe* is the parent process of the *cmd.exe* process. Using this hint, we observe that there's a Group Policy script that deleted the mapped drive.

## Summary

1. *Net.exe* is deleting the mapped drive, and its parent process is *cmd.exe*. The following command is executed:

   ```console
   net use z: /delete
   ```

2. *CMD.exe* is processing a .bat file *deletedrives.bat*, and its parent process is *GPScript.exe*.

   ```console
   C:\Windows\system32\cmd.exe /c "\contoso.com\SysVol\contoso.com\Policies{E347CA05-D21D-433D-9BCA-2FE555336749}\User\Scripts\Logon\deletedrives.bat"
   ```

3. *GPScript.exe* is the process that runs during logon to process any logon scripts.

We need to identify the GPO that contains this logon script. Here are two methods.

### Method 1: Use the Gpresult /h output collected during log collection

### Method 2: Use the Group Policy management snap-in (GPMC.msc)

1. Open *GPMC.msc* on a domain controller or machine where you have the snap-in installed.
2. Right-click the domain and select **Search**.
3. In the search items, select **GUID**, and then enter the GPO GUID that we found in the command of *cmd.exe*.

We identified that the **DomainWideSettings** GPO has the logon script.

If you don't want the **DomainWideSettings** GPO to delete the mapped drive, use one of these methods:

- Remove the logon scripts from the GPO **DomainWideSettings** as this GPO is used to configure other domain-wide settings.
- Unlink the GPO **DomainWideSettings** completely.
- Set a "Block Policy Inheritance" on the "Users" OU where the user object is located.
- Set a Deny "Apply GPO" for the "Users" group on the GPO **DomainWideSettings**.

_Source: Microsoft Learn, licensed CC BY 4.0._
