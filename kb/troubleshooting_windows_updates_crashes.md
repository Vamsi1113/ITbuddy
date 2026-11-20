# Troubleshooting Windows, updates and crashes

## Blue screen (stop code) or sudden restart
What it usually means: Windows stopped to protect itself, usually because of a faulty driver, failing memory or disk, overheating, or a bad update. The stop code on the screen narrows it down.
Common codes: DRIVER_IRQL_NOT_LESS_OR_EQUAL (a driver touched memory it should not, often network or storage), IRQL_NOT_LESS_OR_EQUAL (similar), PAGE_FAULT_IN_NONPAGED_AREA (memory or driver), SYSTEM_SERVICE_EXCEPTION (a driver or program), CRITICAL_PROCESS_DIED (a core process failed, often disk or update), KERNEL_DATA_INPAGE_ERROR (disk or memory), MEMORY_MANAGEMENT (memory), WHEA_UNCORRECTABLE_ERROR (hardware), INACCESSIBLE_BOOT_DEVICE (disk or boot problem after an update).
Try this: note the stop code, restart, install pending Windows updates, and unplug new USB devices. If it repeats, start in safe mode and roll back recent driver updates.
Tobi can: read recent unexpected shutdowns and the crash reasons from the event log, show what was installed recently, and raise a ticket with the code.
Call IT when it happens more than once: IT needs the stop code and time.

## Windows Update is stuck or failed
What it usually means: a download did not finish, there is not enough free disk space, a service is stopped, or a pending restart blocks the install.
Common codes: 0x80070002 (files missing), 0x80070005 (access denied), 0x800F0922 (not enough space or a system component problem), 0x8024402C (cannot reach the update server).
Try this: restart the computer, free at least 10 GB of disk space, run Windows Update again, and check the internet connection.
Tobi can: show the latest installed updates, tell you whether a restart is pending, and check free disk space.
Call IT when the same code returns after a restart: it may need the update troubleshooter or a repair.

## A restart is pending or the computer keeps asking to restart
What it usually means: updates are waiting for a restart.
Try this: save your work and restart, because installing needs it.
Tobi can: check whether a restart is pending.

## A program crashes or closes by itself
What it usually means: a damaged installation, a conflict with an add-in, an old version, or a lack of memory.
Try this: restart the program, install updates, disable add-ins, restart the computer, and as a last step repair or reinstall the program.
Tobi can: list the programs that crashed recently and when, and show the error source.
Call IT when the same program crashes after a repair.

## Start menu, taskbar or search does not respond
What it usually means: Windows Explorer is stuck or a recent update changed something.
Try this: press Ctrl+Shift+Esc, find Windows Explorer in the Task Manager and choose Restart, then restart the computer.
Call IT when it returns after a restart.

## Windows says "low disk space" or apps will not update
What it usually means: the system drive is almost full.
Try this: empty the Recycle Bin, delete old downloads, and use Storage settings to remove temporary files.
Tobi can: check free space and clear approved temporary files, the Recycle Bin and caches after you approve.

## Date and time are wrong
What it usually means: the time zone is wrong, the clock drifted, or the battery for the clock is weak.
Try this: open Settings > Time & language > Date & time, turn on Set time automatically and the time zone, and press Sync now.
Tobi can: check the clock against a time source and open the Date & time settings page.
Call IT when it resets after each restart.

## Computer will not start properly or boots into repair
What it usually means: a failed update, a damaged system file, or a disk problem.
Try this: let the repair finish, restart once, and unplug USB devices. Do not repeatedly force the power off.
Call IT: this needs hands-on repair. Raise a ticket and give the message on the screen.

## Files and programs open in the wrong app
What it usually means: the default app for that type changed.
Try this: open Settings > Apps > Default apps, pick the file type and choose the app.
Tobi can: open the Default apps settings page.

## An app or a feature is missing after an update
What it usually means: an update replaced or removed it, or a policy changed.
Try this: search the Start menu, reinstall from the approved list, and ask IT if a policy changed.
Tobi can: show what was installed or removed recently and the approved software list.

## System file or Windows repair needed
What it usually means: damaged Windows files cause odd behaviour.
Try this: IT can run system file and image repair checks (sfc /scannow and DISM). These need administrator rights.
Call IT: raise a ticket describing the symptoms.
