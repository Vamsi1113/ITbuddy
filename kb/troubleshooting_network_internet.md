# Troubleshooting internet, Wi-Fi and VPN

## How to tell where an internet problem is
Work from the inside out. First your computer (Wi-Fi switched on, airplane mode off, connected to a network), then your local network (router or access point), then the internet itself (DNS and websites). Ask one question at a time: can I open the router's page, can I reach a public address such as 1.1.1.1, can I open a website by name? A failure at one step tells you which layer to fix.
Tobi can: check the network adapter and IP settings, test whether the internet and website names work, read the Wi-Fi signal, and flush the name cache after you approve.

## Connected to Wi-Fi but "No internet"
What it usually means: the computer has joined the network, but the router has no internet, or DNS is failing, or the network needs a sign-in page (captive portal).
Try this: open a plain website such as example.com in a browser to trigger a sign-in page, restart the router if it is yours, forget and rejoin the network, and try another device on the same Wi-Fi. If every device fails, the internet connection itself is down.
Tobi can: test the router, the public internet and website names separately and report which fails.
Call IT when only your computer fails on a network where others work.

## Websites will not open but apps like Teams still work
What it usually means: DNS (the website-name lookup) is failing or cached incorrectly, a browser proxy or extension is blocking, or the clock is wrong.
Try this: flush the DNS cache, try another browser, open the site in a private window, and check the date and time.
Tobi can: flush the DNS cache after you approve and re-test website names.
Call IT when names fail for everyone on the network.

## Cannot see any Wi-Fi networks or the Wi-Fi option is missing
What it usually means: airplane mode is on, Wi-Fi is switched off, the adapter is disabled or has a driver problem.
Try this: turn airplane mode off, use the laptop's Wi-Fi key, open Settings > Network & internet and switch Wi-Fi on, and restart the computer.
Tobi can: open the Wi-Fi settings page for you and check whether the adapter is reported as having a problem.
Call IT when the Wi-Fi adapter does not appear at all: it may need a driver or repair.

## Wi-Fi keeps disconnecting
What it usually means: weak signal, interference, power saving turning the adapter off, or roaming between access points.
Try this: move closer to the router, forget and rejoin the network, restart the router, and on a laptop plug in power. Choose the 5 GHz network for speed or the 2.4 GHz network for range.
Tobi can: read the current Wi-Fi signal strength and network name.
Call IT when it drops at the same place in the office every day.

## Internet is very slow
What it usually means: weak Wi-Fi signal, many people or devices, a big download or cloud backup running, a VPN adding delay, or a computer with high CPU, memory or disk use.
Try this: test on another device, move closer to the router, pause large uploads and downloads, close extra browser tabs, and disconnect the VPN for a test if policy allows.
Tobi can: check the connection and the computer's own load, and name the program using the most memory.
Call IT when slowness is constant for many people.

## "Your connection is not private" or certificate warnings
What it usually means: the computer's date or time is wrong, a public Wi-Fi sign-in page is intercepting, or the website's certificate is expired or untrusted. On a company network a proxy may use a company certificate.
Try this: correct the date and time, reload, and never click through a warning on a sign-in or banking page.
Tobi can: check the clock and test the website's certificate.
Call IT when a warning appears on many sites at once on the company network.

## VPN will not connect or keeps disconnecting
What it usually means: no working internet underneath, an expired password or MFA prompt not approved, a blocked network, or an outdated VPN client.
Try this: confirm normal internet first, approve the MFA prompt on your phone, try another network such as a phone hotspot, and restart the VPN app.
Tobi can: check the internet connection and open the VPN settings page.
Call IT when the VPN reports a specific error code, giving them the code.

## Cannot reach internal sites or file shares
What it usually means: you are not on the office network or VPN, or the internal name cannot be resolved.
Try this: connect the VPN, then open the address again. Mapped drives often need the VPN first.
Tobi can: test whether an internal address answers.
Call IT when the VPN is connected but the internal site is still unreachable.

## Wired network or docking station not working
What it usually means: a loose cable, a dock with a stale driver, a switch port that is off, or the wrong network profile.
Try this: reseat the cable, try another port or the cable directly, restart the dock by unplugging its power, and restart the computer.
Tobi can: check whether the wired adapter is up and has an address.
Call IT when the cable works on another computer but not on yours.

## "Limited connectivity" or an address starting with 169.254
What it usually means: the computer could not get an address from the router (DHCP).
Try this: disconnect and reconnect, restart the router, and try another network.
Tobi can: read your IP settings and flag the 169.254 address.
Call IT when it happens on the company network, because the address server may be down.

## Hotel, cafe or guest Wi-Fi needs a sign-in page
What it usually means: a captive portal controls access.
Try this: open a plain http page such as http://neverssl.com in a browser to bring up the sign-in page, accept the terms and then use the VPN.
Tobi can: confirm that the internet test fails only until you sign in.

## A proxy or firewall blocks the website
What it usually means: a proxy setting, an extension or a company filter blocks the address.
Try this: check Settings > Network & internet > Proxy, try a private window without extensions, and note the exact message.
Tobi can: open the proxy settings page and test the address.
Call IT when the message says the site is blocked by policy.
