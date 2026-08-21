#!/usr/bin/env python3
"""
Re-encrypt every stored credential with a new Fernet key.

LOT-E / P8. Until now `app/utils/encryption.py` documented a rotation
procedure whose step 3 read "TODO: create migration script" — a written
procedure with no capability behind it. `EnvironmentService.rotate_credential`
only overwrites one credential with a NEW plaintext value; it never
re-encrypts what is already in the database. This script is that missing step.

What it does
------------
Reads every row of `project_credentials`, decrypts it with the OLD key,
re-encrypts it with the NEW key, and verifies the round trip before writing.
Everything happens in a single transaction: if one row fails, nothing is
committed.

Usage
-----
    # dry run (default): reports what would change, writes nothing
    python scripts/rotate_encryption_key.py --new-key "<new-fernet-key>"

    # actually rotate
    python scripts/rotate_encryption_key.py --new-key "<new-fernet-key>" --apply

    # rotate away from a legacy SECRET_KEY-derived key
    python scripts/rotate_encryption_key.py --old-secret-key-derived \
        --new-key "<new-fernet-key>" --apply

    # cla:SEC-03 — encrypt the tokens still stored in the clear, without
    # rotating the key. Run this BEFORE deploying: jordan_deploy_service
    # refuses a plaintext token rather than using it.
    python scripts/rotate_encryption_key.py --encrypt-plaintext --apply

    # after switching CREDENTIALS_ENCRYPTION_KEY in .env, confirm
    python scripts/rotate_encryption_key.py --verify-only

Then set CREDENTIALS_ENCRYPTION_KEY to the new key in the single .env and
restart the backend.

This script never prints a credential value, a key, or any fragment of
either. Rows are identified by id / project_id / credential_type only.
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

# Allow running as `python scripts/rotate_encryption_key.py` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.fernet import Fernet, InvalidToken  # noqa: E402

from app.config import settings  # noqa: E402
from app.utils.encryption import (  # noqa: E402
    build_fernet,
    derive_fernet_from_secret_key,
    looks_like_plaintext_token,
)


class RotationError(RuntimeError):
    """A row could not be processed; the whole transaction is abandoned."""


def _encrypt(fernet: Fernet, plaintext: str) -> str:
    """Mirror CredentialEncryption.encrypt (Fernet + urlsafe-b64 wrapper)."""
    return base64.urlsafe_b64encode(fernet.encrypt(plaintext.encode())).decode()


def _decrypt(fernet: Fernet, ciphertext: str) -> str:
    """Mirror CredentialEncryption.decrypt."""
    decoded = base64.urlsafe_b64decode(ciphertext.encode())
    return fernet.decrypt(decoded).decode()


def resolve_old_fernet(args) -> Tuple[Fernet, str]:
    """Determine which key currently protects the rows, without printing it."""
    if args.old_key:
        return build_fernet(args.old_key), "--old-key"
    if args.old_secret_key:
        return derive_fernet_from_secret_key(args.old_secret_key), "--old-secret-key (derived)"
    if args.old_secret_key_derived:
        if not settings.SECRET_KEY:
            raise RotationError(
                "--old-secret-key-derived needs SECRET_KEY to be configured."
            )
        return derive_fernet_from_secret_key(settings.SECRET_KEY), "SECRET_KEY (derived)"
    if settings.CREDENTIALS_ENCRYPTION_KEY:
        return build_fernet(settings.CREDENTIALS_ENCRYPTION_KEY), "settings.CREDENTIALS_ENCRYPTION_KEY"
    if settings.SECRET_KEY:
        return derive_fernet_from_secret_key(settings.SECRET_KEY), "SECRET_KEY (derived, legacy)"
    raise RotationError(
        "No current key available. Pass --old-key or --old-secret-key, or "
        "configure CREDENTIALS_ENCRYPTION_KEY."
    )


def classify(
    value: Optional[str],
    old: Fernet,
    new: Optional[Fernet],
    allow_plaintext: bool,
) -> Tuple[str, Optional[str]]:
    """
    Return (status, plaintext).

    status is one of: empty, rotate, already, plaintext, undecryptable.
    """
    if not value:
        return "empty", None
    try:
        return "rotate", _decrypt(old, value)
    except (InvalidToken, ValueError, Exception):
        pass
    if new is not None:
        try:
            return "already", _decrypt(new, value)
        except (InvalidToken, ValueError, Exception):
            pass
    if allow_plaintext and looks_like_plaintext_token(value):
        return "plaintext", value
    return "undecryptable", None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-encrypt project_credentials with a new Fernet key (P8).",
    )
    parser.add_argument("--new-key", help="New Fernet key to encrypt with.")
    parser.add_argument("--old-key", help="Current key, if not the configured one.")
    parser.add_argument("--old-secret-key", help="Legacy SECRET_KEY value to derive the old key from.")
    parser.add_argument(
        "--old-secret-key-derived",
        action="store_true",
        help="Derive the old key from the configured SECRET_KEY (pre-CREDENTIALS_ENCRYPTION_KEY deployments).",
    )
    parser.add_argument(
        "--encrypt-plaintext",
        action="store_true",
        help="Also encrypt rows still holding a bare provider token (cla:SEC-03).",
    )
    parser.add_argument("--apply", action="store_true", help="Commit. Without it, dry run.")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only check that every row decrypts with the configured key. Writes nothing.",
    )
    parser.add_argument("--database-url", help="Override DATABASE_URL for this run.")
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
        settings.DATABASE_URL = args.database_url

    # Imported late so the DATABASE_URL override above is picked up.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.project_credential import ProjectCredential

    if not args.verify_only and not args.new_key and not args.encrypt_plaintext:
        parser.error(
            "--new-key is required, unless --verify-only or --encrypt-plaintext is used."
        )

    try:
        old_fernet, old_source = resolve_old_fernet(args)
    except RotationError as exc:
        print(f"ERROR: {exc}")
        return 2

    # --encrypt-plaintext without --new-key: encrypt the bare tokens under the
    # key already in use, and leave every properly encrypted row untouched.
    # That is the migration an operator runs before deploying (cla:SEC-03),
    # without forcing an unrelated key rotation on the whole table.
    new_fernet = build_fernet(args.new_key) if args.new_key else old_fernet
    same_key = args.new_key is None

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    mode = "VERIFY" if args.verify_only else ("APPLY" if args.apply else "DRY-RUN")
    if same_key and not args.verify_only:
        mode += " (encrypt-plaintext only, key unchanged)"
    print("=" * 72)
    print(f"Credential key rotation — mode: {mode}")
    print(f"Database      : {_safe_dsn(settings.DATABASE_URL)}")
    print(f"Old key source: {old_source}")
    print(
        "New key       : "
        + ("(unchanged — encrypting plaintext only)" if same_key else "provided")
    )
    print("=" * 72)

    counts = {"rotate": 0, "already": 0, "plaintext": 0, "empty": 0, "undecryptable": 0}
    failures = []

    try:
        rows = session.query(ProjectCredential).order_by(ProjectCredential.id).all()
        print(f"{len(rows)} credential row(s) found.\n")

        for row in rows:
            status, plaintext = classify(
                row.encrypted_value, old_fernet, new_fernet, args.encrypt_plaintext
            )
            counts[status] += 1
            ctype = getattr(row.credential_type, "value", row.credential_type)
            label = f"id={row.id} project={row.project_id} type={ctype}"

            if status == "undecryptable":
                failures.append(label)
                print(f"  [FAIL   ] {label} — decrypts with neither key")
                continue
            if status == "empty":
                print(f"  [SKIP   ] {label} — empty value")
                continue
            if status == "already":
                print(f"  [OK     ] {label} — already under the new key")
                continue
            if status == "rotate" and same_key:
                # The key is not changing: a row that already decrypts is fine
                # as it is. Rewriting it would churn ciphertext for nothing.
                counts["rotate"] -= 1
                counts["already"] += 1
                print(f"  [OK     ] {label} — already encrypted, left untouched")
                continue
            if args.verify_only:
                print(f"  [OK     ] {label} — decrypts ({len(plaintext)} chars)")
                continue

            new_value = _encrypt(new_fernet, plaintext)
            # Verify the round trip BEFORE trusting the write.
            if _decrypt(new_fernet, new_value) != plaintext:
                failures.append(label)
                print(f"  [FAIL   ] {label} — round-trip check failed")
                continue
            tag = "ENCRYPT" if status == "plaintext" else "ROTATE "
            print(f"  [{tag}] {label} — verified round trip ({len(plaintext)} chars)")
            if args.apply:
                row.encrypted_value = new_value

        print()
        print("-" * 72)
        print(
            f"rotate={counts['rotate']} plaintext={counts['plaintext']} "
            f"already={counts['already']} empty={counts['empty']} "
            f"undecryptable={counts['undecryptable']}"
        )

        if failures:
            session.rollback()
            print(f"ABORTED — {len(failures)} row(s) could not be processed. "
                  "Nothing was written.")
            for f in failures:
                print(f"  - {f}")
            return 1

        if args.verify_only:
            session.rollback()
            print("VERIFY OK — every non-empty row decrypts with the current key.")
            return 0

        if args.apply:
            session.commit()
            if same_key:
                print(
                    f"COMMITTED — {counts['plaintext']} plaintext row(s) encrypted "
                    "under the current key. The key itself is unchanged, so there "
                    "is nothing to update in .env."
                )
            else:
                print("COMMITTED — all rows re-encrypted with the new key.")
                print("Next: set CREDENTIALS_ENCRYPTION_KEY to the new key in .env, "
                      "restart, then re-run with --verify-only.")
        else:
            session.rollback()
            print("DRY-RUN — nothing written. Re-run with --apply to commit.")
        return 0

    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    finally:
        session.close()
        engine.dispose()


def _safe_dsn(url: str) -> str:
    """Render a DSN without its password."""
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


if __name__ == "__main__":
    sys.exit(main())
