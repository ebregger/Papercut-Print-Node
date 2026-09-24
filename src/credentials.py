"""Load PaperCut credentials from a restricted local secrets file."""

from __future__ import annotations

import json
import logging
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CREDENTIALS_PATH = "~/mtu-print-node/config/credentials.json"
MAX_WORLD_READABLE_MODE = 0o077  # reject if group/other have any permission


@dataclass(frozen=True)
class MtuCredentials:
  user_id: str
  username: str
  password: str


class CredentialsError(Exception):
  """Raised when credentials cannot be loaded safely."""


def expand_path(value: str | Path) -> Path:
  return Path(value).expanduser().resolve()


def _check_file_permissions(path: Path) -> None:
  """Reject credentials files that are readable by group/other (Unix only)."""
  if sys.platform == "win32":
    logger.debug("Skipping POSIX permission check on Windows for %s", path)
    return
  mode = path.stat().st_mode
  if mode & MAX_WORLD_READABLE_MODE:
    raise CredentialsError(
      f"{path} is too permissive (mode {stat.filemode(mode)}). "
      "Run: chmod 600 config/credentials.json"
    )


def load_credentials_file(path: Path | None = None, *, settings: dict | None = None) -> dict[str, dict[str, str]]:
  if path is None:
    path = resolve_credentials_path(settings)
  else:
    path = expand_path(path)
  if not path.is_file():
    raise CredentialsError(
      f"Credentials file not found: {path}\n"
      "Create it from the example:\n"
      "  cp config/credentials.json.example config/credentials.json\n"
      "  chmod 600 config/credentials.json"
    )
  _check_file_permissions(path)
  with path.open(encoding="utf-8") as handle:
    payload = json.load(handle)

  accounts = payload.get("accounts")
  if not isinstance(accounts, dict) or not accounts:
    raise CredentialsError(
      f"{path} must contain a non-empty 'accounts' object"
    )

  normalized: dict[str, dict[str, str]] = {}
  for account_id, entry in accounts.items():
    if not isinstance(entry, dict):
      raise CredentialsError(f"accounts.{account_id} must be an object")
    username = (entry.get("username") or "").strip()
    password = entry.get("password") or ""
    if not username or not password:
      raise CredentialsError(
        f"accounts.{account_id} needs non-empty username and password"
      )
    if password.startswith("PASTE_") or password == "YOUR_PAPERCUT_PASSWORD":
      raise CredentialsError(
        f"accounts.{account_id} still has a placeholder password"
      )
    normalized[str(account_id)] = {
      "username": username,
      "password": password,
    }
  return normalized


def _credential_candidates(settings: dict | None = None) -> list[Path]:
  candidates: list[Path] = []
  if settings and settings.get("credentials_path"):
    candidates.append(expand_path(settings["credentials_path"]))
  candidates.append(Path.cwd() / "config" / "credentials.json")
  repo_root = Path(__file__).resolve().parent.parent
  candidates.append(repo_root / "config" / "credentials.json")
  candidates.append(expand_path(DEFAULT_CREDENTIALS_PATH))
  # Preserve order, drop duplicates.
  seen: set[Path] = set()
  unique: list[Path] = []
  for path in candidates:
    if path not in seen:
      seen.add(path)
      unique.append(path)
  return unique


def resolve_credentials_path(settings: dict | None = None) -> Path:
  for path in _credential_candidates(settings):
    if path.is_file():
      return path
  return _credential_candidates(settings)[0]


def get_credentials(
    account_id: str,
    *,
    credentials_path: Path | str | None = None,
    settings: dict | None = None,
) -> MtuCredentials:
  path = expand_path(credentials_path) if credentials_path else resolve_credentials_path(settings)
  accounts = load_credentials_file(path, settings=settings)
  if account_id not in accounts:
    known = ", ".join(sorted(accounts)) or "(none)"
    raise CredentialsError(
      f"Unknown credential id '{account_id}'. Known ids: {known}"
    )
  entry = accounts[account_id]
  return MtuCredentials(
    user_id=account_id,
    username=entry["username"],
    password=entry["password"],
  )


def merge_user_credentials(
    users: list[dict],
    *,
    credentials_path: Path | str | None = None,
    settings: dict | None = None,
) -> list[dict]:
  """
  Attach username/password to each printer user from the secrets file.

  Each user entry must include credential_id matching a key in accounts{}.
  Passwords must never appear in users.json.
  """
  path = expand_path(credentials_path) if credentials_path else resolve_credentials_path(settings)
  accounts = load_credentials_file(path, settings=settings)
  merged: list[dict] = []

  for user in users:
    user_id = user.get("id")
    cred_id = user.get("credential_id", user_id)
    if not cred_id:
      raise CredentialsError(f"User {user!r} missing id/credential_id")
    if cred_id not in accounts:
      raise CredentialsError(
        f"User '{user_id}' references credential_id '{cred_id}' "
        f"but it is not defined in {path}"
      )
    if "password" in user or "username" in user:
      logger.warning(
        "Ignoring inline credentials for user '%s'; using %s instead",
        user_id,
        path,
      )
    entry = accounts[cred_id]
    merged.append(
      {
        **user,
        "username": entry["username"],
        "password": entry["password"],
      }
    )
  return merged


def list_account_ids(
    *,
    credentials_path: Path | str | None = None,
    settings: dict | None = None,
) -> list[str]:
  path = expand_path(credentials_path) if credentials_path else resolve_credentials_path(settings)
  return sorted(load_credentials_file(path))
