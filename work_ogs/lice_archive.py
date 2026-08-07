# -*- coding: utf-8 -*-
"""Inspect and extract the fixed-layout LICE/Wpbb archives used by PS2 OGs."""
import argparse
import hashlib
import json
import os
import struct


def sha256(data):
    return hashlib.sha256(data).hexdigest().upper()


def find_wpbb(data):
    position = 0
    while True:
        position = data.find(b'Wpbb', position, min(len(data), 0x100000))
        if position < 0:
            raise ValueError('Wpbb directory not found')
        if position + 8 <= len(data):
            count = struct.unpack_from('<I', data, position + 4)[0]
            table_end = position + 8 + count * 8
            if 0 < count < 0x10000 and table_end <= len(data):
                valid = True
                for index in range(count):
                    offset, size = struct.unpack_from(
                        '<II', data, position + 8 + index * 8)
                    if offset + size > len(data):
                        valid = False
                        break
                if valid:
                    return position
        position += 4


def parse_archive(data):
    if data[:4] == b'LICE':
        header_offset, count, active_count = struct.unpack_from(
            '<III', data, 4)
        if data[header_offset:header_offset + 4] != b'Wpbb':
            raise ValueError(
                f'missing Wpbb directory at 0x{header_offset:X}')
        order = list(struct.unpack_from(
            f'<{count}H', data, 0x10)) if count else []
        archive_type = 'LICE'
    else:
        header_offset = find_wpbb(data)
        count = struct.unpack_from('<I', data, header_offset + 4)[0]
        active_count = count
        order = list(range(count))
        archive_type = 'Wpbb'
    directory_count = struct.unpack_from('<I', data, header_offset + 4)[0]
    if directory_count != count:
        raise ValueError(
            f'LICE/Wpbb count mismatch: {count} != {directory_count}')
    entries = []
    for index in range(count):
        offset, size = struct.unpack_from(
            '<II', data, header_offset + 8 + index * 8)
        if offset + size > len(data):
            raise ValueError(
                f'entry {index} exceeds archive: '
                f'0x{offset:X}+0x{size:X}>0x{len(data):X}')
        payload = data[offset:offset + size]
        entries.append({
            'index': index,
            'order': order[index],
            'offset': offset,
            'size': size,
            'sha256': sha256(payload),
            'head_hex': payload[:16].hex(),
        })
    return {
        'archive_type': archive_type,
        'header_offset': header_offset,
        'count': count,
        'active_count': active_count,
        'entries': entries,
    }


def load(path):
    with open(path, 'rb') as source:
        return source.read()


def command_list(args):
    data = load(args.archive)
    manifest = parse_archive(data)
    manifest['archive'] = os.path.abspath(args.archive)
    manifest['size'] = len(data)
    manifest['sha256'] = sha256(data)
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as destination:
            json.dump(manifest, destination, ensure_ascii=False, indent=2)
            destination.write('\n')
    for entry in manifest['entries']:
        print(
            f"{entry['index']:04d} order={entry['order']:04X} "
            f"offset=0x{entry['offset']:08X} size=0x{entry['size']:08X} "
            f"head={entry['head_hex']}")


def command_extract(args):
    data = load(args.archive)
    manifest = parse_archive(data)
    os.makedirs(args.output, exist_ok=True)
    for entry in manifest['entries']:
        if args.indices and entry['index'] not in args.indices:
            continue
        start = entry['offset']
        payload = data[start:start + entry['size']]
        path = os.path.join(args.output, f"{entry['index']:04d}.bin")
        with open(path, 'wb') as destination:
            destination.write(payload)
        print(path)
    with open(
            os.path.join(args.output, 'manifest.json'),
            'w', encoding='utf-8') as destination:
        json.dump(manifest, destination, ensure_ascii=False, indent=2)
        destination.write('\n')


def command_replace(args):
    data = bytearray(load(args.archive))
    manifest = parse_archive(data)
    entry = manifest['entries'][args.index]
    replacement = load(args.replacement)
    if len(replacement) > entry['size']:
        raise ValueError(
            f'replacement is too large: 0x{len(replacement):X} > '
            f"0x{entry['size']:X}")
    start = entry['offset']
    data[start:start + entry['size']] = b'\x00' * entry['size']
    data[start:start + len(replacement)] = replacement
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'wb') as destination:
        destination.write(data)
    print(args.output)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    list_parser = subparsers.add_parser('list')
    list_parser.add_argument('archive')
    list_parser.add_argument('--json')
    list_parser.set_defaults(function=command_list)

    extract_parser = subparsers.add_parser('extract')
    extract_parser.add_argument('archive')
    extract_parser.add_argument('output')
    extract_parser.add_argument('--indices', type=int, nargs='*')
    extract_parser.set_defaults(function=command_extract)

    replace_parser = subparsers.add_parser('replace')
    replace_parser.add_argument('archive')
    replace_parser.add_argument('index', type=int)
    replace_parser.add_argument('replacement')
    replace_parser.add_argument('output')
    replace_parser.set_defaults(function=command_replace)

    args = parser.parse_args()
    args.function(args)


if __name__ == '__main__':
    main()
