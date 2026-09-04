# -*- coding: utf-8 -*-
"""Remove every Ashsaber-only experiment from CURRENT ISO before release."""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import build_stage35_ashsaber_acquisition_hotfix as event_hook
import build_post35_ashsaber_lazy_acquisition as lazy_hook


ROOT = Path(__file__).resolve().parent
ISO = ROOT / "build" / "SRWOGS_AxelRoleSwap_kr_CURRENT.iso"
MANIFEST = ROOT / "runtime" / "ashsaber_experiments_rollback_manifest.json"
EXPECTED_SHA256 = "89457CA6DC3704AC3E931323982393432D4E5B9CC0C44CFF88B6CBF6EBA704CD"

ASH_COMPATIBILITY = {
    0x6FAFD2: (b"\xff\xff", b"\x01\x02"),
    0x95FFD2: (b"\xff\xff", b"\x01\x02"),
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def padded(blob: bytes, size: int) -> bytes:
    if len(blob) > size:
        raise ValueError("stub exceeds original cave")
    return blob + bytes(size - len(blob))


def main() -> None:
    before = digest(ISO)
    if before != EXPECTED_SHA256:
        raise SystemExit(f"CURRENT ISO guard failed: {before}")

    patches: list[tuple[str, int, bytes, bytes]] = []

    event_hook_offset = event_hook.va_to_iso(event_hook.HOOK_VA)
    event_jump = struct.pack("<I", event_hook.j(event_hook.STUB_VA)) + event_hook.ORIG_HOOK[4:]
    patches.append(("stage35 allocator hook", event_hook_offset, event_jump, event_hook.ORIG_HOOK))
    patches.append((
        "stage35 allocator cave",
        event_hook.va_to_iso(event_hook.STUB_VA),
        padded(event_hook.build_stub(), len(event_hook.ORIG_CAVE)),
        event_hook.ORIG_CAVE,
    ))

    lazy_hook_offset = lazy_hook.va_to_iso(lazy_hook.HOOK_VA)
    lazy_jump = struct.pack("<I", lazy_hook.j(lazy_hook.STUB_VA)) + lazy_hook.ORIG_HOOK[4:]
    patches.append(("post35 UI hook", lazy_hook_offset, lazy_jump, lazy_hook.ORIG_HOOK))
    patches.append((
        "post35 UI cave",
        lazy_hook.va_to_iso(lazy_hook.STUB_VA),
        padded(lazy_hook.build_stub(), len(lazy_hook.ORIG_CAVE)),
        lazy_hook.ORIG_CAVE,
    ))

    for offset, (old, new) in ASH_COMPATIBILITY.items():
        patches.append(("Ashsaber compatibility restore", offset, old, new))

    with ISO.open("r+b") as image:
        for label, offset, old, _ in patches:
            image.seek(offset)
            actual = image.read(len(old))
            if actual != old:
                raise SystemExit(
                    f"guard failed for {label} at {offset:#x}: "
                    f"expected {old.hex(' ')}, got {actual.hex(' ')}"
                )
        for _, offset, _, new in patches:
            image.seek(offset)
            image.write(new)

    after = digest(ISO)
    report = {
        "kind": "rollback-all-ashsaber-experiments",
        "sha256_before": before,
        "sha256_after": after,
        "preserved": [
            "enhanced Soulgain return/stats/name",
            "enhanced Soulgain all-normal-pilot compatibility",
            "Axel boarding mask fix",
            "Vaisaga all-normal-pilot compatibility",
            "battle dialogue fixes",
        ],
        "removed": [
            "stage35 Ashsaber acquisition allocator hook",
            "post35 Ashsaber lazy-backfill UI hook",
            "allied Ashsaber all-pilots compatibility experiment",
        ],
        "changes": [
            {
                "label": label,
                "offset": hex(offset),
                "before": old.hex(" "),
                "after": new.hex(" "),
            }
            for label, offset, old, new in patches
        ],
    }
    MANIFEST.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(after)


if __name__ == "__main__":
    main()
