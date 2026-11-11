# SNAKE-50000 Writeup（官方参考解法）

> 官方题解，随题库存档；`src/` 为完整工程源码，`tools/` 含可复现的解题脚本。

## 0x00 题目信息

| 项 | 值 |
|---|---|
| 附件 | `snake50000.exe`（84,244,632 B）SHA256 `0954028e0f432185ad4c1edc5aa5b8d86821c0f620ac2fc9138fa2e583f6d0aa` |
| 分类 | Reverse（Godot 引擎） |
| 题面 | 贪吃蛇吃满 50000 分（5000 颗食物）解锁 flag |
| 答案 | `flag{7544nnfn55dn9f9T5df503fn}` |
| 预期难度 | 中上（需要逆向 Godot PCK 加密机制 + GDScript 字节码） |

四道关卡：**识别引擎 → 挖出 AES 密钥 → 解密 PCK 反编译脚本 → 离线复现 flag 铸造算法**。

---

## 0x01 为什么不能硬玩 / 不能改分

**硬玩**：初始 6.7 格/秒，吃 50 颗后加速到满速 25 格/秒（`BASE_STEP 0.150s → MIN_STEP 0.040s`，每颗食物加速 0.0022s）。5000 颗食物即使机器人完美寻路也要按小时计，人类一条命通关概率为零。

**改内存分数**：`flag_manager.gd` 的反作弊——每次真实吃食物记录时间戳，`reveal()` 校验：

```gdscript
# 分数必须 == 吃食物次数 × 10（防只改分数）
if score != _food_times.size() * POINTS_PER_FOOD: return DECOY
# 时间跨度必须物理可达：相邻间隔 ≥ 30ms（防一帧批量刷时间戳）
if span < (_food_times.size() - 1) * MIN_FOOD_GAP_MS: return DECOY
```

不满足返回诱饵 `flag{Y0u_W1sh_It_W4s_Th1s_E4sy}`（交平台判错，且提示玩家"你想得太简单了"）。

> `strings snake50000.exe | grep flag{` 一无所获——flag 从不以任何形式存在于二进制中，是**到达终点时现场铸造**的。

---

## 0x02 第一关：识别引擎与加密形态

1. 拖进 IDA/Ghidra 或直接 `strings`：大量 `Godot Engine v4.5.1.stable.custom_build` 字符串 → Godot 4.5.1 导出游戏。
2. 查文件尾：最后 12 字节 = `pck_size(u64 LE) + "GDPC"` → **PCK 内嵌在 exe 尾部**（标准 Godot 自包含导出）。
3. 解析 PCK v3 头（`pck_start = 文件长 − 12 − pck_size`，小端）：

```
+0   u32  magic      = "GDPC" (0x43504447)
+4   u32  version    = 3
+8   u32×3 godot 版本 = 4.5.1
+20  u32  flags      = 0x3  → bit0 PACK_DIR_ENCRYPTED（目录加密!）
                        bit1 PACK_REL_FILEBASE
+24  u64  file_base  = 112（相对 pck_start）
+32  u64  dir_ofs    （相对 pck_start）
+40  64B  保留
```

`flags bit0 = 1` 说明目录结构被 AES 加密。用 gdsdecomp（GDRE Tools）直接打开 → 解析失败，确认是**自编模板 + 全加密导出**（官方模板不含密钥，出题人自己编译了带密钥的模板）。

---

## 0x03 第二关：从 exe 里挖出 32 字节 AES 密钥

### 知识点

Godot 的 PCK 加密密钥在**模板编译期**通过环境变量 `SCRIPT_AES256_ENCRYPTION_KEY` 注入，生成 `script_encryption_key.gen.cpp` 里的 `uint8_t script_encryption_key[32]`，链接进模板 exe 的 `.data` 段。**所以密钥必然以 32 字节裸二进制躺在 exe 里。**

### 方法 A：Ghidra 静态（标准姿势）

1. 搜字符串 `Can't open encrypted pack directory.`（`file_access_pack.cpp` 的报错）
2. 交叉引用 → `try_open_pack()` → 附近把 32 字节数组逐字节拷进 Vector 的循环，其源操作数地址即密钥数组
3. dump 32 字节：`f956ea30749ff095e35fcf5cb074d6e821782ca8072568624d9d3cb595564ce8`

### 方法 B：MD5 预言机暴力扫描（自动化姿势，0.3 秒）

加密 blob 自带两层可验证性：**明文结构已知**（目录明文首条目 = `u32 路径长度` + `.` 开头的 ASCII 路径）+ **头部自带明文 MD5**。于是把 `.data` 段每个偏移的 32 字节都当密钥试：

