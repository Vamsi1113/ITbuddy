# How to: apps, updates and system tools

## Install an app
Steps: use the company app store: **Company Portal** or **Software Center** in Start. Pick the app and select **Install**. Apps from the internet usually need IT approval and administrator rights.
Tobi can: install programs from the approved software list after you approve, and check whether a program is on that list.

## Uninstall an app
Steps: Settings > Apps > **Installed apps** (Windows 11) or Apps & features, select the ... next to the app > **Uninstall**. Some company apps cannot be removed.
Call IT when the app is required by the company or the uninstall fails.

## Stop apps from starting with Windows
Steps: Settings > Apps > **Startup**, switch off apps you do not need right away. Or Task Manager (Ctrl + Shift + Esc) > **Startup apps**.
Tobi can: list the programs that start with Windows and open the Startup apps settings.

## Close a frozen app (End task)
Steps: press **Ctrl + Shift + Esc** to open Task Manager, select the app that says "Not responding" > **End task**. Unsaved work in that app is lost.
Tobi can: show what uses the most memory and CPU, and close a program after you approve.

## See what is using memory, CPU or disk
Steps: Task Manager (Ctrl + Shift + Esc) > **Processes**: click the CPU, Memory or Disk column to sort. **Performance** shows totals and how much RAM the PC has.
Tobi can: measure CPU, memory and disk use right now and list the top programs.

## Check for Windows updates or pause them
Steps: Settings > **Windows Update** > **Check for updates**, then restart when asked. **Pause updates** delays them for a week or more. Company devices may control updates centrally.
Tobi can: show the latest installed updates and whether a restart is pending.

## Restart properly (and why it helps)
Steps: Start > Power > **Restart**. Shut down with Fast Startup does not fully reset Windows, so a Restart clears more problems. Save your work first.

## Start in Safe Mode
Steps: Start > Power, hold **Shift** and select **Restart**. Then Troubleshoot > Advanced options > Startup Settings > **Restart** > press **4** (or 5 with networking). Restart normally to leave Safe Mode.
Good to know: on a BitLocker-encrypted device you may be asked for the recovery key.
Call IT before using Safe Mode on a work device if you are not sure.

## Repair Windows system files (sfc and DISM)
Steps: open Start, type **cmd**, right-click Command Prompt > **Run as administrator**, then run `sfc /scannow`. If it cannot fix everything, run `DISM /Online /Cleanup-Image /RestoreHealth` and then `sfc /scannow` again. Restart afterwards.
Call IT when you do not have administrator rights.

## Reset or repair one app
Steps: Settings > Apps > Installed apps > ... next to the app > **Advanced options** > **Repair** (keeps data) or **Reset** (clears its data). Office: Settings > Apps > Microsoft 365 > **Modify** > **Quick Repair**.

## Go back with System Restore
Steps: open Start, type **Create a restore point** > **System Restore** > pick a point from before the problem. Your documents are not touched; apps installed after that point are removed.
Call IT when System Restore is switched off or you are not an administrator.

## Get remote help from IT (Quick Assist)
Steps: open Start, type **Quick Assist**, choose **Get help** and type the code that the IT person gives you. Only share your screen with IT staff you contacted yourself.

## Run a command in Command Prompt or PowerShell
Steps: right-click Start > **Terminal** (Windows 11) or open Start and type **cmd**. Commands that change the system need **Run as administrator**. Never paste commands from an unknown website or email.
Tobi can: run safe, read-only checks itself and explain what each command does.

## Find your IP address, computer name and user name
Steps: Settings > Network & internet > your connection > **Properties** shows the IP address. In Command Prompt: `ipconfig` (IP), `hostname` (computer name), `whoami` (user).
Tobi can: show your IP address, gateway, DNS servers, computer name and who is signed in.

## Clear the browser cache
Steps: in Edge or Chrome press **Ctrl + Shift + Delete**, choose a time range, tick **Cached images and files** (and cookies only if asked by IT), select **Clear**.
Tobi can: clear the Teams and browser caches after you approve.

## Check device drivers (Device Manager)
Steps: right-click Start > **Device Manager**. A yellow warning sign means a device has a problem: right-click it > **Update driver**. Do not download drivers from unknown websites.
Tobi can: list the devices Windows reports a problem with.
Call IT when a driver needs administrator rights or the device stays in error.
