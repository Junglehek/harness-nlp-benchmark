#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T1 数据准备脚本：从 ChnSentiCorp 源数据生成
  1) fixtures/t1_gold.json         —— gold 标签（评分用，Agent 不可见）
  2) <run-root>/workspace/input/t1_input.json —— Agent 输入（不含 gold）
并在每次运行前重置 <run-root>/workspace/。

用法：
    python3 prepare_workspace.py \
        --source ../../../../eval_datasets/chnsenticorp/ChnSentiCorp_htl_all.csv \
        --run-root ../../runs/t1/A/rep1
（两个参数均有默认值；--run-root 按条件/遍数传入以隔离各次运行）
"""

import argparse
import csv
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SOURCE = os.path.normpath(os.path.join(
    HERE, '../../../../eval_datasets/chnsenticorp/ChnSentiCorp_htl_all.csv'))
DEFAULT_RUN_ROOT = os.path.normpath(os.path.join(HERE, '../runs/t1/run_default'))
GOLD_PATH = os.path.join(HERE, 't1_gold.json')


def read_rows(path):
    """多编码尝试读取 CSV 行。"""
    for enc in ('utf-8-sig', 'utf-8', 'gb18030', 'gbk'):
        try:
            with open(path, 'r', encoding=enc, newline='') as f:
                return [r for r in csv.reader(f) if r and any(c.strip() for c in r)]
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise SystemExit('[FATAL] 无法识别源文件编码：%s' % path)


def parse_label(v):
    v = str(v).strip()
    if v in ('0', '1'):
        return int(v)
    low = v.lower()
    if low in ('neg', 'negative', '负面'):
        return 0
    if low in ('pos', 'positive', '正面'):
        return 1
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default=DEFAULT_SOURCE, help='ChnSentiCorp 源 CSV')
    ap.add_argument('--run-root', default=DEFAULT_RUN_ROOT, help='本次运行根目录')
    args = ap.parse_args()

    if not os.path.exists(args.source):
        raise SystemExit('[FATAL] 源文件不存在：%s' % args.source)
    rows = read_rows(args.source)
    if len(rows) < 2:
        raise SystemExit('[FATAL] 源文件数据行不足')

    # 跳过表头（首行无法解析为标签则视为表头）
    if parse_label(rows[0][0]) is None and parse_label(rows[0][-1]) is None:
        data_rows = rows[1:]
    else:
        data_rows = rows

    # 自动定位 label 列（首列或末列，前 20 行抽样判定）
    sample = data_rows[:20]

    def col_all_label(idx):
        vals = [parse_label(r[idx]) for r in sample if len(r) > idx]
        return bool(vals) and all(v is not None for v in vals)

    n_cols = max(len(r) for r in data_rows)
    if n_cols >= 2 and col_all_label(0):
        label_col, text_col = 0, 1
    elif n_cols >= 2 and col_all_label(n_cols - 1):
        label_col, text_col = n_cols - 1, 0
    else:
        raise SystemExit('[FATAL] 无法定位 label 列，请人工检查源文件格式')

    records = []
    for r in data_rows:
        if len(r) <= max(label_col, text_col):
            continue
        lab = parse_label(r[label_col])
        text = r[text_col].strip()
        if lab is None or not text:
            continue
        records.append({'text_id': len(records) + 1,
                        'raw_text': text,
                        'gold_label': lab})
    if not records:
        raise SystemExit('[FATAL] 未解析出有效数据行')

    # ---- 写 gold（存在则校验一致性）
    gold = [{'text_id': r['text_id'], 'gold_label': r['gold_label']} for r in records]
    if os.path.exists(GOLD_PATH):
        try:
            with open(GOLD_PATH, 'r', encoding='utf-8') as f:
                old = json.load(f)
        except Exception:
            old = None
        if old != gold:
            print('[WARN] fixtures/t1_gold.json 与源数据不一致，已按源数据覆盖'
                  '（请确认源数据未变更，否则影响跨条件可比性）')
    with open(GOLD_PATH, 'w', encoding='utf-8') as f:
        json.dump(gold, f, ensure_ascii=False, indent=2)

    # ---- 重置并生成 workspace（输入不含 gold）
    ws = os.path.join(args.run_root, 'workspace')
    if os.path.exists(ws):
        shutil.rmtree(ws)
    os.makedirs(os.path.join(ws, 'input'), exist_ok=True)
    inputs = [{'text_id': r['text_id'], 'raw_text': r['raw_text']} for r in records]
    input_path = os.path.join(ws, 'input', 't1_input.json')
    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(inputs, f, ensure_ascii=False, indent=2)

    n_pos = sum(1 for r in records if r['gold_label'] == 1)
    print('OK: 共 %d 条（正 %d / 负 %d）' % (len(records), n_pos, len(records) - n_pos))
    print('gold -> %s' % GOLD_PATH)
    print('input(无gold) -> %s' % input_path)


if __name__ == '__main__':
    main()
