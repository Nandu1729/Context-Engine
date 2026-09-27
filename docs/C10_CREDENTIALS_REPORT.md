# D094 — Windows credential/configuration boundary (0.9.4)

## Evidence and scope

Owner Windows log `logs_98177901964.zip` binds commit42148a6:14admission checks
PASS4.83s;previous UTF-8 payload regression PASS;portable suite501PASS/1FAIL270.02s.
`test_private_file_boundaries[public]` expects rejection after chmod0644,but the
implementation enforces mode bits only on POSIX. Owner requests the best real-world
option after being offered explicit exclusion versus versioned Windows enforcement.
D094 selects enforcement,not another Windows exclusion or a weakened assertion.

This repair covers `providers.credentials.private_bytes` and all its callers:
explicit Groq/Gemini keys,benchmark live config,and service configuration. It does
not implement ACL enforcement for SQLite memory/deletion/control/provider stores.
Review found the same POSIX-only assumption in
`test_memory.py::test_private_schema_and_journal_boundaries[public]`;that separate
storage-security work remains open and may be the next Windows failure. No claim
that all Windows security or portable-suite failures are repaired.

## Implementation

- Package0.9.4 uses pinned Windows-only `pywin32==311` native API bindings. No other
  dependency versions changed;Linux/macOS do not install the Windows dependency.
- Open existing local fixed-disk files with read/control access,non-inheritable
  handle,read-only sharing,and OPEN_REPARSE_POINT. Reject device/UNC namespaces,
  alternate streams,non-fixed drives,directories and final-component reparse points.
- Check owner and DACL on the opened handle,then read bounded bytes from that same
  handle. No pathname reopen between check/read. Release handles on success/failure.
- Only the effective token user,LocalSystem and built-in Administrators may own
  the file or have nonzero applicable allow ACEs. Inherited grants are checked;
  inherit-only ACEs do not apply to the file. Missing/null DACLs and unknown or
  complex applicable ACE forms fail closed. Deny ACEs do not excuse a broad allow.
  This is a conservative privacy policy,not an emulation of effective Windows access.
- API/import/query/read failures are content-free ContractError;no unchecked
  fallback. The loader never rewrites ACLs or touches real operator credentials.
  Existing POSIX behavior remains unchanged.

Windows chmod changes only the read-only flag,not privacy ACLs ([Python documentation](https://docs.python.org/3.12/library/os.html#os.chmod)).
Handle/security behavior follows [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
[GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo),
and [pywin32 bindings](https://mhammond.github.io/pywin32/win32security__GetSecurityInfo_meth.html).

## Operator implications and limitations

Provision a local credential/config file in a trusted directory using Windows
Security → Advanced:limit owner and applicable allow entries to the running account,
SYSTEM and Administrators. Remove broad Users/Authenticated Users/Everyone grants,
including inherited grants,after reviewing the intended account and directory.
An administrator may provision for a service identity;run the loader under that
identity. Do not try chmod0600 as an ACL substitute. No real ACL changes were made.

The policy trusts parent directories,the current account and local administrators;
it is not encryption,a hostile-parent-filesystem sandbox,protection against a
trusted owner changing ACLs concurrently,or service-wide Windows storage hardening.
Concurrent data writers/deleters conflict with the open sharing mode. Complex ACLs
may be conservatively rejected even when an effective-access calculation is private.
Network/removable/device/extended-namespace credential paths are deliberately unsupported.

## Preservation and verification

Actual0.9.3 wheel and development freeze preserved in
`archives/c10-credentials-094/` before editing. Older0.9.2 archive,all historical
scripts/manifests/results/private environments remain unchanged. Only the built-in
candidate freeze advances;no historical re-freeze or new inference authority.
Both archived wheels are checked;0.9.2 still reproduces its entire original plan.
Candidate source hash:`650c8f6d60c538a08e096f32c870e75c103f1dc39265588263df06a3ca210716`.

Focused local macOS run:186PASS/10native-Windows skips/2dependency warnings6.03s.
Covers ACL policy,public/inherited/unknown grants,redaction,read ordering,handle
cleanup,byte limits,free-tier/Gemini/service regressions,runtime transition and the
unchanged17-module Windows scope. Ten native Windows tests exercise real ACLs,
including actual inheritance,null DACL,write grants,Unicode paths,symlinks and
handle-sharing replacement/write rejection. These are NOT yet Windows passes.
Existing permission tests now create real Windows ACL fixtures,retaining rejection
assertions;no additional existing tests were skipped.
Additional30qualification/evidence-policy checks PASS1.73s. Offline wheel build
and packaged ACL-module/Windows dependency metadata inspection PASS.
Final native-binding constant review corrected module lookups before handoff;
focused ACL/runtime/brain checks41PASS/10native untested1.63s,scoped lint/format/diff
PASS,final wheel rebuilt. Brain integrity PASS889/900words. Journal archive retains
earlier evidence verbatim;no historical records removed.

The manual Windows diagnostic runs credential/security tests first,then admission
checks and the existing first-failure suite. Next:owner review,commit/push and NEW
diagnostic run. Full Windows qualification and separate SQLite ACL work remain
pending. No automatic CI dispatch,real credential/DB migration or inference.
