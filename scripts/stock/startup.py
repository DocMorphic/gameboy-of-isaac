#!/usr/bin/env python3
"""Verify pinned assets natively, cache that result, and prepare faster startup."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

SCALE_PATCHES = [
    ('0f2ec80f87f0010000', '0f28d048e910000000'),
    ('f30f59c2e881fee6fff30f10542410', 'f30f59c2f248904890f30f10542410'),
]
CHECK_OFFSET = 0x1E6A20
CHECK_PROLOGUE = bytes.fromhex('415731c0b940000000')
CHECK_RETURN = bytes.fromhex('b801000000c3909090')
X11_CACHE_SHA256 = 'b6e89f1d832981bfbf7221abfe4d537cd3983f715323be0c8743d6d038d5c7ad'


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def patch_executable(data):
    for old, new in SCALE_PATCHES:
        old, new = bytes.fromhex(old), bytes.fromhex(new)
        if data.count(old) != 1:
            raise ValueError('Unexpected executable scaling code')
        data = data.replace(old, new)
    if data[CHECK_OFFSET:CHECK_OFFSET+len(CHECK_PROLOGUE)] != CHECK_PROLOGUE:
        raise ValueError('Unexpected archive verification routine')
    return data[:CHECK_OFFSET] + CHECK_RETURN + data[CHECK_OFFSET+len(CHECK_PROLOGUE):]


def decode_lzw(blob, offset, size):
    """KAGE v1: MSB-first LZW, 1024-byte pieces, dictionary shared by pieces."""
    table = [bytes([n]) for n in range(256)]
    width = 8
    result = bytearray()
    while len(result) < size:
        if offset + 4 > len(blob):
            raise ValueError('Truncated archive piece header')
        length = struct.unpack_from('<I', blob, offset)[0] & 0x7fffffff
        offset += 4
        if not 0 < length <= 2047 or offset + length > len(blob):
            raise ValueError('Invalid archive piece length')
        piece = blob[offset:offset+length]
        offset += length
        bits = int.from_bytes(piece, 'big')
        cursor = 0
        previous = None
        decoded = bytearray()
        want = min(1024, size-len(result))
        while len(decoded) < want:
            if len(table) >= 4095:
                table = [bytes([n]) for n in range(256)]
                width = 8
                previous = None
            if previous is not None:
                while (1 << width) <= len(table):
                    width += 1
            shift = len(piece)*8 - cursor - width
            if shift < -7:
                raise ValueError('Truncated LZW code')
            code = ((bits >> shift) if shift >= 0 else (bits << -shift)) & ((1 << width)-1)
            cursor += width
            if code < len(table):
                word = table[code]
            elif code == len(table) and previous is not None:
                word = previous + previous[:1]
            else:
                raise ValueError('Invalid LZW dictionary reference')
            decoded.extend(word)
            if previous is not None:
                table.append(previous + word[:1])
            previous = word
        result.extend(decoded[:want])
    return bytes(result)


def extract_cutscenes(config):
    blob = config.read_bytes()
    magic, version, offset, count = struct.unpack_from('<7sBIH', blob)
    if magic != b'ARCH000' or version != 1 or offset + count*20 > len(blob):
        raise ValueError('Unexpected config archive format')
    for i in range(count):
        h1, h2, start, size, _ = struct.unpack_from('<IIIII', blob, offset+i*20)
        if (h1, h2) == (3438444571, 3730614446):
            if not 0 < size < 1024*1024:
                raise ValueError('Unexpected cutscene configuration size')
            return decode_lzw(blob, start, size)
    raise ValueError('Intro configuration not found')


def without_intro(xml):
    root = ET.fromstring(xml)
    intro = [c for c in root if c.get('id') == '1' and c.get('name') == 'Intro']
    if len(intro) != 1:
        raise ValueError('Unexpected intro configuration')
    for part in list(intro[0]):
        intro[0].remove(part)
    intro[0].set('fadeout', 'false')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def atomic_write(path, data):
    tmp = path.with_name(path.name + '.partial')
    tmp.write_bytes(data)
    os.replace(tmp, path)


def prepare(game):
    manifest = json.loads((game/'runtime/steam-depot.lock.json').read_text())['files']
    stamp = game/'runtime/startup-cache.json'
    try:
        cached = json.loads(stamp.read_text())
    except (OSError, ValueError):
        cached = {}
    checked = {}
    for name, expected in manifest.items():
        if name != 'isaac.x64' and not (name.startswith('resources/packed/') and name.endswith('.a')):
            continue
        path = game/'gamefiles'/name
        st = path.stat()
        signature = [st.st_size, st.st_mtime_ns, st.st_ctime_ns, expected['sha256']]
        if cached.get(name) != signature:
            if st.st_size != expected['size'] or sha256(path) != expected['sha256']:
                raise ValueError('Game file verification failed: ' + name)
        checked[name] = signature
    exe = game/'gamefiles/isaac.x64.hack'
    if cached.get('patch_version') != 1 or not exe.is_file() or sha256(exe) != cached.get('patched_sha256'):
        atomic_write(exe, patch_executable((game/'gamefiles/isaac.x64').read_bytes()))
        exe.chmod(0o755)
    source = game/'libs.x64/libx11_cache.so'
    if sha256(source) != X11_CACHE_SHA256:
        raise ValueError('Unexpected upstream X11 cache library')
    library = source.read_bytes()
    if library[0x150c:0x1510] != bytes.fromhex('4883f809'):
        raise ValueError('Unexpected X11 cache expiration code')
    library = library[:0x150f] + b'\x00' + library[0x1510:]
    fast_cache = game/'libs.x64/libx11_cache_fast.so'
    if not fast_cache.exists() or fast_cache.read_bytes() != library:
        atomic_write(fast_cache, library)
    intro = game/'gamefiles/resources/cutscenes.xml'
    generated = without_intro(extract_cutscenes(game/'gamefiles/resources/packed/config.a'))
    if not intro.exists() or intro.read_bytes() != generated:
        atomic_write(intro, generated)
    checked.update(patch_version=1, patched_sha256=sha256(exe))
    if cached != checked:
        atomic_write(stamp, (json.dumps(checked, indent=2)+'\n').encode())
        print('Verified packed assets natively; prepared fast startup and intro skip', flush=True)


if __name__ == '__main__':
    prepare(Path(sys.argv[1]).resolve())
