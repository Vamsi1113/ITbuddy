<!-- source: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/convert -->
# convert

Reference article for the convert command, which converts a disk from one disk type to another.

Converts a disk from one disk type to another.

## Syntax

```
convert basic
convert dynamic
convert gpt
convert mbr
```

### Parameters

| Parameter | Description |
| --------- | ----------- |
| convert basic command | Converts an empty dynamic disk into a basic disk. |
| convert dynamic command | Converts a basic disk into a dynamic disk. |
| convert gpt command | Converts an empty basic disk with the master boot record (MBR) partition style into a basic disk with the GUID partition table (GPT) partition style. |
| convert mbr command | Converts an empty basic disk with the GUID Partition Table (GPT) partition style into a basic disk with the master boot record (MBR) partition style. |

## Related links

- Command-Line Syntax Key

_Source: Microsoft Learn, licensed CC BY 4.0._
