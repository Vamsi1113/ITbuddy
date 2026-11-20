<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/installing-updates-features-roles/processor-not-supported-together-with-windows-version -->
# The processor is not supported together with the Windows version error

Discusses issues in which you receive the processor is not supported together with the Windows version that you are currently using error or the 80240037 error code when you scan or download Windows updates.

This article discusses the errors "Processor not supported" and "80240037" encountered during Windows Update.

_Original KB number:_ 4012982

## Symptoms

When you try to scan or download updates through Windows Update, you receive the following error message:
> Unsupported hardware
> Your PC uses a processor that is designed for the latest version of Windows. Because the processor is not supported together with the Windows version that you are currently using, your system will miss important security updates.

Additionally, you may see the following error message in the Windows Update window:
> Windows could not search for new updates
An error occurred while checking for new updates for your computer.
Error(s) found:
Code 80240037 Windows Update encountered an unknown error.

## Solution

Since these errors occur when Windows detects an incompatible processor, ensure that Windows is compatible with the processor you're using. Refer to the following documentation for the latest processor generations and models that are supported in different Windows editions:

- For supported Windows Client Processors

- For supported Windows Server Processors

- For supported Windows IoT Core Processors

## Additional resources

- Windows Processor Requirements
- Windows Server support and installation instructions for the AMD EPYC 7000 Series server processors
- Lifecycle support policy FAQ -Windows products

## Data collection

If you need assistance from Microsoft support, we recommend you collect the information by following the steps mentioned in Gather information by using TSS for deployment-related issues.

_Source: Microsoft Learn, licensed CC BY 4.0._
