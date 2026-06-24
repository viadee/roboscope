"""Curated execution-modifier registry (EXEC.10).

Single source of truth for which PreRunModifier / PreRebotModifier classes a run
may use. Three trust tiers:

* **vendor** — RoboScope-shipped, in-repo, vetted (``builtin.py``). EDITOR-usable.
* **org** — registered by the *operator* via backend config (NOT the UI):
  the ``roboscope.modifiers`` entry-point group, or a ``ROBOSCOPE_MODIFIERS_CONFIG``
  file. Trust established at deploy time → EDITOR-usable once registered.
* runtime *user-code* is NOT in this registry — a modifier reference that is not a
  registered key is treated as user-code and gated ADMIN + the
  ``executionPreRunModifierUserCode`` flag (see ``governance.dependencies``).

The gate routes by registry membership, never by a free-typed class path. The
registry never raises on a bad org entry: it logs and skips it (a broken plugin
must not take the server down).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from importlib import import_module
from importlib import metadata as importlib_metadata
from pathlib import Path

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "roboscope.modifiers"
CONFIG_ENV_VAR = "ROBOSCOPE_MODIFIERS_CONFIG"
VALID_KINDS = ("prerun", "prerebot")


@dataclass(frozen=True)
class ModifierEntry:
    """A curated modifier the run dialog may offer and the resolver may emit."""

    key: str
    class_path: str  # vendor: "ClassName" in builtin.py; org: "module.sub:Class"
    kind: str  # "prerun" | "prerebot"
    label: str
    tier: str  # "vendor" | "org"
    description: str = ""
    args_schema: tuple[dict, ...] = ()

    def public_dict(self) -> dict:
        """Shape returned to the frontend picker (no internal class paths)."""
        return {
            "key": self.key,
            "kind": self.kind,
            "label": self.label,
            "tier": self.tier,
            "description": self.description,
            "args_schema": list(self.args_schema),
        }


# --- Tier-A vendor entries (in-repo, vetted) ------------------------------------

_VENDOR_ENTRIES: tuple[ModifierEntry, ...] = (
    ModifierEntry(
        key="roboscope_tag_stamp",
        # Module path (NOT a file path): RF imports it like the quarantine
        # listener precedent, so it needs `src` importable in the run venv — the
        # same documented FLAKY-3 precondition. builtin.py imports only robot.api.
        class_path="src.execution.modifiers.builtin.TagStamper",
        kind="prerun",
        label="Tag stamper",
        tier="vendor",
        description="Adds a fixed tag to every test in the run.",
        args_schema=({"name": "tag", "label": "Tag", "required": False},),
    ),
)


# --- Tier-B org loaders (operator-trusted, backend config only) -----------------


def _load_entry_point_entries() -> list[ModifierEntry]:
    """Discover org modifiers from the ``roboscope.modifiers`` entry-point group.

    An entry-point's name is the registry key; its value (``module:Class``) is the
    class path. Optional class attributes ``roboscope_kind`` / ``roboscope_label``
    / ``roboscope_description`` supply metadata. A failing entry is logged + skipped.
    """
    out: list[ModifierEntry] = []
    try:
        eps = importlib_metadata.entry_points(group=ENTRY_POINT_GROUP)
    except Exception:  # pragma: no cover - importlib quirks across versions
        logger.warning("could not enumerate %s entry points", ENTRY_POINT_GROUP, exc_info=True)
        return out
    for ep in eps:
        try:
            cls = ep.load()
            kind = getattr(cls, "roboscope_kind", "prerun")
            if kind not in VALID_KINDS:
                raise ValueError(f"invalid roboscope_kind {kind!r}")
            out.append(
                ModifierEntry(
                    key=ep.name,
                    class_path=ep.value,
                    kind=kind,
                    label=getattr(cls, "roboscope_label", ep.name),
                    tier="org",
                    description=getattr(cls, "roboscope_description", ""),
                )
            )
        except Exception:
            logger.warning(
                "skipping org modifier entry-point %r (load/validation failed)",
                getattr(ep, "name", "?"),
                exc_info=True,
            )
    return out


def _read_config_file(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in (".toml",):
        import tomllib

        data = tomllib.loads(text)
    elif suffix in (".json",):
        data = json.loads(text)
    elif suffix in (".yaml", ".yml"):
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(text)
    else:
        raise ValueError(f"unsupported modifiers config extension: {suffix}")
    entries = data.get("modifiers", data) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise ValueError("modifiers config must be a list (or a {modifiers: [...]} table)")
    return entries


def _load_config_entries() -> list[ModifierEntry]:
    """Load org modifiers declared in the ``ROBOSCOPE_MODIFIERS_CONFIG`` file.

    Each entry: ``{key, class_path, kind, label, description?, args_schema?}``.
    The class is imported to validate it is loadable. Bad entries are skipped.
    """
    cfg = os.environ.get(CONFIG_ENV_VAR)
    if not cfg:
        return []
    path = Path(cfg)
    if not path.is_file():
        logger.warning("%s points to a missing file: %s", CONFIG_ENV_VAR, cfg)
        return []
    try:
        raw_entries = _read_config_file(path)
    except Exception:
        logger.warning("could not parse %s (%s)", CONFIG_ENV_VAR, cfg, exc_info=True)
        return []

    out: list[ModifierEntry] = []
    for raw in raw_entries:
        try:
            key = raw["key"]
            class_path = raw["class_path"]
            kind = raw.get("kind", "prerun")
            if kind not in VALID_KINDS:
                raise ValueError(f"invalid kind {kind!r}")
            _import_class(class_path)  # validate importability; raises on failure
            out.append(
                ModifierEntry(
                    key=key,
                    class_path=class_path,
                    kind=kind,
                    label=raw.get("label", key),
                    tier="org",
                    description=raw.get("description", ""),
                    args_schema=tuple(raw.get("args_schema", ())),
                )
            )
        except Exception:
            logger.warning(
                "skipping org modifier config entry %r (load/validation failed)",
                raw.get("key", "?") if isinstance(raw, dict) else "?",
                exc_info=True,
            )
    return out


def _import_class(class_path: str):
    """Import ``module:Class`` or ``module.Class`` and return the class object."""
    if ":" in class_path:
        module_name, _, attr = class_path.partition(":")
    else:
        module_name, _, attr = class_path.rpartition(".")
    if not module_name or not attr:
        raise ValueError(f"malformed class path: {class_path!r}")
    mod = import_module(module_name)
    return getattr(mod, attr)


# --- Registry assembly (cached) -------------------------------------------------

_cache: dict[str, ModifierEntry] | None = None
_cache_lock = threading.Lock()


def load_registry(*, force: bool = False) -> dict[str, ModifierEntry]:
    """Return the merged registry ``{key: ModifierEntry}`` (vendor + org).

    Cached after first call. Org keys never override vendor keys (vendor wins;
    a colliding org key is logged + skipped). The lock serialises the lazy
    first-load so the (operator-code-importing) loaders run once, not per racing
    request.
    """
    global _cache
    if _cache is not None and not force:
        return _cache
    with _cache_lock:
        if _cache is not None and not force:
            return _cache
        registry: dict[str, ModifierEntry] = {e.key: e for e in _VENDOR_ENTRIES}
        for entry in (*_load_entry_point_entries(), *_load_config_entries()):
            if entry.key in registry:
                logger.warning(
                    "org modifier key %r collides with an existing entry; skipping", entry.key
                )
                continue
            registry[entry.key] = entry
        _cache = registry
        return registry


def reset_cache() -> None:
    """Drop the cache (tests + a future hot-reload)."""
    global _cache
    _cache = None


def get_available_modifiers(kind: str | None = None) -> list[ModifierEntry]:
    """All curated entries, optionally filtered by kind, sorted by label."""
    entries = load_registry().values()
    if kind is not None:
        entries = [e for e in entries if e.kind == kind]
    return sorted(entries, key=lambda e: (e.tier != "vendor", e.label.lower()))


def get_modifier(key: str) -> ModifierEntry | None:
    return load_registry().get(key)


def is_curated_key(key: str) -> bool:
    """True iff ``key`` is a registered curated modifier (Tier A/B)."""
    return key in load_registry()


def build_modifier_spec(key: str, args: list | tuple = ()) -> str:
    """Resolve a curated key to the ``robot`` ``--prerunmodifier``/``--prerebotmodifier``
    value string (``module.Class:arg1:arg2``). Both vendor and org entries use a
    module path RF imports (the quarantine-listener precedent).

    Raises ``KeyError`` if the key is not curated (callers must check first).
    """
    entry = load_registry()[key]
    parts = [entry.class_path, *(str(a) for a in args)]
    return ":".join(parts)
