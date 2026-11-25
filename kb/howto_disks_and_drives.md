# How to: disks, drives and partitions

## Split the C drive to make a new D drive (create a partition)
What it is: you take free space from C: (shrink it) and turn that space into a new drive such as D:. Your files on C: stay where they are.
Before you start: back up important files. On a work laptop this needs administrator rights and the drive is usually encrypted with BitLocker, so ask IT first if you are not an administrator.
Steps:
1. Right-click the Start button and choose **Disk Management**.
2. Right-click the **C:** drive and choose **Shrink Volume**. Wait while Windows checks how much it can free.
3. In "Enter the amount of space to shrink in MB" type the size of the new drive in MB: 1 GB = 1024 MB, so **40 GB = 40960 MB**, 50 GB = 51200 MB, 100 GB = 102400 MB. Select **Shrink**.
4. A black bar called **Unallocated** appears. Right-click it and choose **New Simple Volume**, then **Next**.
5. Keep the full size, pick the drive letter **D** (if D is taken by a DVD or card reader, pick another letter), choose **NTFS**, give it a name such as "Data", tick **Perform a quick format**, then **Finish**.
6. The new drive appears in File Explorer under This PC.
On Windows 11 you can also do it in Settings > System > Storage > Advanced storage settings > **Disks & volumes**: select C:, **Properties** > **Change size**, then create a new volume in the unallocated space.
If Windows offers less space than you asked for: some system files cannot be moved, so C: cannot shrink further. Free up space first or ask IT.
Tobi can: check how much free space each drive has and open the Disks & volumes settings. It cannot change partitions itself: that needs administrator rights.
Call IT when you are not an administrator, the drive is BitLocker-encrypted and you do not have the recovery key, or Shrink Volume is greyed out.

## Make a drive bigger (extend a volume)
What it is: you add unallocated space that sits right after a drive to that drive.
Steps: open **Disk Management** (right-click Start), right-click the drive, choose **Extend Volume**, keep the suggested size and select **Finish**.
Good to know: Extend Volume only works when the unallocated space is directly to the right of the drive. If a recovery partition sits in between, the option is greyed out: ask IT. Deleting a partition to make room erases everything on it.
Call IT when you need administrator rights or the option is greyed out.

## Delete a partition or merge D back into C
Steps: back up everything on D: first. In **Disk Management** right-click D: > **Delete Volume** (this erases all its files), then right-click C: > **Extend Volume** to add the freed space.
Call IT when C: cannot be extended because another partition sits between them.

## Change a drive letter
Steps: open **Disk Management**, right-click the drive > **Change Drive Letter and Paths** > **Change**, pick a free letter, select **OK**.
Good to know: do not change the letter of C:. Programs installed on a drive may stop working if its letter changes.

## Check how much space is free on each drive
Steps: open File Explorer and select **This PC**: each drive shows a bar with the free space. For details, open Settings > System > **Storage**.
Tobi can: show the free space on every drive and the size of your main folders right now.

## Format a USB stick or external drive
Steps: copy off anything you need first, because formatting erases the drive. In File Explorer right-click the drive under This PC > **Format**. Choose **exFAT** to use it on Windows and Mac, or **NTFS** for Windows only, tick **Quick Format**, select **Start**.
Good to know: company policy may block or encrypt USB drives (see the USB policy). Never format C:.

## A new or second disk does not show in File Explorer
What it usually means: a brand-new disk must be initialised and given a volume before Windows shows it.
Steps: open **Disk Management**. If asked to initialise, choose **GPT** and **OK**. Right-click the **Unallocated** space > **New Simple Volume** and follow the steps.
Call IT when the disk is not listed at all in Disk Management or shows as "Offline" with an error.

## Check a drive for errors (chkdsk)
Steps: in File Explorer right-click the drive > **Properties** > **Tools** > **Check** > **Scan drive**. Windows fixes what it can; for C: it may ask to restart.
Advanced: in an administrator Command Prompt, `chkdsk C: /f` checks and fixes C: at the next restart.
Call IT when it reports bad sectors or the drive makes clicking noises: back up at once, the drive may be failing.

## Optimise (defragment) a drive
Steps: open Start, type **Defragment and Optimize Drives**, select the drive, select **Optimize**. Windows does this automatically every week. SSDs are trimmed, not defragmented, which is normal.

## Safely remove (eject) a USB drive
Steps: close files that are open from the drive, then select the USB icon near the clock > **Eject**, or right-click the drive in File Explorer > **Eject**. Unplug it when Windows says it is safe.

## Is my drive encrypted with BitLocker? Where is the recovery key?
Steps: open Start, type **Manage BitLocker** (or Control Panel > BitLocker Drive Encryption): it shows "BitLocker on" or "off" for each drive.
The recovery key for a work device is usually stored in your work account: sign in at https://aka.ms/myrecoverykey, or ask IT. Never share the key in chat or email.
Call IT when the computer asks for a BitLocker recovery key at startup and you cannot find it.

## Map a network drive (give a shared folder a drive letter)
Steps: open File Explorer > **This PC** > **Map network drive** (in the toolbar, or under the ... menu on Windows 11). Pick a letter, type the folder path such as `\\server\share`, tick **Reconnect at sign-in**, select **Finish**. Connect the VPN first when you work from home.
Tobi can: test whether the file server answers.
