# -*- coding: utf-8 -*-
"""35화 바이사가 액셀 표시 및 라미아 전투 전 회화 핫픽스.

새 ISO를 만들지 않고 SRWOGS_AxelRoleSwap_kr_CURRENT.iso만 제자리 수정한다.
모든 변경은 기존 값과 슬롯 크기를 확인한 뒤 적용하며, 되돌릴 수 있도록
변경 전후 바이트를 JSON manifest에 기록한다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ogs_korean_codec import decode, encode


ROOT = Path(__file__).resolve().parent
ISO = ROOT / "build" / "SRWOGS_AxelRoleSwap_kr_CURRENT.iso"
MANIFEST = ROOT / "runtime" / "stage35_vysaga_hotfix_manifest.json"

MAP_ISO_OFF = 0xC10800
PTBL_DATA_REL = 0x13A484
ARCHIVE_BASES = (0x5DA000, 0x83F000)  # SHARED.BIN, IM.BIN

# 바이사가 전환 뒤 사용하는 액셀 B 키도 실기 검증된 액셀 A Plot(53)을 쓰게 한다.
# 전투 청크의 대사/음성은 건드리지 않는다.
PTBL_REPLACEMENTS = {
    0x4A5: (54, 53),
    0x521: (54, 53),
}

SCENARIO_REPLACEMENTS = {
    # PASS27에서 앞 대화의 문장이 중복 이식된 슬롯을 OG2 액셀 1.20 흐름으로 복원.
    0x61EE9AF: (
        94,
        "라미아：그런　추상적인　것을　위해@모든　것을@배신하셨다는　겁니까？",
        "라미아：액셀　대장、생각이　어떠셨든…@지령을　어기고　레몬님들을@해치려　하셨습니다",
    ),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def read_cstr(data: bytearray, absolute: int) -> bytes:
    end = data.index(0, absolute)
    return bytes(data[absolute:end])


def main() -> None:
    if not ISO.is_file():
        raise FileNotFoundError(ISO)

    before_sha = sha256(ISO)
    data = bytearray(ISO.read_bytes())
    changes: list[dict[str, object]] = []

    for archive_base in ARCHIVE_BASES:
        for raw_key, (expected, replacement) in PTBL_REPLACEMENTS.items():
            absolute = archive_base + PTBL_DATA_REL + raw_key * 2
            old = int.from_bytes(data[absolute:absolute + 2], "little")
            if old != expected:
                raise ValueError(
                    f"PTbl guard failed at 0x{absolute:X}: {old} != {expected}"
                )
            new_raw = replacement.to_bytes(2, "little")
            changes.append({
                "kind": "ptbl",
                "absolute_offset": f"0x{absolute:X}",
                "raw_key": f"0x{raw_key:X}",
                "old_index": old,
                "new_index": replacement,
                "old_hex": bytes(data[absolute:absolute + 2]).hex(),
                "new_hex": new_raw.hex(),
            })
            data[absolute:absolute + 2] = new_raw

    for map_offset, (capacity, expected_text, replacement_text) in SCENARIO_REPLACEMENTS.items():
        absolute = MAP_ISO_OFF + map_offset
        old_raw = read_cstr(data, absolute)
        old_text = decode(old_raw)
        if old_text != expected_text:
            raise ValueError(
                f"scenario guard failed at 0x{map_offset:X}: {old_text!r}"
            )
        new_encoded = encode(replacement_text)
        if len(new_encoded) > capacity:
            raise ValueError(
                f"slot overflow at 0x{map_offset:X}: {len(new_encoded)} > {capacity}"
            )
        old_slot = bytes(data[absolute:absolute + capacity])
        new_raw = new_encoded + bytes(capacity - len(new_encoded))
        changes.append({
            "kind": "scenario_text",
            "map_offset": f"0x{map_offset:X}",
            "absolute_offset": f"0x{absolute:X}",
            "capacity": capacity,
            "encoded_size": len(new_encoded),
            "old_text": old_text,
            "new_text": replacement_text,
            "old_hex": old_slot.hex(),
            "new_hex": new_raw.hex(),
        })
        data[absolute:absolute + capacity] = new_raw

    ISO.write_bytes(data)
    after_sha = sha256(ISO)

    # 재검증: 지정 범위 외 파일 크기 불변, PTbl과 문자열 모두 목표값 일치.
    verify = ISO.read_bytes()
    if len(verify) != len(data):
        raise AssertionError("ISO size changed")
    for archive_base in ARCHIVE_BASES:
        for raw_key, (_, replacement) in PTBL_REPLACEMENTS.items():
            absolute = archive_base + PTBL_DATA_REL + raw_key * 2
            actual = int.from_bytes(verify[absolute:absolute + 2], "little")
            if actual != replacement:
                raise AssertionError(f"PTbl verify failed at 0x{absolute:X}")
    for map_offset, (_, _, replacement_text) in SCENARIO_REPLACEMENTS.items():
        absolute = MAP_ISO_OFF + map_offset
        actual = decode(read_cstr(bytearray(verify), absolute))
        if actual != replacement_text:
            raise AssertionError(f"scenario verify failed at 0x{map_offset:X}")

    manifest = {
        "target": str(ISO),
        "description": "35화 바이사가 액셀 화자 표시 및 VS 라미아 전투 전 회화 핫픽스",
        "before_sha256": before_sha,
        "after_sha256": after_sha,
        "iso_size": len(data),
        "change_count": len(changes),
        "changed_bytes": sum(
            sum(a != b for a, b in zip(bytes.fromhex(str(c["old_hex"])), bytes.fromhex(str(c["new_hex"]))))
            for c in changes
        ),
        "changes": changes,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "target": str(ISO),
        "before_sha256": before_sha,
        "after_sha256": after_sha,
        "change_count": len(changes),
        "changed_bytes": manifest["changed_bytes"],
        "manifest": str(MANIFEST),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
