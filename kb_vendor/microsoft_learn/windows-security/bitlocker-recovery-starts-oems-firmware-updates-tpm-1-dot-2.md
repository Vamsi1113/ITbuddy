<!-- source: https://learn.microsoft.com/en-us/troubleshoot/windows-client/windows-security/bitlocker-recovery-starts-oems-firmware-updates-tpm-1-dot-2 -->
# BitLocker Recovery starts when OEMs perform firmware updates for TPM 1.2

Provides a workaround for the issue where BitLocker Recovery starts when OEMs perform firmware updates for TPM 1.2.

This article provides a workaround for the issue where BitLocker Recovery starts when OEMs perform firmware updates for TPM 1.2.

Applies to:   Windows 10 - all editions
_Original KB number:_   3184518

## Symptoms

For Trusted Platform Module (TPM) 1.2, Windows does not know if the system is going through a firmware update. In this situation, the computer reboots into BitLocker Recovery.

`Manage-bde`: protectors)

To suspend protection, run the following command line:

```console
manage-bde -protectors -disable c:
```

To resume protection, run the following command line:

```console
manage-bde -protectors -enable c:
```

## Workaround

For IT managers who are performing firmware updates for TPM 1.2 through Windows Update, make sure that you suspend BitLocker before you run the updates. This prevents BitLocker Recovery from starting.

## More Information

Use TPM 2.0, as PCR 7 performs all these measurements automatically.

_Source: Microsoft Learn, licensed CC BY 4.0._
