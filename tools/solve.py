#!/usr/bin/env python3
"""
SNAKE-50000 参考解题器（WP 配套）

用法:
    python solve.py <snake50000.exe> [--key <64hex>] [--out <dir>]

不带 --key 时自动从 exe 的 PE 数据段里扫描出 AES-256 密钥
（原理：用候选密钥解密目录 blob 首块，结构过滤 + MD5 预言机确认）。
"""
import argparse
import hashlib
import os
import struct
import sys
import time

from Crypto.Cipher import AES

# ---------- Godot 常量 ----------
PACK_HEADER_MAGIC = 0x43504447          # "GDPC"
PACK_FORMAT_VERSION_V3 = 3
PACK_DIR_ENCRYPTED = 1 << 0
PACK_REL_FILEBASE = 1 << 1
PACK_FILE_ENCRYPTED = 1 << 0

IMG_SCN_CNT_INITIALIZED_DATA = 0x00000040
IMG_SCN_MEM_DISCARDABLE = 0x02000000


def parse_embedded_pck(data: bytes):
    """内嵌 PCK：文件尾 12 字节 = pck_size(u64 LE) + 'GDPC'"""
    tail_magic = struct.unpack_from('<I', data, len(data) - 4)[0]
    assert tail_magic == PACK_HEADER_MAGIC, 'not an embedded Godot PCK'
    pck_size, = struct.unpack_from('<Q', data, len(data) - 12)
    pck_start = len(data) - 12 - pck_size
    assert struct.unpack_from('<I', data, pck_start)[0] == PACK_HEADER_MAGIC

    ver, maj, mnr, pat, flags = struct.unpack_from('<5I', data, pck_start + 4)
    file_base, dir_ofs = struct.unpack_from('<QQ', data, pck_start + 24)
    print(f'[+] PCK: v{ver} godot {maj}.{mnr}.{pat} flags=0x{flags:x} '
          f'@0x{pck_start:x} size={pck_size}')
    print(f'    dir_encrypted={bool(flags & PACK_DIR_ENCRYPTED)}')
    return pck_start, file_base, dir_ofs


def parse_pe_data_sections(data: bytes):
    """返回 PE 中已初始化数据段的 (name, raw_offset, raw_size) 列表"""
    e_lfanew, = struct.unpack_from('<I', data, 0x3C)
    num_sections, = struct.unpack_from('<H', data, e_lfanew + 6)
    opt_size, = struct.unpack_from('<H', data, e_lfanew + 20)
    sec_table = e_lfanew + 24 + opt_size
    out = []
    for i in range(num_sections):
        off = sec_table + i * 40
        name = data[off:off + 8].rstrip(b'\x00').decode('ascii', 'replace')
        raw_size, raw_ptr = struct.unpack_from('<II', data, off + 16)
        chars, = struct.unpack_from('<I', data, off + 36)
        if raw_size and (chars & IMG_SCN_CNT_INITIALIZED_DATA) \
                and not (chars & IMG_SCN_MEM_DISCARDABLE):
            out.append((name, raw_ptr, min(raw_size, len(data) - raw_ptr)))
    return out


def fae_decrypt(blob: bytes, key: bytes) -> bytes:
    """FileAccessEncrypted 无 magic blob: md5(16) + plain_len(8) + iv(16) + AES-256-CFB128 密文"""
    md5d = blob[0:16]
    length, = struct.unpack_from('<Q', blob, 16)
    iv = blob[24:40]
    ds = length + (16 - length % 16 if length % 16 else 0)
    ct = blob[40:40 + ds]
    pt = AES.new(key, AES.MODE_CFB, iv=iv, segment_size=128).decrypt(ct)[:length]
    if hashlib.md5(pt).digest() != md5d:
        raise ValueError('MD5 mismatch - wrong key?')
    return pt


