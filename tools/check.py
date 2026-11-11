"""一条龙检查：有没有 PCK？有没有 AES 加密？"""
import sys

exe = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\djkl1\snake_ctf\game\build\snake50000.exe'
d = open(exe, 'rb').read()

print(f'文件: {exe} ({len(d):,} bytes)')

# ① 有没有 PCK：看尾部 4 字节
if d[-4:] != b'GDPC':
    print('① 有PCK吗 : 没有（尾部无 GDPC，找旁边的 .pck 文件）')
    sys.exit()
print('① 有PCK吗 : 有（尾部 GDPC ✓）')

# ② PCK 起点与头部 flags
size = int.from_bytes(d[-12:-4], 'little')
s = len(d) - 12 - size
print(f'   位置     : {s:,} ~ 尾部，共 {size:,} 字节')

flags = int.from_bytes(d[s + 20:s + 24], 'little')
if flags & 1:
    print(f'② 有AES吗 : 有（flags={flags}，bit0=1 目录加密）→ 先挖 32 字节密钥')
else:
    print(f'② 有AES吗 : 没有（flags={flags}，bit0=0）→ GDRE 直接开')
