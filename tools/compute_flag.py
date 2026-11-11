#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SNAKE-500 flag 计算器（出题人专用，切勿随题目分发！）

flag 不存在于游戏二进制中，到达 500 分时由 KEY 现场计算：
    KEY --FNV-1a--> 32位种子 --xorshift32--> 字符流 --字母表--> flag

本工具与 game/scripts/flag_manager.gd 的 _mint() 完全等价，
用于：改了 KEY 之后算出最终 flag，登记到评分平台。

用法:
    python compute_flag.py            # 用游戏内置 KEY 计算
    python compute_flag.py "任意KEY"   # 试算自定义 KEY
"""
import sys

# 与 flag_manager.gd 保持一致
ALPHABET = "5n4k3G0dTc7f9"
FLAG_LEN = 24

# 游戏 _key() 里的三个碎片
KEY_PARTS = ("G0d0t", "-5n4k3", "-c7f2025", "-x7k9m2")


def fnv1a(text: str) -> int:
    h = 2166136261
    for b in text.encode("utf-8"):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def xs(s: int) -> int:
    s = (s ^ ((s << 13) & 0xFFFFFFFF)) & 0xFFFFFFFF
    s = s ^ (s >> 17)
    s = (s ^ ((s << 5) & 0xFFFFFFFF)) & 0xFFFFFFFF
    return s


def mint(key: str) -> str:
    s = fnv1a(key)
    out = []
    for _ in range(FLAG_LEN):
        s = xs(s)
        out.append(ALPHABET[s % len(ALPHABET)])
    return "flag{" + "".join(out) + "}"


def main() -> None:
    key = sys.argv[1] if len(sys.argv) > 1 else "".join(KEY_PARTS)
    print("KEY : %s" % key)
    print("FLAG: %s" % mint(key))


if __name__ == "__main__":
    main()
