#!/usr/bin/env python3
"""
repack_plain.py —— 把加密 exe 里的 PCK 解出并重打包成【无加密】独立 .pck
GDRE Tools 打开产物时无需填任何密钥。

用法: python repack_plain.py <snake50000.exe> <64hex密钥> [输出.pck]
"""
import hashlib
import struct
import sys

from Crypto.Cipher import AES

PACK_FILE_ENCRYPTED = 1 << 0


def pad4(n: int) -> int:
    return (4 - n % 4) % 4


def pad16(n: int) -> int:
    return (16 - n % 16) % 16


def main():
    exe, key_hex = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else 'rebuilt_plain.pck'
    key = bytes.fromhex(key_hex)

    data = open(exe, 'rb').read()
    pck_size, = struct.unpack_from('<Q', data, len(data) - 12)
    s = len(data) - 12 - pck_size
    file_base, dir_ofs = struct.unpack_from('<QQ', data, s + 24)

    # ---- 解密目录 ----
    d = s + dir_ofs
    count, = struct.unpack_from('<I', data, d)
    md5d = data[d + 4:d + 20]
    length, = struct.unpack_from('<Q', data, d + 20)
    iv = data[d + 28:d + 44]
    ds = length + (16 - length % 16 if length % 16 else 0)
    pt = AES.new(key, AES.MODE_CFB, iv=iv, segment_size=128).decrypt(data[d + 44:d + 44 + ds])[:length]
    assert hashlib.md5(pt).digest() == md5d, '目录解密失败: 密钥不对'

    # ---- 解析条目 + 解密文件 ----
    entries = []          # (path, plaintext)
    pos = 0
    for _ in range(count):
        slen, = struct.unpack_from('<I', pt, pos)
        path = pt[pos + 4:pos + 4 + slen].rstrip(b'\x00').decode('utf-8')
        pos += 4 + slen
        ofs, size = struct.unpack_from('<QQ', pt, pos)
        pos += 16
        md5 = pt[pos:pos + 16]
        pos += 16
        flags, = struct.unpack_from('<I', pt, pos)
        pos += 4

        start = s + file_base + ofs
        if flags & PACK_FILE_ENCRYPTED:
            plain_len, = struct.unpack_from('<Q', data, start + 16)
            blob_len = 40 + (plain_len + 15) // 16 * 16
            blob = data[start:start + blob_len]
            length2, = struct.unpack_from('<Q', blob, 16)
            iv2 = blob[24:40]
            ds2 = length2 + (16 - length2 % 16 if length2 % 16 else 0)
            content = AES.new(key, AES.MODE_CFB, iv=iv2, segment_size=128).decrypt(blob[40:40 + ds2])[:length2]
        else:
            content = data[start:start + size]
        assert hashlib.md5(content).digest() == md5, f'{path} MD5 不符'
        entries.append((path, content))
    print(f'[+] 解密 {count} 个文件, MD5 全部通过')

    # ---- 重打包为无加密 PCK v3 ----
    buf = bytearray()
    buf += struct.pack('<5I', 0x43504447, 3, 4, 5, 1)   # GDPC v3 4.5.1
    buf += struct.pack('<I', 1 << 1)                     # flags = REL_FILEBASE(无加密)
    file_base_ofs = len(buf); buf += b'\x00' * 8         # file_base 占位
    dir_ofs_ofs = len(buf);  buf += b'\x00' * 8         # dir_ofs 占位
    buf += b'\x00' * 64                                  # 保留区

    buf += b'\x00' * pad16(len(buf))                     # 文件区 16 对齐
    file_base = len(buf)
    records = []
    for path, content in entries:
        buf += b'\x00' * pad16(len(buf))
        records.append((path, len(buf) - file_base, len(content), hashlib.md5(content).digest()))
        buf += content

    buf += b'\x00' * pad16(len(buf))                     # 目录区 16 对齐
    dir_abs = len(buf)
    dir = struct.pack('<I', len(records))
    for path, ofs, size, md5 in records:
        pb = path.encode('utf-8')
        dir += struct.pack('<I', len(pb) + pad4(len(pb)))
        dir += pb + b'\x00' * pad4(len(pb))
        dir += struct.pack('<QQ', ofs, size) + md5 + struct.pack('<I', 0)  # flags=0 未加密
    buf += dir

    struct.pack_into('<Q', buf, file_base_ofs, file_base)
    struct.pack_into('<Q', buf, dir_ofs_ofs, dir_abs)

    open(out, 'wb').write(buf)
    print(f'[+] 无加密 PCK 已生成: {out} ({len(buf):,} bytes, {len(records)} 文件)')


if __name__ == '__main__':
    main()
