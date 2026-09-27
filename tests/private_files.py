"""Real platform permission fixtures. Only call with synthetic temporary files."""

import os


def set_private_permissions(path, *, public=False):
    if os.name != "nt":
        path.chmod(0o644 if public else 0o600)
        return
    import ntsecuritycon
    import win32api
    import win32con
    import win32security as security

    token = security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        user = security.GetTokenInformation(token, security.TokenUser)[0]
    finally:
        token.Close()
    acl = security.ACL()
    for sid in (
        user,
        security.ConvertStringSidToSid("S-1-5-18"),
        security.ConvertStringSidToSid("S-1-5-32-544"),
    ):
        acl.AddAccessAllowedAce(security.ACL_REVISION, ntsecuritycon.FILE_ALL_ACCESS, sid)
    if public:
        acl.AddAccessAllowedAce(
            security.ACL_REVISION,
            ntsecuritycon.FILE_GENERIC_READ,
            security.ConvertStringSidToSid("S-1-1-0"),
        )
    security.SetNamedSecurityInfo(
        str(path),
        security.SE_FILE_OBJECT,
        security.DACL_SECURITY_INFORMATION | security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        acl,
        None,
    )
