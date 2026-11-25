<!-- source: https://learn.microsoft.com/en-us/windows-server/storage/disk-management/overview-of-disk-management -->
# Overview of Disk Management

Learn how to use the Disk Management system utility in Windows to initialize drives, extend volumes, shrink partitions, and change drive letters.

Disk Management is a system utility in Windows for advanced storage operations. You can use the utility to see information about each drive on your computer and all partitions in each drive. The utility shows partition details, including statistics and the amount of space allocated or used.

Some of the tasks you can complete with Disk Management include:

- Set up a new drive on your computer by initializing a new disk
- Extend a basic volume into unclaimed space in a volume on the same drive
- Shrink a basic volume or partition, such as to enable extending into a neighboring partition
- Change a drive letter or assign a new drive letter

## View drives and partitions

The following image shows the Disk Management overview for several drives. **Disk 0** has three partitions, and **Disk 1** has two partitions. On **Disk 0**, the *C:* drive for Windows uses the most disk space. Two other partitions for system operations and recovery use a smaller amount of disk space.

Windows typically includes three partitions on your main drive, which is usually the *C:\\* drive:

| Partition | Purpose |
|-----------|---------|
| **Local&#160;Disk&#160;(C:)** | Stores the Windows operating system installation. Common storage location for other apps and files. |
| **EFI&#160;System**| Supports the start (_boot_) process for the computer and operating system in modern computers. |
| **Recovery** | Stores tools that support Windows recovery operations when the computer doesn't start or in other problem scenarios. For more information, see Recovery options in Windows. |

> Important:
> Disk Management might show the **EFI System** and **Recovery** partitions as 100 percent _free_. However, these partitions store critical files required for the computer to operate properly. As such, the partitions are usually close to full. The recommended practice is to not modify these partitions in any way.

## Prepare resources for tasks

Some Disk Management tasks require special information about your system like a BitLocker recovery key, or an existing resource such as a restore point. The following articles can help you prepare the information and resources you need to complete the tasks:

- Create a recovery drive
- Create a restore point for your system in Windows
- Back up and restore your PC with Windows Backup
- Find your BitLocker recovery key
- Find lost files after you upgrade to Windows

## Use other tools for tasks

The Disk Management utility supports a wide range of drive tasks, but some tasks can be completed only by using another tool.

Here are some common disk management tasks that you need to complete by using other tools in Windows:

- Free up drive space in Windows
- Defragment or optimize your data drives in Windows
- Pool multiple hard drives like a redundant array of independent disks (RAID) with Storage Spaces in Windows

## Troubleshoot issues

When a Disk Management task reports an error, or a procedure doesn't work as expected, try one of the following options to resolve the issue:

- Review suggestions in the Troubleshooting Disk Management article.
- Search the Microsoft Support Community site for posts about files, folders, and storage.
- Ask a question to get input from Microsoft or other community members.
- Contact Microsoft Support about the issue.

## Related content

- Manage disks
- Manage basic volumes

_Source: Microsoft Learn, licensed CC BY 4.0._
