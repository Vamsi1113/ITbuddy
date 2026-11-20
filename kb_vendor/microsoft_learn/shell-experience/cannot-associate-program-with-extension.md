<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/cannot-associate-program-with-extension -->
# Can't associate a program with an extension

You can't associate a program with an extension in Windows 7 because the program that you're pointing to isn't registered correctly.

This article provides a solution to an issue where you're unable to associate a file extension to an application in Windows 7.

Applies to:   Windows 7 Service Pack 1
_Original KB number:_   2159999

## Symptoms

You may not be able to associate a file extension to an application in Windows 7.

## Cause

This may occur if the program you are attempting to associate with is not registered correctly.

## Resolution

Follow the steps below:

1. Type *regedit* in the Run line or from an elevated CMD prompt.
2. Navigate to `Computer\HKEY_CLASSES_ROOT\Applications` and find your .exe name.
3. Navigate under its name to shell> open> command.
4. Under Default, make sure the application location points to the actual location of the executable.
5. Press OK and then try to reassociate the file type as you normally would.

_Source: Microsoft Learn, licensed CC BY 4.0._
