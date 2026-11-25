<!-- source: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/select-partition -->
# select partition

Reference article for the select partition command, which selects the specified partition and shifts the focus to it.

Selects the specified partition and shifts the focus to it. This command can also be used to display the partition that currently has the focus in the selected disk.

## Syntax

```
select partition=<n>
```

### Parameters

| Parameter | Description |
|--|--|
| partition=`<n>` | The number of the partition to receive the focus. You can view the numbers for all partitions on the disk currently selected by using the **list partition** command in DiskPart. |

#### Remarks

- Before you can select a partition you must first select a disk using the **select disk** command.

  - If no partition number is specified, this option displays the partition that currently has the focus in the selected disk.

  - If a volume is selected with a corresponding partition, the partition is automatically selected.

  - If a partition is selected with a corresponding volume, the volume is automatically selected.

## Examples

To shift the focus to *partition 3*, type:

```
select partitition=3
```

To display the partition that currently has the focus in the selected disk, type:

```
select partition
```

## Related links

- Command-Line Syntax Key

- create partition efi command

- create partition extended command

- create partition logical command

- create partition msr command

- create partition primary command

- delete partition command

- detail partition command

- select disk command

- select vdisk command

- select volume command

_Source: Microsoft Learn, licensed CC BY 4.0._
