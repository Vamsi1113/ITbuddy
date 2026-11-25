<!-- source: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/manage-bde-resume -->
# manage-bde resume

Reference article for the manage-bde resume command, which resumes BitLocker encryption or decryption after it has been paused.

Resumes BitLocker encryption or decryption after it has been paused.

## Syntax

```
manage-bde -resume [<drive>] [-computername <name>] [{-?|/?}] [{-help|-h}]
```

### Parameters

| Parameter | Description |
| --------- | ----------- |
| `<drive>` | Represents a drive letter followed by a colon. |
| -computername | Specifies that manage-bde.exe will be used to modify BitLocker protection on a different computer. You can also use **-cn** as an abbreviated version of this command. |
| `<name>` | Represents the name of the computer on which to modify BitLocker protection. Accepted values include the computer's NetBIOS name and the computer's IP address. |
| -? or /? | Displays brief Help at the command prompt. |
| -help or -h | Displays complete Help at the command prompt. |

### Examples

To resume BitLocker encryption on drive C, type:

```
manage-bde -resume C:
```

## Related links

- Command-Line Syntax Key

- manage-bde on command

- manage-bde off command

- manage-bde pause command

- manage-bde command

_Source: Microsoft Learn, licensed CC BY 4.0._
