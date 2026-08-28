#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T1 · ChnSentiCorp 中文情感二分类 —— 自动评分脚本（Oracle，满分 90）

评分构成（与项目档案、rubric.md 一致，满分 90）：
  格式合规性 27 分（＝90×30%）：五个文件是否全部存在、可解析、字段齐全、数据类型正确
                   实现口径：每文件 6 分 = 存在且可解析 2 + 字段齐全 2 + 数据类型正确 2，
                   内部 30 分制检查后按 90% 折算为 27 分制
  准确率     63 分（＝90×70%）：accuracy × 63
                   accuracy = pred_label 与 gold_label 严格匹配（0/1 完全相等）数 / gold 总样本数
  不加分项：precision / recall / f1 与错误样本清单必须报告，但不影响自动分。

Judge 分（10 分）按 rubric.md 评定，本脚本不产生；但本脚本输出独立重算的全部
统计指标与 Agent 报告值的一致性比对（绝对误差 < 0.01 判一致，即误差 < 1%），
供 Judge 维度 2（统计指标计算正确性）直接取用。

Gold 安全：gold 标签位于 tasks/t1_chnsenticorp/fixtures/t1_gold.json，
Agent 运行期间不可接触；本脚本仅在评分阶段读取。

用法：
    python3 evaluator.py --run-dir <Agent 产出目录，默认 workspace>
    python3 evaluator.py --run-dir <Agent 产出目录> --gold <gold 文件路径>

输出：
    stdout                        评分摘要
    <run-dir>/t1_autoscore.json   完整评分与独立重算结果
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GOLD_PATH = os.path.join(HERE, 'fixtures', 't1_gold.json')

METRICS_FIELDS = ('accuracy', 'precision', 'recall', 'f1')
CONFUSION_FIELDS = ('tp_count', 'fp_count', 'fn_count', 'tn_count')


