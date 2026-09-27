# C10 — Windows SQLite ACL repair, D095

2026-09-27. Package0.9.5 is a development candidate,not a qualified release.
Owner approves real Windows SQLite security after repeated77f2de7 failures in
`test_private_schema_and_journal_boundaries[public]`. ZIP98353896744 records
636PASS/1FAIL291.71s;the backup filename and verbose-output fixes pass.

## Boundary implemented

- Memory databases,deletion ledgers,backup/restore paths,provider accounting/replay
  databases and service-control databases share the Windows storage boundary.
- New files/directories receive private security descriptors at creation. Existing
  files/directories are validated,never permission-rewritten or truncated.
- The effective user,SYSTEM and built-in Administrators are the only accepted
  owners/grantees. Null DACLs,broad grants and unsupported applicable ACE types
  fail closed. Parent-directory checks also inspect inherit-only grants and require
  an inheritable full-control grant for the effective user.
- Directory inheritance protects newly created SQLite journals. Existing rollback,
  WAL,shared-memory and matching super-journal files are checked before opening
  SQLite. This matters because Windows normally inherits new file ACLs from the
  parent directory;see [Microsoft file security](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights).
- Final file/directory reparse points,hard-linked files,non-disk objects and lexical
  UNC/device/alternate-stream paths are rejected. Permission checks use native
  handles;metadata-only sharing permits SQLite's concurrent read/write handles.
- Every transaction rechecks the boundary. Memory copies revalidate their source;
  restore still checks the independent deletion authority. No schema migration,
  changed quota logic,retry policy or weaker restoration assertion.
- Windows connections also require in-memory SQLite temporary tables/indexes,
  preventing sort/index spill into an unchecked OS temp directory. Durable
  journals remain on disk in the validated private directory. This trades temp
  disk spill for memory use;it does not establish an RSS bound.
- Native errors remain content-free StorageError;missing bindings cannot trigger
  an unchecked fallback. Shared Windows security code stays below provider/service
  layers;credential reading still uses its exclusive-writer-prohibiting handle.

## Scope and operator action

Use a dedicated private application directory. A new missing directory can be
created securely by the store;an existing broad or non-inheriting directory is
rejected even if its database itself has a private ACL. Existing stores may thus
require reviewed operator provisioning before0.9.5 will open them. The package
does not automatically modify existing permissions or migrate real databases.
Stop writers and preserve backups/deletion authority before any operator change.

SQLite opens its own paths after validation:trusted ancestors,effective user,
SYSTEM and administrators remain explicit assumptions. This is not protection
against hostile ancestor replacement,concurrent trusted-principal ACL rewrites,
encryption bypass or administrators. No universal filesystem-race or sandbox claim.
Unsupported ACL shapes fail closed,even where Windows effective access might be
safe. Native Windows verification,full platform qualification and production
recovery/load/quality gates remain pending.

## Tests and preserved evidence

Synthetic pytest directories get private inheritable Windows ACLs. The original
public-database test now grants real public access instead of relying on chmod.
The provider public-file assertion now runs on Windows too. Negative tests retain
their rejection assertions;the17historical POSIX module exclusions are unchanged.

New tests cover directory inheritance,redacted failures,handle cleanup,three store
types,new/reopened files,broad files/parents,sidecars,aliases,exclusive creation,
real journal creation/rollback,changed permissions and deletion-authority checks.
The manual Windows workflow runs a dedicated SQLite ACL probe before the full suite.

Final focused macOS verification:523PASS,44native-Windows tests NOT TESTED,
2dependency warnings,13.37s,including workers,tenant security and operational
recovery probes. Scoped ruff/diff checks PASS. Offline0.9.5 wheel build PASS.
Eight brain integrity tests PASS0.71s after adding the new linked archive to their
synthetic fixture. Built-wheel isolated version/freeze/lazy-import check PASS;
brain index/check PASS889/900words.
Windows-native tests comprise34new storage tests and10existing credential tests;
their local skips are not Windows passes.

Actual0.9.4 wheel/freeze preserved in[baseline archive](../archives/c10-storage-095/README.md).
Its wheel hash and exact freeze are checked by an isolated child. Existing0.9.3
and0.9.2 archives remain unchanged;0.9.2 still reproduces its original full plan.
Only the built-in0.9.5 development freeze advances;historical experiments are not
re-frozen. No live provider calls,operator database edits or remote CI dispatch.

Next:owner commit/push and start a NEW Windows diagnostic. Share the SQLite probe
and final summary;do not count a partial run as full Windows qualification.
