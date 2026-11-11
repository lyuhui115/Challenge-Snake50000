"""扫描 PCK 内 'GDEC' (0x43454447) 加密文件 blob，逐一尝试解密"""
import struct, hashlib
from Crypto.Cipher import AES

EXE = r'C:\Users\djkl1\snake_ctf\game\build\snake50000.exe'
OUR_KEY = bytes.fromhex('f956ea30749ff095e35fcf5cb074d6e821782ca8072568624d9d3cb595564ce8')

data = open(EXE, 'rb').read()
pck_size, = struct.unpack_from('<Q', data, len(data) - 12)
pck_start = len(data) - 12 - pck_size
region = data[pck_start:pck_start + pck_size]

MAGIC = b'GDEC'
i = 0
blobs = []
while True:
    i = region.find(MAGIC, i)
    if i < 0:
        break
    blobs.append(pck_start + i)
    i += 1
print(f'GDEC blobs found: {len(blobs)}')

for off in blobs:
    d = off + 4
    md5d = data[d:d+16]
    length, = struct.unpack_from('<Q', data, d+16)
    iv = data[d+24:d+40]
    if length > pck_size:
        print(f'  @{off}: length {length} 超界，跳过')
        continue
    ds = length + (16 - length % 16 if length % 16 else 0)
    ct = data[d+40:d+40+ds]
    for name, key in [('our', OUR_KEY), ('zero', bytes(32))]:
        pt = AES.new(key, AES.MODE_CFB, iv=iv, segment_size=128).decrypt(ct)[:length]
        if hashlib.md5(pt).digest() == md5d:
            print(f'  @{off}: len={length} -> [{name} key] 解密成功: {pt[:60]!r}')
            break
    else:
        print(f'  @{off}: len={length} -> 两个 key 都失败')
