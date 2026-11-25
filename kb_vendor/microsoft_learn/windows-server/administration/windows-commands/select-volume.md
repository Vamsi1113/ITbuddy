<!-- source: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/select-volume -->
# select volume

Reference article for the select volume command, which selects the specified volume and shifts the focus to it.

Selects the specified volume and shifts the focus to it. This command can also be used to display the volume that currently has the focus in the selected disk.

## Syntax

```
select volume={<n>|<d>}
```

### Parameters

| Parameter | Description |
|--|--|
| `<n>` | The number of the volume to receive the focus. You can view the numbers for all volumes on the disk currently selected by using the **list volume** command in DiskPart. |
| `<d> `| The drive letter or mount point path of the volume to receive the focus. |

## Remarks

- If no volume is specified, this command displays the volume that currently has the focus in the selected disk.

- On a basic disk, selecting a volume also gives the focus to the corresponding partition.

  - If a volume is selected with a corresponding partition, the partition will be automatically selected.

  - If a partition is selected with a corresponding volume, the volume will be automatically selected.

## Examples

To shift the focus to *volume 2*, type:

```
select volume=2
```

To shift the focus to *Drive C*, type:

```
select volume=c
```

To shift the focus to the volume mounted on a folder named *c:\mountpath*, type:

```
select volume=c:\mountpath
```

To display the volume that currently has the focus in the selected disk, type:

```
select volume
```

## Related links

- Command-Line Syntax Key

- add volume command

- attributes volume command

- create volume mirror command

- create volume raid command

- create volume simple command

- create volume stripe command

- delete volume command

- detail volume command

- fsutil volume command

- list volume command

- offline volume command

- onine volume command

- select disk command

- select partition command

- select vdisk command

_Source: Microsoft Learn, licensed CC BY 4.0._
