<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/application-error-explorer-shut-down -->
# Application Error in Explorer.exe When You Shut Down or Restart Windows

Provides a workaround to an application error in Explorer.exe when you shut down or restart Windows.

## Symptoms

You receive the following error message when Windows is shutting down:

> explorer.exe - Application Error
The instruction at \<memory address\> referenced memory at \<memory address\>. The memory could not be "\<read or write\>".
> Click on OK to terminate the program.

> Note:
> The shutdown process continues after the error message is displayed. The error doesn't harm the computer, and it can be safely ignored.

This issue occurs when you right-click the Start tip or press the Windows key+X keyboard shortcut, and then you use the **Shut down or sign out** option to shut down or restart Windows.

## Cause

This error occurs because the **Explorer.exe** process accesses memory that has already been freed during the shutdown process.

## Workaround

To work around this issue, use the Settings charm to shut down or restart Windows.

_Source: Microsoft Learn, licensed CC BY 4.0._
