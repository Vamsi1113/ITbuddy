<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/error-when-burning-files-to-disc -->
# Error when burning files to disc

Provides a resolution to an error that occurs when burning files to disc

This article provides a resolution to an error that occurs when burning files to disc.

Applies to:   Windows 8
_Original KB number:_   2748977

## Symptoms

Consider the following scenario:

1. You have a Windows 8 computer with an optical disc drive that supports writing.
2. You insert a blank disc into the writer and select **Tap to choose what happens with blank DVDs**.
3. You select **Burn files to disc**.
4. The **Burn a Disc** window will appear.
5. You choose the **With a CD/DVD player** option.
6. You click the **Next** button to open up an **Explorer** window.
7. You drag a large file to the Explorer window that appeared in step 6.
8. While the copy is still active, you right click on the blank disc in the left hand pane of Explorer and select **Burn to disc** from the context menu.

After you do this, you receive the following error message:

## Cause

This error occurs because the first copy session is still in progress. If you select **Burn to disc** again, Windows will attempt to burn files to the same drive again in a different session. This is not a supported scenario.

## Resolution

Wait for the file copy to finish before starting **Burn to disc**.

_Source: Microsoft Learn, licensed CC BY 4.0._