def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def is_float(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------- 格式检查

def check_classification(run_dir):
    """6 分：存在且可解析 2 + 字段齐全 2 + 类型正确 2"""
    issues = []
    path = os.path.join(run_dir, 't1_classification.json')
    if not os.path.exists(path):
        return 0.0, None, ['t1_classification.json 不存在']
    try:
        data = load_json(path)
    except Exception as e:
        return 0.0, None, ['t1_classification.json 解析失败：%s' % e]
    score = 2.0
    if not (isinstance(data, list) and data):
        issues.append('t1_classification.json 应为非空 JSON 数组')
        return score, None, issues
    miss_field = False
    bad_type = False
    for r in data:
        if not isinstance(r, dict):
            miss_field, bad_type = True, True
            break
        if not all(f in r for f in ('text_id', 'raw_text', 'pred_label')):
            miss_field = True
        pl = r.get('pred_label')
        if not (is_int(r.get('text_id')) and isinstance(r.get('raw_text'), str)
                and is_int(pl) and pl in (0, 1)):
            bad_type = True
    if not miss_field:
        score += 2.0
    else:
        issues.append('存在缺字段记录：需 text_id / raw_text / pred_label')
    if not bad_type:
        score += 2.0
    else:
        issues.append('存在类型错误记录：text_id 整数、raw_text 字符串、pred_label ∈ {0,1}')
    return score, data, issues


def check_metrics(run_dir):
    """6 分：存在且可解析 2 + 字段齐全 2 + 类型正确 2"""
    issues = []
    path = os.path.join(run_dir, 't1_metrics.json')
    if not os.path.exists(path):
        return 0.0, None, ['t1_metrics.json 不存在']
    try:
        data = load_json(path)
    except Exception as e:
        return 0.0, None, ['t1_metrics.json 解析失败：%s' % e]
    score = 2.0
    if not isinstance(data, dict):
        issues.append('t1_metrics.json 应为 JSON 对象')
        return score, None, issues
    missing = [f for f in METRICS_FIELDS if f not in data]
    bad_type = [f for f in METRICS_FIELDS
                if f in data and not (is_float(data[f]) and 0.0 <= data[f] <= 1.0)]
    if not missing:
        score += 2.0
    else:
        issues.append('缺字段：%s' % missing)
    if not bad_type:
        score += 2.0
    else:
        issues.append('类型/取值错误（应为 0-1 浮点数）：%s' % bad_type)
    return score, data, issues


def check_confusion(run_dir):
    """6 分：存在且可解析 2 + 字段齐全 2 + 类型正确 2"""
    issues = []
    path = os.path.join(run_dir, 't1_confusion_matrix.json')
    if not os.path.exists(path):
        return 0.0, None, ['t1_confusion_matrix.json 不存在']
    try:
        data = load_json(path)
    except Exception as e:
        return 0.0, None, ['t1_confusion_matrix.json 解析失败：%s' % e]
    score = 2.0
    if not isinstance(data, dict):
        issues.append('t1_confusion_matrix.json 应为 JSON 对象')
        return score, None, issues
    missing = [f for f in CONFUSION_FIELDS if f not in data]
    bad_type = [f for f in CONFUSION_FIELDS
                if f in data and not (is_int(data[f]) and data[f] >= 0)]
    if not missing:
        score += 2.0
    else:
        issues.append('缺字段：%s' % missing)
    if not bad_type:
        score += 2.0
    else:
        issues.append('类型错误（应为非负整数）：%s' % bad_type)
    return score, data, issues


def check_distribution(run_dir):
    """6 分：存在且可解析 2 + 字段齐全 2 + 类型正确 2"""
    issues = []
    path = os.path.join(run_dir, 't1_distribution.json')
    if not os.path.exists(path):
        return 0.0, None, ['t1_distribution.json 不存在']
    try:
        data = load_json(path)
    except Exception as e:
        return 0.0, None, ['t1_distribution.json 解析失败：%s' % e]
    score = 2.0
    if not isinstance(data, dict):
        issues.append('t1_distribution.json 应为 JSON 对象')
        return score, None, issues
    missing = [f for f in ('pred_positive_count', 'pred_negative_count', 'pred_positive_ratio')
               if f not in data]
    bad = False
    if 'pred_positive_count' in data and not (is_int(data['pred_positive_count'])
                                               and data['pred_positive_count'] >= 0):
        bad = True
    if 'pred_negative_count' in data and not (is_int(data['pred_negative_count'])
                                              and data['pred_negative_count'] >= 0):
        bad = True
    if 'pred_positive_ratio' in data and not (is_float(data['pred_positive_ratio'])
                                              and 0.0 <= data['pred_positive_ratio'] <= 1.0):
        bad = True
    if not missing:
        score += 2.0
    else:
        issues.append('缺字段：%s' % missing)
    if not bad:
        score += 2.0
    else:
        issues.append('类型错误：count 应为非负整数，ratio 应为 0-1 浮点数')
    return score, data, issues


def check_error_analysis(run_dir):
    """6 分：存在且可解析 2 + 章节齐全 2 + 案例数≥5 2"""
    issues = []
    path = os.path.join(run_dir, 't1_error_analysis.md')
    if not os.path.exists(path):
        return 0.0, ['t1_error_analysis.md 不存在']
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        return 0.0, ['t1_error_analysis.md 读取失败：%s' % e]
    score = 2.0
    has_cases = ('错误样本' in text) or ('错误案例' in text) or ('error case' in text.lower())
    has_types = ('错误类型' in text) or ('类型分类' in text) or ('归类' in text)
    has_advice = ('改进建议' in text) or ('改进方向' in text) or ('改进措施' in text)
    if has_cases and has_types and has_advice:
        score += 2.0
    else:
        issues.append('章节不全（需含：错误样本清单/错误类型分类/改进建议）')
    n_cases = len(re.findall(r'text_id', text, re.IGNORECASE))
    if n_cases >= 5:
        score += 2.0
    else:
        issues.append('错误案例不足 5 条（检测到 text_id 出现 %d 次）' % n_cases)
    return score, issues


# ---------------------------------------------------------------- 评分主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-dir', default='workspace',
                    help='Agent 产出目录（默认 workspace）')
    ap.add_argument('--gold', default=DEFAULT_GOLD_PATH,
                    help='gold 文件路径（默认 fixtures/t1_gold.json）')
    args = ap.parse_args()
    run_dir = os.path.abspath(args.run_dir)
    gold_path = os.path.abspath(args.gold)

    if not os.path.exists(gold_path):
        print('[FATAL] gold 文件不存在：%s' % gold_path)
        print('请先运行 fixtures/prepare_workspace.py 生成 gold，或指定 --gold 路径。')
        sys.exit(2)
    gold = load_json(gold_path)
    gold_map = {int(g['text_id']): int(g['gold_label']) for g in gold}

    # ---- 格式合规性（30 分）
    fmt_cls, cls_data, iss_cls = check_classification(run_dir)
    fmt_met, met_data, iss_met = check_metrics(run_dir)
    fmt_cfm, cfm_data, iss_cfm = check_confusion(run_dir)
    fmt_dis, dis_data, iss_dis = check_distribution(run_dir)
    fmt_err, iss_err = check_error_analysis(run_dir)
    per_file = {
        't1_classification.json': fmt_cls,
        't1_metrics.json': fmt_met,
        't1_confusion_matrix.json': fmt_cfm,
        't1_distribution.json': fmt_dis,
        't1_error_analysis.md': fmt_err,
    }
    format_score = sum(per_file.values())
    issues = iss_cls + iss_met + iss_cfm + iss_dis + iss_err

    # ---- 准确率（70 分）与独立重算
    accuracy = 0.0
    acc_score = 0.0
    recomputed = None
    notes = []
    pred_map = {}
    if cls_data:
        dup = 0
        for r in cls_data:
            if isinstance(r, dict):
                tid, pl = r.get('text_id'), r.get('pred_label')
                if is_int(tid) and is_int(pl) and pl in (0, 1):
                    if tid in pred_map:
                        dup += 1
                    pred_map[tid] = int(pl)
        if dup:
            notes.append('t1_classification.json 存在 %d 个重复 text_id，取最后一条' % dup)
        correct = sum(1 for tid, gl in gold_map.items() if pred_map.get(tid) == gl)
        accuracy = correct / len(gold_map) if gold_map else 0.0
        acc_score = accuracy * 63.0
        missing_pred = len(gold_map) - len(set(gold_map) & set(pred_map))
        if missing_pred:
            notes.append('%d 个 gold 样本无对应预测，按预测错误计' % missing_pred)
        tp = sum(1 for tid, gl in gold_map.items() if gl == 1 and pred_map.get(tid) == 1)
        fp = sum(1 for tid, gl in gold_map.items() if gl == 0 and pred_map.get(tid) == 1)
        fn = sum(1 for tid, gl in gold_map.items() if gl == 1 and pred_map.get(tid) != 1)
        tn = sum(1 for tid, gl in gold_map.items() if gl == 0 and pred_map.get(tid) != 1)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        recomputed = {
            'accuracy': accuracy,
            'precision': round(precision, 6),
            'recall': round(recall, 6),
            'f1': round(f1, 6),
            'confusion': {'tp_count': tp, 'fp_count': fp, 'fn_count': fn, 'tn_count': tn},
            'distribution': {
                'pred_positive_count': tp + fp,
                'pred_negative_count': fn + tn,
                'pred_positive_ratio': round((tp + fp) / len(gold_map), 6) if gold_map else 0.0,
            },
        }
    else:
        notes.append('t1_classification.json 不可用，accuracy 记 0')

    format_final = round(format_score * 0.9, 2)  # 30 分制 → 27 分制（90×30%）
    total = round(format_final + acc_score, 2)

    # ---- 一致性比对（供 Judge 维度 2 使用，不进自动分）
    consistency = None
    if met_data and recomputed:
        consistency = {'metrics': {}, 'confusion': {}, 'distribution': {}}
        n_ok = 0
        n_all = 0
        for f in METRICS_FIELDS:
            n_all += 1
            rep_v, rec_v = met_data.get(f), recomputed[f]
            ok = is_float(rep_v) and abs(float(rep_v) - rec_v) < 0.01
            n_ok += 1 if ok else 0
            consistency['metrics'][f] = {
                'reported': rep_v, 'recomputed': rec_v, 'consistent': ok}
        for f in CONFUSION_FIELDS:
            n_all += 1
            rep_v = cfm_data.get(f) if cfm_data else None
            rec_v = recomputed['confusion'][f]
            ok = rep_v == rec_v
            n_ok += 1 if ok else 0
            consistency['confusion'][f] = {
                'reported': rep_v, 'recomputed': rec_v, 'consistent': ok}
        if dis_data:
            for f in ('pred_positive_count', 'pred_negative_count', 'pred_positive_ratio'):
                rep_v, rec_v = dis_data.get(f), recomputed['distribution'][f]
                ok = (rep_v == rec_v) if 'count' in f else (
                    is_float(rep_v) and abs(float(rep_v) - rec_v) < 0.01)
                consistency['distribution'][f] = {
                    'reported': rep_v, 'recomputed': rec_v, 'consistent': ok}
        consistency['summary'] = '%d/%d 项一致（误差<1%% 判一致）' % (n_ok, n_all)

    result = {
        'task': 'T1',
        'dataset': 'ChnSentiCorp',
        'run_dir': run_dir,
        'gold_total': len(gold_map),
        'format_score': {'per_file': per_file, 'total_30': round(format_score, 2),
                         'final_27': format_final, 'issues': issues},
        'accuracy': round(accuracy, 6),
        'accuracy_score': round(acc_score, 2),
        'auto_total': total,
        'recomputed': recomputed,
        'consistency_check_for_judge': consistency,
        'notes': notes,
    }
    out_path = os.path.join(run_dir, 't1_autoscore.json')
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print('[WARN] 评分结果写入失败：%s' % e)

    print('=' * 60)
    print('T1 自动评分  |  gold 样本数: %d' % len(gold_map))
    print('-' * 60)
    for fn_, sc in per_file.items():
        print('  格式·%-30s %4.1f / 6' % (fn_, sc))
    print('  格式合规性合计: %.1f / 30（折算 %.1f / 27）' % (format_score, format_final))
    print('  accuracy: %.6f  ->  准确率得分: %.2f / 63' % (accuracy, acc_score))
    print('-' * 60)
    print('  自动分合计: %.2f / 90   (Judge 分 10 分另按 rubric.md 评定)' % total)
    if issues:
        print('  问题清单:')
        for it in issues:
            print('    - %s' % it)
    if consistency:
        print('  指标一致性(Judge用): %s' % consistency['summary'])
    print('=' * 60)
    print('完整结果: %s' % out_path)


if __name__ == '__main__':
    main()