```python
for i in range(len(data_section)):
    key = data_section[i:i+32]
    pt0 = AES.new(key, AES.MODE_CFB, iv=iv, segment_size=128).decrypt(ct[:16])
    slen, = struct.unpack('<I', pt0)          # 首 u32 应是小值
    if 4 <= slen <= 512 and pt0[4:5] == b'.': # 路径以 '.' 开头
        # 候选！全量解密做 MD5 终审
        ...验证 md5(明文) == blob 里存的 md5 → 命中
```

实测：密钥位于 `.data+0xb220`，45601 次尝试、**0.3 秒**命中。（完整实现见附录 `solve.py`。）

---

## 0x04 第三关：解密 PCK，还原全部资源

### FileAccessEncrypted blob 格式（无 magic 变体）

```
+0  16B  明文 MD5
+16  u64  明文长度 plain_len
+24 16B  IV
+40  ..   AES-256-CFB128 密文（长度 = ceil(plain_len/16)*16）
```

加密算法：mbedtls `aes_crypt_cfb128`，即标准 **AES-256-CFB/128bit**。PyCryptodome 对应 `AES.MODE_CFB, segment_size=128`。

### 两个格式陷阱（踩过才知道）

1. **目录区**：`pck_start+dir_ofs` 处先有 4 字节明文 `file_count`，**然后**才是加密 blob。目录明文是连续条目：`u32(路径长+padding) | 路径(含\0填充) | u64 ofs(相对file_base) | u64 size | 16B md5 | u32 flags(bit0=文件已加密)`。
2. 条目里的 **`size` 是明文长度**，不是磁盘 blob 长度（blob 实长 = `40 + ceil(size/16)*16`，按它去切片才能解出完整密文）。

### 结果

12 个文件全部解出（目录 md5 与文件 md5 双重校验通过）：

```
.godot/exported/133200997/export-...-main.scn   749 B   主场景（二进制资源）
.godot/imported/icon.svg-....ctex              1414 B
project.binary                                  422 B   = project.godot 二进制化
scripts/main.gdc                               7318 B   ★ 游戏逻辑（编译版）
scripts/flag_manager.gdc                       1598 B   ★ flag 铸造（编译版）
...（icon、remap、uid_cache 等共 12 个）
```

> 捷径：GDRE Tools（gdsdecomp）GUI 里 "Recover" 并填入密钥 hex 也能一键解包加密 PCK；本节脚本是不依赖第三方 GUI 的纯手工路线。
>
> **实测（2026-11 补充）**：GDRE v2.7.4（截稿最新版）直接打开加密 exe 时，即使填对密钥也报 `Incorrect encryption key`——它不支持 `encrypt_directory`（目录级加密），该报错信息有误导性。可靠姿势是先用 `tools/repack_plain.py` 把解密后的资源重打包成无加密 PCK，再交给 GDRE：
> ```
> python tools/repack_plain.py snake50000.exe f956ea...ce8 rebuilt_plain.pck
> GDRE → Recover → 选 rebuilt_plain.pck   ← 无需密钥，实测正常恢复出全部源码
> ```

---

## 0x05 第四关（上）：从 .gdc 挖出铸造算法

`.gdc` 是 GDScript 二进制 token 格式：`"GDSC"` + `u32 版本` + **zstd 压缩流**。

```python
import zstandard
tokens = zstandard.ZstdDecompressor().stream_reader(open('flag_manager.gdc','rb').read()[12:]).read()
```

解压后字符串常量池明文可读（`strings` 即可）：

```
flag{Y0u_W1sh_It_W4s_Th1s_E4sy}     ← 诱饵
5n4k3G0dTc7f9                        ← 字母表(14字符)
G0d0t / -5n4k3 / -c7f2025 / -x7k9m2  ← KEY 的四个分片(源码里拼接存储)
flag{ / integrity check failed ...
```

数值常量同样在池子里，直接暴露算法身份：

| 常量 | 含义 |
|---|---|
| `2166136261` (0x811C9DC5) + `16777619` (0x01000193) | **FNV-1a 32bit 指纹**（offset basis + prime） |
| 移位 `13 / 17 / 5` | **xorshift32** 标准参数 |
| `24` | flag 长度 FLAG_LEN |

想要完整源码，把解密后的 `.gdc` 丢给 **gdsdecomp/GDRE Tools** 反编译，得到原始 GDScript：

```gdscript
# flag_manager.gd（节选）
func _key() -> String:
    return "G0d0t" + "-5n4k3" + "-c7f2025" + "-x7k9m2"   # 拼出 KEY

func _mint() -> String:            # 到达 50000 分时现场铸造
    var s := _fnv1a(_key())        # KEY --FNV-1a--> 32bit 种子
    var out := ""
    for _i in FLAG_LEN:            # 24 轮
        s = _xs(s)                 # xorshift32
        out += ALPHABET[s % ALPHABET.length()]   # %14 映射到 14 字符字母表
    return "flag{" + out + "}"
```

