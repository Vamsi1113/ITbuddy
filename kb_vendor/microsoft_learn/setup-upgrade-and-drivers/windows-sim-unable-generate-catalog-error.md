<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/windows-sim-unable-generate-catalog-error -->
# Windows SIM was unable to generate a catalog or Parameter count mismatch error

fixes errors that occur when generating a catalog (.clg) in Windows System Image Manager (WSIM).

This article helps fix errors that occur when generating a catalog (.clg) in Windows System Image Manager (WSIM).

Applies to:   Windows 7 Service Pack 1, Windows Server 2012 R2
_Original KB number:_   2524737

## Symptoms

When generating a catalog (.clg) in Windows System Image Manager (WSIM) or clicking Edit Unattend.xml in Microsoft Deployment Toolkit (MDT) and trying to generate a catalog file, it may take extended period of time before producing the error message and you may receive the following error messages:

> Windows SIM was unable to generate a catalog. For troubleshooting assistance, see the topic: 'Windows System Image Manager Technical Reference' in the Windows OPK or Windows AIK User's Guide.
System.InvalidOperationException: The operation failed to complete.

or

> Windows System Image Manager execution failed.
System.Reflection.TargetParameterCountException: Parameter count mismatch.

or

> Performing operation "generate" on Target "Catalog".
The operation failed to complete

## Cause

Windows System Image manager has the following default behavior for generating catalog files:

x86 Windows System Image Manager

Can create catalogs for x86, x64, and Itanium-based Windows images.

x64 Windows System Image Manager

Can create catalogs only for x64 Windows images.

Itanium-based Windows System Image Manager

Can create catalogs only for Itanium-based Windows images

## Resolution

Generate the catalog file on a supported platform. For Microsoft Deployment Toolkit, it's possible to mount the DeploymentShare from another computer with MDT and the AIK installed with the proper architecture to generate the catalog then it can be accessed by the original MDT server.

## More information

This is by design. For more information, see Understanding Windows Image Files and Catalog Files

## Data collection

If you need assistance from Microsoft support, we recommend you collect the information by following the steps mentioned in Gather information by using TSS for deployment-related issues.

_Source: Microsoft Learn, licensed CC BY 4.0._
