"""Offline, one-use launch activation for PDF Serial Renamer.

Only SHA-256 digests of the issued keys are bundled with the application.
Usage state is stored per-user in the application data folder.
"""

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Optional


KEY_HASHES = frozenset(
{
    "b5112e1d5c3a648d4ee95916fba9b23bd97bde279cb70e0acb96e411f5a8f801",
    "01d90bc4ab66cdd9a1238d7a1d6dff1a251451f912d7af11d8599bb2f228c4dc",
    "0a53a95a254047933ef3843686b8d78bbf8bc00137cb864d0e6a4ae1aa7c0ec6",
    "301eb326e2f99ad845b4d5b63d8bef34c6a04af2eafd50982b12b08582f736d1",
    "2737c58832145fcff79f45223b1c4c07ec6fc3147b8c0b7df7cdf24444f5b435",
    "33e39d58bf39fb74d3b49f3fc8502d727b06211553fccf6701f5788c00abf948",
    "916f3f4dbddb65adf52188f4e6e9e890213fb7e9f8a4ad0e4ec1e5988fe7339d",
    "dcd030611cd8c9c177ece368508c9647d7930d3bb077a6aacd1aff623bc03af7",
    "3e53846bc8f572d769c4c6e99d6da26431ecf15a5c19174b34e0f66d3e2b9a90",
    "c61a6f4e179a1d588075d46b82aad36dd0ca0c3585a4d2a2d8b70deaa475cee2",
    "16879c80bed23ed24ee2886a1795910ad5fbb80eb7c07155e5f766dfda969a1f",
    "5982a9efbc8d8d6e990c50f2473e0801e8fdc51c12e68020dcae7bb66a56c7cc",
    "762e6b37cf4e8f8489786a3247891bdf460d97779071239fc2222ee1a9583808",
    "0f7b2ff5fb807d43182db28046835b3d339f99b6cd346e82fe2c83b14d8cd390",
    "c14585eaa821b0b0e0e9b80e4960145238a5ba0646b99d542b64ec9937e9e21e",
    "71ef0744a5a1441da926dd7bee3359461d090626c108439814d9b262729dafd6",
    "9ee0ac212ee204aa853327538bfd99d529245707c38dee37a67bf03851794f84",
    "504d40d6b49f8c7b40a0478bcd3db7ac564693a074bb525bad2b91cc8093535c",
    "47a3a30f5ed13499ba69667653838253d15688cdd78d7307ac44cacc75351001",
    "a4a1ba4b73a492d463d1e572699705d70898d92a65822936ba4cb3acb454871b",
    "a695b0dbe4b3f95487c0becd32c2c95fe573f43f9b5d9a5c62c6ba2934e13157",
    "b4aec47c46648ac657fbe460ab1fd2354561b779cd3035a325935b373ea2c923",
    "5eb50f8164ae7e56ee9c1449a35542a000f0d07b38458675a6062f11c6a56682",
    "6d02248bd7b046e9c095c59ff7df0a70473c1b40daba0cc5cd84b6f0624b2068",
    "19b2a64c1ec9a0aab4ea9531443b4667d5921fcc0d47b9535b7855ea0097db76",
    "c2a9645e2efef5f21c30e0c17239863e5c647cdff87a70ff2c496f42d47e3209",
    "802b74aec57e7c0b20da70496024b434a4595ed429bc6cbc24d4f812d0452e7f",
    "97e6aeb24f34510cd06cc6a665a06388bbbc703a0ab3184c9951d32440e0b028",
    "07267dfccda25d91990c9060c9be51c305dfd4ea8c5cfa6f4e982401aa7e6001",
    "d5232055c29105cec889c005f5056f6576cf631aa558b2455d24ad7daf2c9e6d",
}
)


class ActivationError(Exception):
    """Base error for activation and license-state failures."""


class InvalidActivationKey(ActivationError):
    """Raised when a key is malformed, unknown, or already used."""


class ActivationStateError(ActivationError):
    """Raised when the persistent activation state cannot be trusted or saved."""


def _normalise_key(raw_key: str) -> str:
    return re.sub(r"[-\s]", "", raw_key).upper()


def _hash_key(normalised_key: str) -> str:
    return hashlib.sha256(normalised_key.encode("ascii")).hexdigest()


def default_state_path() -> Path:
    """Return a user-writable, per-user application data path."""
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "PDFSerialRenamer" / "activation.json"