`main.gdc` 侧确认：`TARGET_SCORE = 50000`、胜利时 `flag_manager.reveal(_score)` 先过反作弊再 `_mint()`，且 flag 直接写进剪贴板。

---

## 0x06 第四关（下）：离线复现，拿到 flag

不需要再碰游戏——算法自包含，12 行 Python：

```python
ALPHABET = "5n4k3G0dTc7f9"
KEY = "G0d0t" + "-5n4k3" + "-c7f2025" + "-x7k9m2"

def fnv1a(t):
    h = 2166136261
    for b in t.encode(): h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h

def xs(s):
    s ^= (s << 13) & 0xFFFFFFFF; s &= 0xFFFFFFFF
    s ^= s >> 17
    s ^= (s << 5) & 0xFFFFFFFF;  s &= 0xFFFFFFFF
    return s

s, out = fnv1a(KEY), ""
for _ in range(24):
    s = xs(s); out += ALPHABET[s % 14]
print("flag{" + out + "}")
```

输出：

```
flag{7544nnfn55dn9f9T5df503fn}
```

---

## 0x07 备选路线（也通，但更累）

| 路线 | 做法 | 评价 |
|---|---|---|
| 改 PCK 重打包 | 解密 → 改 `main.gd` 的 `TARGET_SCORE` → 重编译/重打包 → 重新加密目录和文件 → 嵌回 exe 尾部（修 pck_size） | 可行，但要复刻导出器全部格式细节；跑游戏吃 3 颗拿真 flag |
| 运行时 hook | x64dbg 断在 AES key expansion 或 dump `script_encryption_key` 内存；或 hook `reveal()` 返回值 | 只解决密钥，后半段一样要逆 |
| 游戏内 bot | 写 Godot 外挂自动寻路 5000 颗 | 理论可行，数小时级，还得绕反作弊的时间戳校验（真吃满则天然合法）——最"正义"但最慢 |

离线复算是设计上的**最短路径**：反作弊把"游戏内作弊"的成本抬得比"读懂算法"更高。

---

## 0x08 出题人后记：防线与攻破点复盘

设计的四道防线 vs 实际攻破情况：

| 防线 | 预期 | 实际 |
|---|---|---|
| 自编模板 + PCK 全加密（目录+所有文件 AES） | 挡 gdsdecomp 一键反编译 | ✅ 有效，但密钥明躺 `.data`，MD5 预言机 **0.3s** 自动搜出 |
| flag 动态铸造，二进制零 flag 痕迹 | 挡 `strings` 搜 flag | ✅ 有效（加密层内确实搜不到） |
| KEY 分片存储 | 挡直接搜完整 KEY | ⚠️ 部分有效——zstd 常量池里四个分片裸奔，拼接顺序肉眼可猜 |
| 反作弊（分数-次数-时间戳三重校验） | 挡改内存/改存档 | ✅ 有效，成功把解法推向逆向路线 |
| 数值常量（FNV/xorshift 参数） | 算法指纹 | ❌ 失效——常量池明文，`0x811C9DC5+0x01000193` 是 FNV-1a 的活招牌 |

**若加强（下个版本）**：
1. `_mint()` 改自定义字节码 VM 解释执行（常量池不再直出算法）
2. 密钥白盒化 / 密钥拆分混淆 + 运行时合成，废掉预言机扫描（让 MD5 校验首块过滤失效）
3. 把诱饵 flag 与真 flag 的铸造路径做成同构双分支，增加静态分析歧义

## 0x09 附录

### 环境要求

```
python -m pip install pycryptodome zstandard
```

### 完整解题脚本 solve.py（密钥扫描 + PCK 解密 + 落盘）

见 `tools/solve.py`，用法：

```
python solve.py snake50000.exe            # 自动扫密钥并解出全部文件到 solve_out/
python solve.py snake50000.exe --key f956ea30...   # 已知密钥时跳过扫描
```

实测输出（86MB exe 全程 < 1 秒）：

```
[+] PCK: v3 godot 4.5.1 flags=0x3 @0x5054200 size=13964
[*] 扫描段 .data (723456 bytes) ...
[+] 密钥命中 @ .data+0xb220: f956ea30...ce8  (45601 次尝试, 0.3s)
[+] 目录解密成功（12 个文件, 836 字节明文）
    [ENC]✓ scripts/flag_manager.gdc (1598 B)
    [ENC]✓ scripts/main.gdc (7318 B)
    ...
[+] 全部文件已解出 -> solve_out/
```

### flag 复算

见 0x06 代码，或仓内 `tools/compute_flag.py`（等价实现）。
