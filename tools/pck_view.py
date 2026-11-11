#!/usr/bin/env python3
"""
pck_view.py —— 查看 Godot exe 内嵌 PCK 的状态
用法:
    python pck_view.py <exe>                 # 无钥匙模式: 看头部 + 目录原始字节(乱码)
    python pck_view.py <exe> --key <64hex>   # 带钥匙模式: 额外解密并打印完整文件表
"""
import struct, sys, hashlib
from Crypto.Cipher import AES


def main():
    exe = sys.argv[1]
    key = None
    if len(sys.argv) > 3 and sys.argv[2] == '--key':
        key = bytes.fromhex(sys.argv[3])

    data = open(exe, 'rb').read()
    print(f'文件: {exe}  ({len(data):,} bytes)')

    # ---- 1. 定位 PCK ----
    magic = data[-4:]
    if magic != b'GDPC':
        print('[-] 尾部无 GDPC 魔数: 不是内嵌 PCK 的 Godot 导出')
        return
    pck_size, = struct.unpack_from('<Q', data, len(data) - 12)
    s = len(data) - 12 - pck_size
    print(f'\n[1] PCK 定位')
    print(f'    尾部魔数   : {magic} ✓')
    print(f'    包大小     : {pck_size:,} bytes')
    print(f'    包起始偏移 : {s} (0x{s:x})')
    print(f'    起始处魔数 : {data[s:s+4]} {"✓ 双向确认" if data[s:s+4]==b"GDPC" else "✗ 异常"}')

    # ---- 2. 头部 ----
    ver, maj, mnr, pat, flags = struct.unpack_from('<5I', data, s + 4)
    file_base, dir_ofs = struct.unpack_from('<QQ', data, s + 24)
    print(f'\n[2] 头部 (前44字节, 明文)')
    print(f'    格式版本   : v{ver}')
    print(f'    引擎版本   : {maj}.{mnr}.{pat}')
    print(f'    flags      : {flags:#010b}')
    print(f'                 bit0(目录加密) = {flags & 1}  {"← AES加密了!" if flags & 1 else "(未加密)"}')
    print(f'                 bit1(相对偏移) = {(flags >> 1) & 1}')
    print(f'    file_base  : {file_base}')
    print(f'    目录偏移   : {dir_ofs} → 绝对 {s + dir_ofs}')

    # ---- 3. 目录 ----
    d = s + dir_ofs
    count, = struct.unpack_from('<I', data, d)
    print(f'\n[3] 目录 (在 {d})')
    print(f'    文件数     : {count} (此4字节是明文)')
    print(f'    目录前32字节原始值:')
    print(f'    {data[d+4:d+36].hex(" ")}')
    if not (flags & 1):
        print('    (未加密, 上面应该能认出文件名)')
        return
    print('    ↑ 全是随机样字节 = AES 加密中, 人眼/strings 都没法看')

    if key is None:
        print('\n[!] 目录被加密。带 --key <64hex> 重跑可看解密后的文件表')
        return

    # ---- 4. 解密目录 ----
    md5d = data[d+4:d+20]; length, = struct.unpack_from('<Q', data, d+20)
    iv = data[d+28:d+44]
    ds = length + (16 - length % 16 if length % 16 else 0)
    pt = AES.new(key, AES.MODE_CFB, iv=iv, segment_size=128).decrypt(data[d+44:d+44+ds])[:length]
    if hashlib.md5(pt).digest() != md5d:
        print('[-] MD5 不符: 钥匙不对')
        return
    print(f'\n[4] 解密成功 (MD5 ✓) —— 完整文件表:')
    pos, n = 0, 0
    while pos < len(pt) and n < count:
        slen, = struct.unpack_from('<I', pt, pos)
        path = pt[pos+4:pos+4+slen].rstrip(b'\x00').decode('utf-8', 'replace')
        pos += 4 + slen
        ofs, size = struct.unpack_from('<QQ', pt, pos); pos += 16
        md5 = pt[pos:pos+16].hex()[:12]; pos += 16
        fl, = struct.unpack_from('<I', pt, pos); pos += 4
        n += 1
        print(f'    {n:2d}. {path}')
        print(f'        大小={size:>6}B  偏移={ofs:<6} 加密={"是" if fl & 1 else "否"}  md5={md5}..')


if __name__ == '__main__':
    main()