def scan_key(data: bytes, pck_start, dir_ofs: int) -> bytes:
    """用目录 blob 当预言机，暴力扫描 exe 数据段找 32 字节 AES 密钥"""
    d = pck_start + dir_ofs + 4                    # 跳过明文 file_count
    md5d = data[d:d + 16]
    length, = struct.unpack_from('<Q', data, d + 16)
    iv = data[d + 24:d + 40]
    ds = length + (16 - length % 16 if length % 16 else 0)
    ct = data[d + 40:d + 40 + ds]
    block0 = ct[:16]

    t0 = time.time()
    tried = 0
    for name, roff, rsize in parse_pe_data_sections(data):
        print(f'[*] 扫描段 {name} ({rsize} bytes) ...')
        for i in range(rsize - 32):
            key = data[roff + i:roff + i + 32]
            tried += 1
            pt0 = AES.new(key, AES.MODE_CFB, iv=iv, segment_size=128).decrypt(block0)
            # 目录明文首条目: u32 字符串长度(小值) + 以 '.' 开头的 ASCII 路径
            slen, = struct.unpack_from('<I', pt0, 0)
            if 4 <= slen <= 512 and pt0[4:5] == b'.':
                pt = AES.new(key, AES.MODE_CFB, iv=iv, segment_size=128).decrypt(ct)[:length]
                if hashlib.md5(pt).digest() == md5d:
                    print(f'[+] 密钥命中 @ {name}+0x{i:x}: {key.hex()}'
                          f'  ({tried} 次尝试, {time.time()-t0:.1f}s)')
                    return key
            if tried % 4_000_000 == 0:
                print(f'    ... {tried} 次尝试, {time.time()-t0:.0f}s')
    raise SystemExit('[-] 未找到密钥')


def parse_directory(pt: bytes):
    entries = []
    pos = 0
    while pos < len(pt):
        slen, = struct.unpack_from('<I', pt, pos)
        path = pt[pos + 4:pos + 4 + slen].rstrip(b'\x00').decode('utf-8', 'replace')
        pos += 4 + slen
        ofs, size = struct.unpack_from('<QQ', pt, pos)
        pos += 16
        md5 = pt[pos:pos + 16]
        pos += 16
        flags, = struct.unpack_from('<I', pt, pos)
        pos += 4
        entries.append((path, ofs, size, md5, flags))
    return entries


def _pad4(n: int) -> int:
    return (4 - n % 4) % 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('--key', default=None, help='64 位 hex 密钥（缺省自动扫描）')
    ap.add_argument('--out', default='solve_out')
    args = ap.parse_args()

    data = open(args.exe, 'rb').read()
    print(f'[+] {args.exe} ({len(data)} bytes)')

    pck_start, file_base, dir_ofs = parse_embedded_pck(data)

    if args.key:
        key = bytes.fromhex(args.key)
    else:
        key = scan_key(data, pck_start, dir_ofs)

    # ---- 解密目录 ----
    d = pck_start + dir_ofs
    count, = struct.unpack_from('<I', data, d)
    pt = fae_decrypt(data[d + 4:], key)
    print(f'[+] 目录解密成功（{count} 个文件, {len(pt)} 字节明文）')

    entries = parse_directory(pt)
    assert len(entries) == count, f'条目数不符: {len(entries)} != {count}'

    # ---- 解密所有文件 ----
    os.makedirs(args.out, exist_ok=True)
    for path, ofs, size, md5, flags in entries:
        start = pck_start + file_base + ofs
        if flags & PACK_FILE_ENCRYPTED:
            # 目录里的 size 是明文长度；blob 实长 = 40 + ceil(plain_len/16)*16
            plain_len, = struct.unpack_from('<Q', data, start + 16)
            blob_len = 40 + (plain_len + 15) // 16 * 16
            content = fae_decrypt(data[start:start + blob_len], key)
        else:
            content = data[start:start + size]
        ok = hashlib.md5(content).digest() == md5
        safe = path.replace('\\', '/').lstrip('./')
        outp = os.path.join(args.out, safe)
        os.makedirs(os.path.dirname(outp) or args.out, exist_ok=True)
        with open(outp, 'wb') as f:
            f.write(content)
        tag = 'ENC' if flags & PACK_FILE_ENCRYPTED else 'PLA'
        print(f'    [{tag}]{"✓" if ok else "✗"} {path} ({len(content)} B)')

    print(f'[+] 全部文件已解出 -> {args.out}/')


if __name__ == '__main__':
    main()
