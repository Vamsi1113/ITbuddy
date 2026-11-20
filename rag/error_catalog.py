"""Baseline error-code catalogue indexed alongside the KB. Extend or replace with your own list."""

SAMPLE_ERROR_CODES = [
    {
        "code": "0x80070005",
        "description": "Access is denied. The process does not have permission for the requested operation.",
        "causes": "Missing permissions, UAC restriction, file locked by another process.",
        "fixes": "Run as administrator, check file permissions, check if file is in use.",
        "app": "",
        "os": "windows",
    },
    {
        "code": "0x800CCC0E",
        "description": "Outlook cannot connect to your email server.",
        "causes": "SMTP/IMAP server not reachable, wrong port, firewall blocking.",
        "fixes": "Check server address and port in Outlook settings. Try port 587 for SMTP. Check firewall.",
        "app": "outlook",
        "os": "windows",
    },
    {
        "code": "NET::ERR_CERT_AUTHORITY_INVALID",
        "description": "Browser reports an untrusted certificate authority.",
        "causes": "Self-signed cert, expired cert, wrong system clock, proxy/MITM.",
        "fixes": "Check the system clock is correct. Contact the website owner. If on corporate proxy, install the proxy certificate.",
        "app": "",
        "os": "any",
    },
    {
        "code": "0x80004005",
        "description": "Unspecified error. Often occurs with network drive mapping or Windows Update.",
        "causes": "Permissions, network path unavailable, corrupted update cache.",
        "fixes": "Check network path is reachable, run Windows Update troubleshooter, re-enter network credentials.",
        "app": "",
        "os": "windows",
    },
    {
        "code": "DRIVER_IRQL_NOT_LESS_OR_EQUAL",
        "description": "Blue screen stop error caused by a driver accessing memory at an inappropriate IRQL.",
        "causes": "Faulty or incompatible device driver, usually network or storage driver.",
        "fixes": "Boot in safe mode, roll back recently updated drivers, run memory diagnostics.",
        "app": "",
        "os": "windows",
    },
]
