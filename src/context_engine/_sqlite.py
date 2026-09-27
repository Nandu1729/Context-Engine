"""SQLite connection policy shared by local stores, without provider dependencies."""

import os
import sqlite3


def connect(*args, **kwargs):
    db = sqlite3.connect(*args, **kwargs)
    try:
        if os.name == "nt":
            # Sort/index temporary data must not spill into an unchecked OS temp
            # directory. Durable rollback/WAL files still use the private DB dir.
            db.execute("PRAGMA temp_store=MEMORY")
            if db.execute("PRAGMA temp_store").fetchone()[0] != 2:
                raise sqlite3.OperationalError("Private SQLite temporary storage unavailable")
        return db
    except BaseException:
        db.close()
        raise
