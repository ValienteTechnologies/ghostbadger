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
from pathlib import Path

from flask import current_app, session

_PROJECT_ROOT = Path(__file__).parent.parent
_LOCAL_BW     = _PROJECT_ROOT / "packages" / "bitwarden" / "node_modules" / ".bin" / "bw"
# bw config is stored here so it doesn't touch any global ~/.config/Bitwarden CLI
_BW_APPDATA   = _PROJECT_ROOT / "packages" / "bitwarden" / ".bw-appdata"


def _bw_cmd() -> str:
    """Return path to local bw binary, or 'bw' if not yet installed."""
    return str(_LOCAL_BW) if _LOCAL_BW.exists() else "bw"


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
        # Isolate bw config/data from any global Bitwarden install
        env["BITWARDENCLI_APPDATA_DIR"] = str(_BW_APPDATA)
        if self._session_key:
            env["BW_SESSION"] = self._session_key
        if env_extra:
            env.update(env_extra)

        cmd = _bw_cmd()
        try:
            result = subprocess.run(
                [cmd, *args],
                input=stdin_data,
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
        except FileNotFoundError:
            raise VaultwardenError(
                f"bw CLI not found at {cmd}. "
                "Run: cd packages/bw && npm install"
            )
        except subprocess.TimeoutExpired:
            raise VaultwardenError("bw CLI timed out.")

        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip() or "bw CLI error"
            raise VaultwardenError(err)

        return result.stdout.strip()

    # ── Session management ─────────────────────────────────────────

    def _bw_status(self) -> str:
        """Return the bw status string: unauthenticated | locked | unlocked."""
        try:
            raw = self._run_bw("status", "--raw")
            return json.loads(raw).get("status", "unauthenticated")
        except (VaultwardenError, json.JSONDecodeError):
            return "unauthenticated"

    def connect(self) -> str:
        """
        Full connect flow: configure server → API key login → unlock.
        Returns the bw session key. Caller should store it in Flask session.
        """
        _BW_APPDATA.mkdir(parents=True, exist_ok=True)

        # 1. Configure server (idempotent)
        self._run_bw("config", "server", self._server_url)

        # 2. Log in via API key if not already authenticated
        if self._bw_status() == "unauthenticated":
            self._run_bw(
                "login", "--apikey",
                env_extra={
                    "BW_CLIENTID":     self._client_id,
                    "BW_CLIENTSECRET": self._client_secret,
                },
            )

        # 3. Unlock — --raw returns just the session key
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
        if not self._session_key or self._bw_status() != "unlocked":
            key = self.connect()
            session["vw_session_key"] = key

    # ── Public API ─────────────────────────────────────────────────

    def status(self) -> dict:
        """Return the bw status dict (keys: serverUrl, status, userEmail, …)."""
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
        import datetime

        self._ensure_unlocked()

        deletion_date = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=delete_days)
        ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        send_obj: dict = {
            "name": name,
            "type": 0,
            "text": {"text": text, "hidden": False},
            "deletionDate": deletion_date,
            "disabled": False,
        }
        if password:
            send_obj["password"] = password

        encoded = self._run_bw("encode", stdin_data=json.dumps(send_obj))
        raw = self._run_bw("send", "create", encoded)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VaultwardenError(f"Failed to parse Send response: {exc}") from exc


def is_vaultwarden_configured(app) -> bool:
    """True if server-side config (URL, ORG_ID, COLLECTION_ID) is set."""
    return all(
        app.config.get(k, "").strip()
        for k in ("VAULTWARDEN_URL", "VAULTWARDEN_ORG_ID", "VAULTWARDEN_COLLECTION_ID")
    )


def is_vault_connected() -> bool:
    """True if user credentials are present in the current session."""
    return bool(
        session.get("vw_client_id")
        and session.get("vw_client_secret")
        and session.get("vw_master_password")
    )


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
