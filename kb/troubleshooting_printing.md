# Troubleshooting printing

## How Tobi troubleshoots a printing problem
Printing problems live in one of four places, and Tobi checks all four in one pass: your computer (print service, printer list, default printer, stuck jobs, driver, recent print errors), the file you want to print (missing, empty, locked, damaged, password-protected), the printer itself (offline, out of paper or ink, jam, open cover, needs service) and the connection between them (network address answers, or USB cable).
Problems on your computer are fixed by Tobi after you approve: clear a stuck print queue, set the right default printer, bring a printer back online, restart the print service when you have administrator rights, and send a test page to confirm.
Problems outside your computer (paper, toner, jam, power, cable, network, a broken file) cannot be fixed by software, so Tobi gives you the exact steps to do. Problems that need administrator rights, such as a missing driver or a stopped print service on a standard account, are passed to IT with a ticket.
Say "my printer is not printing" or "why will report.pdf not print" and give the file name if you know it.

## Printer shows offline or "Printer offline"
What it usually means: Windows cannot reach the printer, or the printer is switched off, asleep, out of paper, or has an error on its screen. Sometimes Windows itself has the setting "Use Printer Offline" ticked.
Try this: check the printer is on and its screen shows no error, press any button to wake it, and make sure it is on the same Wi-Fi or network cable as your computer. Open Settings > Bluetooth & devices > Printers & scanners > your printer > Open print queue, and in the Printer menu make sure "Use Printer Offline" is not ticked.
Tobi can: check whether the printer's network address answers, clear the "Use Printer Offline" setting, and clear stuck jobs that keep it marked offline.
Call IT when the printer is reachable on the network but Windows still says offline after a restart of the printer and computer, or the printer's IP address changed.

## Print job stuck in the queue and will not print or delete
What it usually means: one damaged or failed job blocks everything behind it. The printer may have lost power halfway through a job, or a job was sent to an offline printer.
Try this: open the print queue (Settings > Printers & scanners > your printer > Open print queue), choose Printer > Cancel All Documents, wait a minute, and print again. If the job stays in "Deleting", the print service needs a restart, which needs administrator rights.
Tobi can: cancel all waiting jobs of a printer after you approve, restart the print service when you are an administrator, and check afterwards that the queue is empty.
Call IT when jobs keep getting stuck, or the queue cannot be cleared because you are not an administrator.

## Nothing happens when I click Print
What it usually means: the program is sending to the wrong printer (often Microsoft Print to PDF as the default), the print service is stopped, or the document is still being prepared.
Try this: in the Print window, choose your real printer from the list instead of the default, and check that "Print to file" is not ticked. Wait a few seconds for a large document, then check the print queue for a waiting job.
Tobi can: see which printer is the default, switch the default to your real printer, and check the print service is running.
Call IT when your printer is missing from the list: it may need to be added from the company print server.

## No printer in the list or "no printers found"
What it usually means: the printer was never added on this computer, was removed by an update, or you are not connected to the network it lives on.
Try this: connect to the office network or the VPN, then open Settings > Bluetooth & devices > Printers & scanners > Add device, wait for the printer to appear and pick it. For an office printer ask IT for its name, such as \\printserver\floor2.
Tobi can: confirm that no physical printer is installed and open the Printers & scanners page for you.
Call IT when the printer does not appear even on the right network, or needs a driver you cannot install.

## Printer prints blank pages
What it usually means: the cartridge is empty or the protective tape was not removed from a new one, the print head is clogged, the wrong paper side is up, or the document itself is blank (a damaged file or white text).
Try this: print the printer's own test or status page from its menu. If that is blank too, the printer needs a cartridge or head-cleaning. If only one document is blank, open it in its program and check it shows text, then print it to PDF and print the PDF.
Tobi can: check the file for being empty or damaged and send a test page from Windows.
Call the printer supplier or IT when the printer's own test page is blank after replacing the cartridge.

## Faint, streaky or smudged printing
What it usually means: low toner or ink, a dirty or clogged print head or roller, the wrong paper type setting, or damp paper.
Try this: run the printer's cleaning or head-alignment routine from its menu, replace a low cartridge, use the paper type that matches the tray, and use dry, flat paper. For laser printers, gently rocking the toner cartridge can restore a little life before replacing it.
Tobi can: report the toner or ink warning the printer sends to Windows.
Call IT or the supplier when cleaning and a new cartridge do not help.

## Paper jam, paper out, or paper tray errors
What it usually means: the printer reports a physical problem. Software cannot clear it.
Try this: switch the printer off, open every cover and the rear panel, pull jammed paper out slowly in the direction the paper travels without tearing it, check for torn pieces, close everything and switch on. For "out of paper" with paper loaded, fan the stack, load it flat under the guides, and make sure the paper size in the tray matches the print job.
Tobi can: read the printer's reported state (out of paper, jam, door open, output tray full) and tell you which step applies.
Call IT or the supplier when the jam message stays after you have removed all paper.

