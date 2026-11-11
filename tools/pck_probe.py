"""分析 snake50000.exe 内嵌 PCK：确定目录加密实际使用的密钥"""
import struct, hashlib, sys
from Crypto.Cipher import AES

EXE = r'C:\Users\djkl1\snake_ctf\game\build\snake50000.exe'
OUR_KEY = bytes.fromhex('f956ea30749ff095e35fcf5cb074d6e821782ca8072568624d9d3cb595564ce8')

data = open(EXE, 'rb').read()
print(f'exe size: {len(data)}')

# 内嵌 PCK：文件尾 12 字节 = pck_size(8) + magic(4)
pck_size, = struct.unpack_from('<Q', data, len(data) - 12)
tail_magic = data[-4:]
print(f'tail: size={pck_size}, magic={tail_magic}')
pck_start = len(data) - 12 - pck_size
assert data[pck_start:pck_start+4] == b'GDPC', 'PCK start magic mismatch'
print(f'pck_start: {pck_start} (0x{pck_start:x})')

# 头部: magic,ver,maj,min,patch,flags(各4) file_base(8) dir_ofs(8) reserved(64)
ver, maj, mnr, pat, flags = struct.unpack_from('<5I', data, pck_start + 4)
file_base, dir_ofs = struct.unpack_from('<QQ', data, pck_start + 4 + 20)
print(f'format v{ver}, godot {maj}.{mnr}.{pat}, flags=0x{flags:x} '
      f'(DIR_ENC={bool(flags & 1)}, REL_FILEBASE={bool(flags & 2)})')
print(f'file_base={file_base}, dir_ofs(rel)={dir_ofs} -> abs {pck_start + dir_ofs}')

# 目录区（V3, REL_FILEBASE）：count(4)明文 + 加密blob
d = pck_start + dir_ofs
ncount, = struct.unpack_from('<I', data, d)
print(f'file_count (plaintext): {ncount}')
d += 4
md5d = data[d:d+16]
length, = struct.unpack_from('<Q', data, d+16)
iv = data[d+24:d+40]
ct = data[d+40:d+40+length + (16 - length % 16 if length % 16 else 0)]
print(f'dir blob: md5={md5d.hex()}, plain_len={length}, iv={iv.hex()}, ct_len={len(ct)}')

for name, key in [('OUR KEY', OUR_KEY), ('ZERO KEY', bytes(32))]:
    cipher = AES.new(key, AES.MODE_CFB, iv=iv, segment_size=128)
    pt = cipher.decrypt(ct)[:length]
    ok = hashlib.md5(pt).digest() == md5d
    print(f'[{name}] md5 match: {ok}')
    if ok:
        n, = struct.unpack_from('<I', pt, 0)
        print(f'  -> directory OK, {n} files; first bytes: {pt[:48]!r}')
        sys.exit(0)
print('两个密钥都解不开 —— 需要进一步排查')