class ActivationManager:
    """Reserve one unused key for a launch and consume it when the app closes.

    A reservation left behind by a crash or force quit is consumed on the next
    launch, so an interrupted session cannot make its key reusable.
    """

    STATE_VERSION = 1

    def __init__(self, key_hashes: Optional[Iterable[str]] = None, state_path=None):
        self._key_hashes = frozenset(key_hashes if key_hashes is not None else KEY_HASHES)
        self.state_path = Path(state_path) if state_path is not None else default_state_path()
        self._state = self._load_state()

        stale_key = self._state["active"]
        if stale_key is not None:
            recovered = {
                "version": self.STATE_VERSION,
                "used": list(self._state["used"]) + [stale_key],
                "active": None,
            }
            self._save_state(recovered)
            self._state = recovered

    @property
    def total_count(self) -> int:
        return len(self._key_hashes)

    @property
    def used_count(self) -> int:
        return len(self._state["used"])

    @property
    def remaining_count(self) -> int:
        reserved = 1 if self._state["active"] is not None else 0
        return self.total_count - self.used_count - reserved

    @property
    def used_hashes(self):
        """Expose a copy for diagnostics and tests; raw keys are never stored."""
        return frozenset(self._state["used"])

    def reserve_key(self, raw_key: str) -> None:
        """Validate and persist a key reservation for this application session."""
        if self._state["active"] is not None:
            raise ActivationError("Đã có một key được kích hoạt cho phiên này.")

        normalised_key = _normalise_key(raw_key)
        if not re.fullmatch(r"[A-F0-9]{24}", normalised_key):
            raise InvalidActivationKey("Key không đúng định dạng.")

        key_hash = _hash_key(normalised_key)
        if key_hash not in self._key_hashes:
            raise InvalidActivationKey("Key không hợp lệ.")
        if key_hash in self._state["used"]:
            raise InvalidActivationKey("Key này đã được sử dụng.")

        reserved = {
            "version": self.STATE_VERSION,
            "used": list(self._state["used"]),
            "active": key_hash,
        }
        self._save_state(reserved)
        self._state = reserved

    def consume_active_key(self) -> bool:
        """Consume the reserved key on normal application shutdown."""
        key_hash = self._state["active"]
        if key_hash is None:
            return False

        consumed = {
            "version": self.STATE_VERSION,
            "used": list(self._state["used"]) + [key_hash],
            "active": None,
        }
        self._save_state(consumed)
        self._state = consumed
        return True

    def _load_state(self):
        if not self.state_path.exists():
            return {"version": self.STATE_VERSION, "used": [], "active": None}

        try:
            with self.state_path.open("r", encoding="utf-8") as state_file:
                state = json.load(state_file)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ActivationStateError(
                f"Không đọc được trạng thái key tại {self.state_path}: {exc}"
            ) from exc

        if not isinstance(state, dict) or state.get("version") != self.STATE_VERSION:
            raise ActivationStateError(
                f"Trạng thái key không hợp lệ tại {self.state_path}."
            )

        used = state.get("used")
        active = state.get("active")
        if not isinstance(used, list) or any(not self._is_known_hash(item) for item in used):
            raise ActivationStateError(
                f"Danh sách key đã dùng không hợp lệ tại {self.state_path}."
            )
        if len(set(used)) != len(used):
            raise ActivationStateError(
                f"Danh sách key đã dùng bị trùng tại {self.state_path}."
            )
        if active is not None and (
            not self._is_known_hash(active) or active in used
        ):
            raise ActivationStateError(
                f"Key đang kích hoạt không hợp lệ tại {self.state_path}."
            )

        return {"version": self.STATE_VERSION, "used": list(used), "active": active}

    def _is_known_hash(self, value) -> bool:
        return isinstance(value, str) and value in self._key_hashes

    def _save_state(self, state) -> None:
        temporary_path = None
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix=".activation-", suffix=".tmp", dir=str(self.state_path.parent)
            )
            temporary_path = Path(temporary_name)
            if os.name != "nt":
                os.fchmod(file_descriptor, 0o600)
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as state_file:
                json.dump(state, state_file, separators=(",", ":"), sort_keys=True)
                state_file.flush()
                os.fsync(state_file.fileno())
            os.replace(str(temporary_path), str(self.state_path))
            temporary_path = None
        except OSError as exc:
            raise ActivationStateError(
                f"Không lưu được trạng thái key tại {self.state_path}: {exc}"
            ) from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
