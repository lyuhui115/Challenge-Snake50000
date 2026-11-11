"""穷举解密模式/密钥组合，并打印明文首字节"""
import struct, hashlib
from Crypto.Cipher import AES

EXE = r'C:\Users\djkl1\snake_ctf\game\build\snake50000.exe'
OUR_KEY = bytes.fromhex('f956ea30749ff095e35fcf5cb074d6e821782ca8072568624d9d3cb595564ce8')

data = open(EXE, 'rb').read()
pck_size, = struct.unpack_from('<Q', data, len(data) - 12)
pck_start = len(data) - 12 - pck_size
dir_ofs, = struct.unpack_from('<Q', data, pck_start + 4 + 20)
d = pck_start + dir_ofs
count, = struct.unpack_from('<I', data, d); d += 4
md5d = data[d:d+16]
length, = struct.unpack_from('<Q', data, d+16)
iv = data[d+24:d+40]
ds = length + (16 - length % 16 if length % 16 else 0)
ct = data[d+40:d+40+ds]
print(f'count={count} md5={md5d.hex()} len={length} iv={iv.hex()}')

for kname, key in [('our', OUR_KEY), ('zero', bytes(32))]:
    for mode, mk in [('CFB128', lambda k: AES.new(k, AES.MODE_CFB, iv=iv, segment_size=128)),
                     ('CFB8',   lambda k: AES.new(k, AES.MODE_CFB, iv=iv, segment_size=8)),
                     ('CBC-dec', lambda k: AES.new(k, AES.MODE_CBC, iv=iv)),
                     ('CTR',    lambda k: AES.new(k, AES.MODE_CTR, nonce=b'', initial_value=iv))]:
        try:
            pt = mk(key).decrypt(ct)[:length]
            hit = hashlib.md5(pt).digest() == md5d
            print(f'{kname:5s} {mode:8s} md5={hit}  head={pt[:32].hex()}')
        except Exception as e:
            print(f'{kname:5s} {mode:8s} error {e}')
