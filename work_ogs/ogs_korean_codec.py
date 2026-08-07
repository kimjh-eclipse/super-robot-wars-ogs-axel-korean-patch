# -*- coding: utf-8 -*-
"""Korean text codec used by the srwogs-v1.4.3s1 patch.

The patch places the 2,350 KS X 1001/EUC-KR completed Hangul syllables in
valid two-byte Shift-JIS slots.  Comparing known localized unit names proves
that the Shift-JIS slot ordinal is the KS X 1001 ordinal plus 1,410.

Non-Hangul text (ASCII, digits, Japanese punctuation, etc.) remains CP932.
"""

from __future__ import annotations

import argparse


SLOT_OFFSET = 1410
SJIS_LEADS = tuple(range(0x81, 0xA0)) + tuple(range(0xE0, 0xF0))
SJIS_TRAILS = tuple(range(0x40, 0x7F)) + tuple(range(0x80, 0xFD))
SJIS_LEAD_INDEX = {value: index for index, value in enumerate(SJIS_LEADS)}
SJIS_TRAIL_INDEX = {value: index for index, value in enumerate(SJIS_TRAILS)}
SJIS_SLOT_COUNT = len(SJIS_LEADS) * len(SJIS_TRAILS)
KS_WIDTH = 94
KS_HANGUL_COUNT = 2350


def ks_index(character: str) -> int:
    encoded = character.encode("euc_kr")
    if len(encoded) != 2:
        raise UnicodeEncodeError(
            "ogs-korean", character, 0, 1,
            "not a KS X 1001 completed Hangul syllable")
    lead, trail = encoded
    if not (0xB0 <= lead <= 0xC8 and 0xA1 <= trail <= 0xFE):
        raise UnicodeEncodeError(
            "ogs-korean", character, 0, 1,
            "not a KS X 1001 completed Hangul syllable")
    index = (lead - 0xB0) * KS_WIDTH + (trail - 0xA1)
    if index >= KS_HANGUL_COUNT:
        raise UnicodeEncodeError(
            "ogs-korean", character, 0, 1,
            "Hangul syllable is outside the 2,350-glyph patch font")
    return index


def slot_bytes(slot: int) -> bytes:
    if not 0 <= slot < SJIS_SLOT_COUNT:
        raise ValueError(f"Shift-JIS slot is out of range: {slot}")
    lead_index, trail_index = divmod(slot, len(SJIS_TRAILS))
    return bytes((SJIS_LEADS[lead_index], SJIS_TRAILS[trail_index]))


def slot_index(lead: int, trail: int) -> int | None:
    try:
        return (
            SJIS_LEAD_INDEX[lead] * len(SJIS_TRAILS)
            + SJIS_TRAIL_INDEX[trail]
        )
    except KeyError:
        return None


def encode_hangul(character: str) -> bytes:
    return slot_bytes(ks_index(character) + SLOT_OFFSET)


def decode_hangul(lead: int, trail: int) -> str | None:
    slot = slot_index(lead, trail)
    if slot is None:
        return None
    index = slot - SLOT_OFFSET
    if not 0 <= index < KS_HANGUL_COUNT:
        return None
    euc_kr = bytes((
        0xB0 + index // KS_WIDTH,
        0xA1 + index % KS_WIDTH,
    ))
    return euc_kr.decode("euc_kr")


def encode(text: str) -> bytes:
    output = bytearray()
    for position, character in enumerate(text):
        if "\uac00" <= character <= "\ud7a3":
            try:
                output.extend(encode_hangul(character))
            except UnicodeEncodeError as error:
                raise UnicodeEncodeError(
                    "ogs-korean", text, position, position + 1,
                    error.reason) from None
        else:
            try:
                output.extend(character.encode("cp932"))
            except UnicodeEncodeError as error:
                raise UnicodeEncodeError(
                    "ogs-korean", text, position, position + 1,
                    error.reason) from None
    return bytes(output)


def decode(data: bytes) -> str:
    output = []
    position = 0
    while position < len(data):
        byte = data[position]
        if byte in SJIS_LEADS and position + 1 < len(data):
            hangul = decode_hangul(byte, data[position + 1])
            if hangul is not None:
                output.append(hangul)
                position += 2
                continue
            pair = data[position:position + 2]
            try:
                output.append(pair.decode("cp932"))
                position += 2
                continue
            except UnicodeDecodeError:
                pass
        try:
            output.append(bytes((byte,)).decode("cp932"))
        except UnicodeDecodeError:
            output.append("\ufffd")
        position += 1
    return "".join(output)


def self_test() -> None:
    samples = {
        "\uc548\uc96c\ub974\uadf8": bytes.fromhex(
            "8f c6 91 8a 8c a1 89 76"),
        "\uc18c\uc6b8\uac8c\uc778": bytes.fromhex(
            "8e d0 90 8f 88 d2 90 cc"),
    }
    for text, expected in samples.items():
        actual = encode(text)
        assert actual == expected, (
            f"{text}: {actual.hex()} != {expected.hex()}")
        assert decode(actual) == text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="?")
    parser.add_argument("--decode-hex")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("OK")
    elif args.decode_hex is not None:
        print(decode(bytes.fromhex(args.decode_hex)))
    elif args.text is not None:
        print(encode(args.text).hex(" "))
    else:
        parser.error("provide text, --decode-hex, or --self-test")


if __name__ == "__main__":
    main()
