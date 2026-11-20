<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/no-longer-working-error-library-windows-explorer -->
# Opening a Library in Windows Explorer gives error that it is no longer working

This article provides some steps for fixing the error which shows it is no longer working when opening a Library in Windows Explorer.

This article provides a solution for fixing the error that shows it is no longer working when opening a Library in Windows Explorer.

Applies to:   Windows 10 - all editions
_Original KB number:_   2895090

## Symptoms

Consider the following scenario:

- You have a PC running Windows 7 or Windows 8.
- In Windows Explorer, you try to open a Library such as Documents, Music, Pictures or Videos.

In this scenario, when trying to open a library, you may encounter an error stating that it is no longer working. For example, accessing the Documents folder would cause the following error to appear:

> Documents.library-ms is no longer working.
This library can be safely deleted from your computer. Folders that have been included will not be affected.

## Cause

The link to the library has become corrupt.

## Resolution

To resolve this issue, follow the steps below.

> Note:
> Following these steps to delete and recreate the libraries will not affect any of the data in your libraries.

1. Open Windows Explorer.
2. On the left-hand pane, find **Libraries** and select it. If you do not see **Libraries** listed, click **View** on the menu at the top of the screen. Then click on the **Navigation pane** drop down and make sure that **Show libraries** has a check next to it.
3. Highlight all of the libraries (Documents, Pictures, Music, and Videos), right-click and choose **Delete**.
4. On the left-hand pane, select **Libraries**, right-click and choose **Restore default libraries**.

The libraries are then recreated and all of your data in the library folders should now be accessible again through the Windows Explorer Libraries.

_Source: Microsoft Learn, licensed CC BY 4.0._
