<!-- source: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/mkdir -->
# mkdir

Reference article for the mkdir command, which creates a directory or subdirectory.

Creates a directory or subdirectory. Command extensions, which are enabled by default, allow you to use a single **mkdir** command to create intermediate directories in a specified path.

> Note:
> This command is the same as the md command.

## Syntax

```
mkdir [<drive>:]<path>
```

### Parameters

| Parameter | Description |
| --------- | ----------- |
| `<drive>`: | Specifies the drive on which you want to create the new directory. |
| `<path>` | Specifies the name and location of the new directory. The maximum length of any single path is determined by the file system. This is a required parameter. |
| /? | Displays help at the command prompt. |

### Examples

To create a directory named *Directory1* within the current directory, type:

```
mkdir Directory1
```

To create the directory tree *Taxes\Property\Current* within the root directory, with command extensions enabled, type:

```
mkdir \Taxes\Property\Current
```

To create the directory tree *Taxes\Property\Current* within the root directory as in the previous example, but with command extensions disabled, type the following sequence of commands:

```
mkdir \Taxes
mkdir \Taxes\Property
mkdir \Taxes\Property\Current
```

## Related links

- Command-Line Syntax Key

- md command

_Source: Microsoft Learn, licensed CC BY 4.0._
