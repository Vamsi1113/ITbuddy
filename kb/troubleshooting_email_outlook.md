# Troubleshooting email and Outlook

## Outlook will not open or is stuck on "Loading profile" or "Processing"
What it usually means: a damaged profile or add-in, a very large data file, or a pending Windows or Office update. Outlook may also be waiting on a network connection.
Try this: wait two minutes, then close Outlook completely (check the Task Manager for a hidden Outlook process), start it in safe mode by holding Ctrl while opening it, and restart the computer. Disable add-ins one by one under File > Options > Add-ins.
Tobi can: check whether Outlook is running or crashing, show recent Outlook crashes from the event log, and close a frozen Outlook after you approve.
Call IT when a new profile is needed or the data file is damaged.

## Outlook keeps asking for my password
What it usually means: the saved sign-in expired, your password changed, MFA was not completed, or the clock is wrong.
Try this: sign in once when prompted and approve the MFA request, check the date and time, sign out of Office accounts under File > Office Account and sign in again, and restart Outlook.
Tobi can: check how many days until your password expires and check the clock.
Call IT when the prompt returns after a fresh sign-in: the account may be blocked or the credential store needs clearing.

## Email is not sending or receiving
What it usually means: you are offline, the mailbox is full, a large attachment blocks the outbox, or the sign-in expired.
Try this: look for "Working Offline" in the Send/Receive tab and turn it off, empty the Outbox of a stuck message, remove very large attachments and share a link instead, and check that other apps have internet.
Tobi can: test the internet connection and show recent Outlook errors.
Call IT when sending fails for everyone or shows a server error code.

## Error 0x800CCC0E, 0x800CCC0D or "cannot connect to the server"
What it usually means: Outlook cannot reach the mail server: no internet, a wrong account setting, or a firewall blocks the connection. 0x800CCC0E is a connection failure and 0x800CCC0D means the server name could not be found.
Try this: check the internet, open Outlook on the web to see whether the mailbox itself works, and restart Outlook.
Tobi can: look up the error code and test the connection.
Call IT when the mailbox opens on the web but not in the Outlook app.

## Mailbox is full or "storage limit reached"
What it usually means: the mailbox reached its size limit.
Try this: empty Deleted Items and Junk Email, sort the mailbox by size to find large messages, save big attachments to a shared folder, and archive old mail.
Call IT when you need a bigger limit for work reasons.

## Emails are missing or search finds nothing
What it usually means: the message is in another folder or the Junk folder, a rule moved it, filters hide it, or the search index is rebuilding.
Try this: search all folders, check Junk Email and Deleted Items, check Rules under Home > Rules, and look at Outlook on the web to compare.
Call IT when the same search fails on Outlook on the web.

## Calendar invites or meetings are not syncing
What it usually means: the calendar is not refreshed, the account is offline, or the meeting is in a shared calendar.
Try this: press Send/Receive, check that the right calendar is ticked, and open the invite on Outlook on the web.
Tobi can: test the connection and look for recent errors.

## Cannot open a shared mailbox or shared calendar
What it usually means: you do not have permission yet, the mailbox has not synced to your profile, or it needs to be added again.
Try this: wait up to an hour after permission was granted, then restart Outlook. Add the mailbox again with File > Account Settings.
Call IT or raise a request: access is given by the mailbox owner or IT, and Tobi can raise the ticket for you.

## Suspicious email or you clicked a link
What it usually means: it may be phishing.
Try this: do not click or open attachments, use the Report button in Outlook, and if you entered your password, tell IT at once so sessions can be signed out.
Tobi can: check a link without opening it and check the antivirus status, and raise a priority ticket for you.
