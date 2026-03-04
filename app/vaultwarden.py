"""Vaultwarden integration via the `bw` CLI subprocess.

Server config (URL, ORG_ID, COLLECTION_ID) comes from app config / .env.
User credentials (CLIENT_ID, CLIENT_SECRET, MASTER_PASSWORD) are provided
at connect time via the UI and stored in the Flask session.
The bw session key is also cached in the Flask session to avoid re-unlocking
on every request.
"""

from __future__ import annotations

import json
import os
import subprocess

from flask import current_app, session


class VaultwardenError(Exception):
    pass


class VaultwardenClient:
    def __init__(
        self,
        server_url: str,
        client_id: str,
        client_secret: str,
        master_password: str,
        org_id: str,
        collection_id: str,
        session_key: str | None = None,
    ) -> None:
        self._server_url      = server_url
        self._client_id       = client_id
        self._client_secret   = client_secret
        self._master_password = master_password
        self._org_id          = org_id
        self._collection_id   = collection_id
        self._session_key     = session_key

    # ── Low-level runner ───────────────────────────────────────────

    def _run_bw(self, *args: str, stdin_data: str | None = None, env_extra: dict | None = None) -> str:
        """Run bw CLI and return stdout. Raises VaultwardenError on non-zero exit."""
        env = os.environ.copy()
        if self._session_key:
            env["BW_SESSION"] = self._session_key
        if env_extra:
            env.update(env_extra)

        try:
            result = subprocess.run(
                ["bw", *args],
                input=stdin_data,
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
        except FileNotFoundError:
            raise VaultwardenError(
                "bw CLI not found. Install it with: npm install -g @bitwarden/cli"
            )
        except subprocess.TimeoutExpired:
            raise VaultwardenError("bw CLI timed out.")

        if result.returncode != 0:
            raise VaultwardenError(result.stderr.strip() or result.stdout.strip() or "bw CLI error")

        return result.stdout.strip()

    # ── Session management ─────────────────────────────────────────

    def connect(self) -> str:
        """
        Full connect flow: configure server → API key login → unlock.
        Returns the bw session key. Caller should store it in Flask session.
        """
        # 1. Configure server (idempotent)
        self._run_bw("config", "server", self._server_url)

        # 2. Check status
        try:
            raw = self._run_bw("status", "--raw")
            bw_status = json.loads(raw).get("status", "unauthenticated")
        except (VaultwardenError, json.JSONDecodeError):
            bw_status = "unauthenticated"

        # 3. Log in if needed
        if bw_status == "unauthenticated":
            self._run_bw(
                "login", "--apikey",
                env_extra={
                    "BW_CLIENTID":     self._client_id,
                    "BW_CLIENTSECRET": self._client_secret,
                },
            )

        # 4. Unlock
        session_key = self._run_bw(
            "unlock", "--passwordenv", "BW_PASSWORD", "--raw",
            env_extra={"BW_PASSWORD": self._master_password},
        )
        if not session_key:
            raise VaultwardenError("bw unlock returned empty session key.")

        self._session_key = session_key
        return session_key

    def _ensure_unlocked(self) -> None:
        """Verify session key is still valid; re-unlock if not. Updates Flask session."""
        if not self._session_key:
            key = self.connect()
            session["vw_session_key"] = key
            return
        try:
            raw = self._run_bw("status", "--raw")
            st = json.loads(raw).get("status")
            if st != "unlocked":
                key = self.connect()
                session["vw_session_key"] = key
        except (VaultwardenError, json.JSONDecodeError):
            key = self.connect()
            session["vw_session_key"] = key

    # ── Public API ─────────────────────────────────────────────────

    def status(self) -> dict:
        """Return the raw bw status dict."""
        self._run_bw("config", "server", self._server_url)
        try:
            return json.loads(self._run_bw("status", "--raw"))
        except (VaultwardenError, json.JSONDecodeError) as exc:
            raise VaultwardenError(f"Could not get vault status: {exc}") from exc

    def add_login(
        self,
        name: str,
        username: str,
        password: str,
        url: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Create a Login item in the org collection."""
        self._ensure_unlocked()

        item: dict = {
            "type": 1,
            "name": name,
            "organizationId": self._org_id,
            "collectionIds": [self._collection_id],
            "login": {
                "username": username,
                "password": password,
                "uris": [{"match": None, "uri": url}] if url else [],
            },
            "notes": notes or "",
        }

        encoded = self._run_bw("encode", stdin_data=json.dumps(item))
        created_raw = self._run_bw("create", "item", encoded)
        try:
            return json.loads(created_raw)
        except json.JSONDecodeError as exc:
            raise VaultwardenError(f"Failed to parse created item: {exc}") from exc

    def create_text_send(
        self,
        name: str,
        text: str,
        delete_days: int = 7,
        password: str | None = None,
    ) -> dict:
        """Create a Text Send and return dict with accessUrl."""
        self._ensure_unlocked()

        cmd = [
            "send", "create",
            "--name", name,
            "--text", text,
            "--deleteInDays", str(delete_days),
        ]
        if password:
            cmd += ["--password", password]

        raw = self._run_bw(*cmd)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VaultwardenError(f"Failed to parse Send response: {exc}") from exc


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_vaultwarden_configured(app) -> bool:
    """True if server-side config (URL, ORG_ID, COLLECTION_ID) is set."""
    return all(
        app.config.get(k, "").strip()
        for k in ("VAULTWARDEN_URL", "VAULTWARDEN_ORG_ID", "VAULTWARDEN_COLLECTION_ID")
    )


def is_vault_connected() -> bool:
    """True if user credentials are present in the current session."""
    return bool(session.get("vw_client_id") and session.get("vw_client_secret") and session.get("vw_master_password"))


def get_vw_client() -> VaultwardenClient:
    """Build a VaultwardenClient from app config + Flask session credentials."""
    cfg = current_app.config
    return VaultwardenClient(
        server_url      = cfg["VAULTWARDEN_URL"],
        client_id       = session["vw_client_id"],
        client_secret   = session["vw_client_secret"],
        master_password = session["vw_master_password"],
        org_id          = cfg["VAULTWARDEN_ORG_ID"],
        collection_id   = cfg["VAULTWARDEN_COLLECTION_ID"],
        session_key     = session.get("vw_session_key"),
    )
