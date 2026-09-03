#!/usr/bin/env python
"""Rotates the Fernet ENCRYPTION_KEY across every vault row.

Zero-downtime rotation for a running deployment:
  1. Services keep the OLD key in ENCRYPTION_KEY_PREVIOUS (MultiFernet
     decrypts with either) — they never break mid-rotation.
  2. This script decrypts with the OLD key and re-encrypts every secret
     column under the NEW key, in ONE transaction: any undecryptable row
     aborts the run BEFORE a single write, so the vault is never
     partially rotated.
  3. The operator then swaps ENCRYPTION_KEY=<new>, ENCRYPTION_KEY_PREVIOUS=<old>,
     restarts, and removes _PREVIOUS after one verified poller cycle.

Usage:
  ENCRYPTION_KEY=<old> ENCRYPTION_KEY_NEW=<new> python scripts/rotate_fernet_key.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))


async def main() -> int:
    from cryptography.fernet import Fernet, InvalidToken
    from sqlalchemy import select

    from app.db.models import OAuthTokenModel, WebhookEndpointModel
    from app.db.session import async_session_factory

    old_key = os.environ.get("ENCRYPTION_KEY", "")
    new_key = os.environ.get("ENCRYPTION_KEY_NEW", "")
    if not old_key or not new_key:
        print("Set ENCRYPTION_KEY (current) and ENCRYPTION_KEY_NEW (fresh) in the env.", file=sys.stderr)
        return 2
    if old_key == new_key:
        print("Rotation requires a different key.", file=sys.stderr)
        return 2
    try:
        old_cipher = Fernet(old_key.encode("utf-8"))
        new_cipher = Fernet(new_key.encode("utf-8"))
    except Exception as e:
        print(f"Malformed key: {e}", file=sys.stderr)
        return 2

    async with async_session_factory() as session:
        # Phase 1: pre-flight — decrypt EVERYTHING before any write.
        rewrites: list[tuple[object, str, str]] = []  # (row, column, new_ciphertext)
        oauth_rows = list(await session.scalars(select(OAuthTokenModel)))
        for row in oauth_rows:
            for col in ("access_token_enc", "refresh_token_enc"):
                value = getattr(row, col)
                if not value:
                    continue
                try:
                    plain = old_cipher.decrypt(value.encode("utf-8"))
                except InvalidToken:
                    print(
                        f"ABORT (nothing written): oauth_tokens[{row.provider}].{col} "
                        "cannot be decrypted with ENCRYPTION_KEY — vault is not fully "
                        "under this key.",
                        file=sys.stderr,
                    )
                    return 3
                rewrites.append((row, col, new_cipher.encrypt(plain).decode("utf-8")))

        endpoint_rows = list(await session.scalars(select(WebhookEndpointModel)))
        for row in endpoint_rows:
            for col in ("secret_enc", "previous_secret_enc"):
                value = getattr(row, col)
                if not value:
                    continue
                try:
                    plain = old_cipher.decrypt(value.encode("utf-8"))
                except InvalidToken:
                    print(
                        f"ABORT (nothing written): webhook_endpoints[{row.id[:8]}].{col} "
                        "cannot be decrypted with ENCRYPTION_KEY.",
                        file=sys.stderr,
                    )
                    return 3
                rewrites.append((row, col, new_cipher.encrypt(plain).decode("utf-8")))

        # Phase 2: one transaction — all or nothing.
        for row, col, new_value in rewrites:
            setattr(row, col, new_value)
        await session.commit()

    rotated_tokens = sum(1 for r in rewrites if r[1].endswith("_enc") or r[1] == "secret_enc" or r[1] == "previous_secret_enc")
    print(f"Rotated {len(oauth_rows)} oauth rows and {len(endpoint_rows)} webhook endpoints ({rotated_tokens} secret columns).")
    print("Now set: ENCRYPTION_KEY=<new>  ENCRYPTION_KEY_PREVIOUS=<old>, restart the stack,")
    print("and remove _PREVIOUS after one verified poller cycle.")
    print("Back up the database dump AND the new key together — either alone is useless.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
