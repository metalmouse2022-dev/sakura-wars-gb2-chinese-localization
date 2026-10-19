# -*- coding: utf-8 -*-
"""
Sakura Taisen GB2 - 一键全量汉化构建脚本 (Build All)
流程:
1. 执行 inject_fixed2.py: 注入主剧情 1~14 章 (12x12/16x16 字体)、高清标题、起名界面
2. 执行 inject_dungeon.py: 注入 8x8 xiaodianzhen-8px 简体字库与地下城/出击剧情
3. 校验并生成最终产物 outputs/Sakura Taisen GB2 - Chinese_Fixed.gbc
"""
import os
import sys
import subprocess
import hashlib

def run_step(desc, script_name):
    print(f"\n{'=' * 60}")
    print(f">> [STEP] {desc} ({script_name})")
    print(f"{'=' * 60}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    res = subprocess.run([sys.executable, script_name], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if res.returncode != 0:
        print(f"[FAIL] 步骤失败: {script_name}")
        print(res.stderr)
        sys.exit(1)
    else:
        print(res.stdout)
        print(f"[OK] 步骤完成: {desc}")

def main():
    print("=" * 60)
    print("【樱花大战GB2 闪电作战 - 一键全量汉化 ROM 构建】")
    print("=" * 60)

    os.makedirs("outputs", exist_ok=True)

    # 步骤 1: 主剧情与核心系统注入
    run_step("主剧情 1~14 章、标题、起名界面注入", "inject_fixed2.py")

    # 步骤 2: 地下城与出击 8x8 简体管线注入
    run_step("8x8 小点阵字体与出击剧情注入", "inject_dungeon.py")

    out_rom = "outputs/Sakura Taisen GB2 - Chinese_Fixed.gbc"
    if os.path.exists(out_rom):
        with open(out_rom, "rb") as f:
            data = f.read()
        sha256 = hashlib.sha256(data).hexdigest()
        print("\n" + "=" * 60)
        print("【构建全流程成功完成！】")
        print(f"产物路径: {out_rom}")
        print(f"文件大小: {len(data):,} 字节")
        print(f"SHA-256 : {sha256}")
        print("=" * 60)

if __name__ == "__main__":
    main()