## Network printer cannot be reached
What it usually means: the printer is off, asleep, on a different network, or its IP address changed so the computer is talking to an address nobody answers on.
Try this: check the printer is on and shows no error, that you are on the same Wi-Fi or cable, and on the VPN or office network when away. Print the printer's network page from its menu and compare its IP address with the one Windows uses. Restart the printer and wait two minutes.
Tobi can: test whether the printer's address answers on the printing port, and show the address Windows is using.
Call IT when the printer's IP address changed, because the printer port must be updated, usually with administrator rights.

## USB printer is not detected
What it usually means: a loose or faulty cable, a dead USB port or hub, a printer that is off, or a missing driver.
Try this: plug the cable straight into the computer, not a hub or dock, try another port and another cable, switch the printer off and on, and check Settings > Printers & scanners for the printer. Restarting the computer helps after driver changes.
Tobi can: list devices that Windows reports a problem with and see whether the printer is marked offline.
Call IT when the printer needs a driver that requires administrator rights.

## Printer works for others but not for me
What it usually means: the problem is on your computer: wrong default printer, a stuck queue on your side, a missing or broken driver, or a firewall or VPN difference.
Try this: print from another program or a different document to see if it is the file. Cancel all documents in your queue, remove and re-add the printer, and restart the computer.
Tobi can: check your computer's queue, default printer and print service, and fix what is wrong after you approve.
Call IT when removing and re-adding the printer fails or you need a driver.

## Only one file will not print
What it usually means: the file is damaged, locked by another program, password-protected or restricted, very large, or a type that cannot be printed directly.
Try this: open the file and check it looks right, save a copy and print the copy, print it to PDF first and print the PDF, and try a different document. For a PDF that refuses to print, print it as an image from the PDF viewer's Advanced options. Very large files with many images print better after you reduce image quality or print a page range.
Tobi can: check whether the file exists, is empty, is locked, is damaged, is password-protected, or is too large, when you tell it the file name.
Call IT when the same file prints on another computer but not yours.

## Printing is very slow
What it usually means: a very large or image-heavy file, a high quality setting, a busy network, a printer that is warming up or low on memory, or a damaged job making the queue retry.
Try this: print in draft or standard quality, reduce image size, print fewer pages at a time, check the queue for a stuck job, and move closer to or onto the wired network.
Tobi can: look for stuck jobs and clear them.
Call IT when slow printing is constant for everyone on that printer.

## Error 0x0000011b, 0x00000709 or 0x00000bcb when connecting to a shared printer
What it usually means: these errors appear when adding a printer from a print server. 0x0000011b is a Windows security change for printer connections, 0x00000709 is often a default printer or registry permission problem, and 0x00000bcb is a driver or Point and Print restriction.
Try this: restart the computer, remove any half-added copy of the printer, and try again. Do not edit the registry yourself.
Tobi can: explain the error and open a ticket with the error code.
Call IT: these fixes usually need administrator rights, a security setting on the print server or a driver on the server. Give IT the exact error code and the printer name.

## Print Spooler keeps stopping
What it usually means: the Windows print service crashes because of a damaged job, a faulty printer driver, or leftover files in the spool folder.
Try this: cancel all documents, restart the computer, and print a simple document. If the service stops again, a driver is probably at fault.
Tobi can: check whether the print service is running, and restart it if you are an administrator.
Call IT when the service stops repeatedly: IT must clear the spool folder or replace the driver.

## Wrong printer or the default printer keeps changing
What it usually means: Windows can choose "Let Windows manage my default printer", which picks the printer you used last.
Try this: open Settings > Bluetooth & devices > Printers & scanners and turn off "Let Windows manage my default printer", then set your printer as default.
Tobi can: set the correct printer as default after you approve.
Call IT when a policy resets the default printer at every sign-in.

## Wrong paper size, cut-off pages or printing on one side only
What it usually means: the paper size or orientation in the program differs from the printer's tray, margins are too small, or double-sided printing is not turned on or not supported.
Try this: in the Print window open Printer properties or More settings and set the paper size to match the tray, turn on "Fit to page", and choose double-sided if the printer supports it.
Tobi can: confirm the printer is working with a test page, so you know the problem is the setting.
Call IT or the printer maker when a setting is greyed out.

## Printing stopped after a Windows update
What it usually means: an update replaced a driver or tightened a printer security rule.
Try this: restart the printer and the computer, remove and re-add the printer, and use the printer maker's driver instead of the generic one.
Tobi can: check for recent print errors in the event log and for a missing driver.
Call IT when the printer worked yesterday for everyone and fails today.

## New cartridge installed but the printer still says empty
What it usually means: the cartridge is not seated, a protective part is still attached, the cartridge is not compatible, or the printer needs a reset.
Try this: remove and reseat the cartridge until it clicks, remove all tape and covers, use the exact cartridge model, then switch the printer off and on.
Call the supplier or IT when a genuine cartridge is still rejected.
