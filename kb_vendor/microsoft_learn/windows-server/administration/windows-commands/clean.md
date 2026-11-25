<!-- source: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/clean -->
# clean

Reference article for the Diskpart clean command, which removes all partitions or volume formatting from the disk with focus.

Removes all partitions or volume formatting from the disk with focus.

> Note:
> For a PowerShell version of this command, see clear-disk command.

## Syntax

```
clean [all]
```

### Parameters

| Parameter | Description |
| --------- | ----------- |
| all | Specifies that each and every sector on the disk is set to zero, which completely deletes all data contained on the disk. |

#### Remarks

- On master boot record (MBR) disks, only the MBR partitioning information and hidden sector information is overwritten.

- On GUID Partition Table (gpt) disks, the gpt partitioning information, including the Protective MBR, is overwritten. There is no hidden sector information.

- A disk must be selected for this operation to succeed. Use the **select disk** command to select a disk and shift the focus to it.

## Examples

To remove all formatting from the selected disk, type:

```
clean
```

## Related links

- clear-disk command

- Command-Line Syntax Key

_Source: Microsoft Learn, licensed CC BY 4.0._
