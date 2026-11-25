# How to: files, folders, backup and sharing

## Show file extensions (.docx, .pdf) and hidden files
Steps: in File Explorer, Windows 11: **View** > **Show** > tick **File name extensions** and **Hidden items**. Windows 10: the **View** tab > tick the same boxes.
Tobi can: switch file extensions or hidden files on after you approve.

## Zip (compress) or unzip files
Steps: select the files, right-click > **Compress to ZIP file** (Windows 11) or **Send to** > **Compressed (zipped) folder**. To unzip, right-click the .zip > **Extract All**. Opening a file inside a zip without extracting can make it read-only.
Tobi can: install 7-Zip from the approved software list after you approve.

## Find a file
Steps: open File Explorer, go to the folder or This PC and type in the search box (top right). Search by name, or use `kind:pdf`, `date:this week`, `size:>100MB`. Recent files are in **Home** / Quick access.
Tobi can: find one of your files by name in your usual folders and other drives, and open it.

## Restore a deleted file
Steps: open the **Recycle Bin**, right-click the file > **Restore**. OneDrive files: open OneDrive in the browser > **Recycle bin**. Shared drives: right-click the folder > **Properties** > **Previous Versions** if IT has turned it on.
Tobi can: show how much is in the Recycle Bin. It never empties it without your approval.

## Get an older version of a file back
Steps: OneDrive or SharePoint: right-click the file > **Version history**. Local files with File History on: right-click > **Properties** > **Previous Versions**. Office files: File > Info > **Version history** or **Manage Document**.

## Back up your files
Steps: the simplest backup on a work PC is OneDrive: Settings in the OneDrive icon > **Sync and backup** > **Manage backup** to back up Desktop, Documents and Pictures. External drive: Control Panel > **File History** > choose the drive > **Turn on**.
Good to know: files saved only on C: and not in OneDrive are not backed up by IT.

## Share a file with a colleague
Steps: put the file in OneDrive or a Teams / SharePoint folder, right-click > **Share**, type the person's name, choose **Can view** or **Can edit**, select **Send**. Sharing a link is better than emailing attachments: everyone works on one copy.
Good to know: follow the data classification rules before sharing outside the company.

## Free up space with OneDrive (files on demand)
Steps: right-click a OneDrive folder > **Free up space**: the files stay visible (cloud icon) and download when you open them. **Always keep on this device** keeps a copy offline.

## Open a file with a different app every time
Steps: right-click the file > **Open with** > **Choose another app** > pick the app > tick **Always use this app**.
Tobi can: open a file for you in its usual app.

## Save or print a document as PDF
Steps: in the app choose **File** > **Print**, choose the printer **Microsoft Print to PDF**, select **Print**, pick a folder and name. Office apps can also **Save As** > PDF.
Tobi can: turn a document, text file or picture into a PDF and save it where you want.

## Copy many or very large files reliably
Steps: for normal amounts use copy and paste in File Explorer. For thousands of files or a slow network, `robocopy "source folder" "target folder" /E` in Command Prompt copies everything with sub-folders and can resume after a break (add `/Z`).
Call IT when you are moving company data to a personal drive: this is usually not allowed.

## Rename many files at once
Steps: select the files, press **F2**, type a name and press Enter: Windows numbers them, for example Report (1), Report (2).

## Create a new folder or a shortcut on the desktop
Steps: right-click an empty spot > **New** > **Folder** (or Ctrl + Shift + N in File Explorer). Shortcut: right-click a file or app > **Show more options** > **Send to** > **Desktop (create shortcut)**.

## Make a file read-only or remove read-only
Steps: right-click the file > **Properties** > tick or untick **Read-only** > **OK**. A file attached from email or downloaded may open in Protected View: select **Enable Editing**.
