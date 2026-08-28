#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T1 · ChnSentiCorp 中文情感二分类 —— LLM-as-Judge 评分脚本（Judge 分 10）

按 rubric.md 五维度对 Agent 产出的 t1_error_analysis.md 打分，评分者固定为
OfoxAI 平台的 anthropic/claude-sonnet-5，temperature = 0（写死，不可调），
以保证四条件（A/B/C/D）× 10 遍使用同一 Judge 同一口径，跨条件可比。

评分维度与权重（与 rubric.md 一致）：
    报告完整性        30%
    统计指标计算正确性 30%
    格式规范性        20%
    可读性            10%
    分析深度          10%
各维度按百分制打分，加权得 judge_total（0-100），折算 judge_score_10（0-10）
即项目档案口径下的 Judge 分（自动分 90 + Judge 分 10 = 100）。

用法：
    export OFOXAI_API_KEY="sk-..."
    python3 judge.py --run-dir runs/t1/A/run_001
    python3 judge.py --run-dir runs/t1/A/run_001 runs/t1/A/run_002
    python3 judge.py --batch "runs/t1/*/run_*"

输出（每个 run-dir 下）：
    t1_judgescore.json   评分结果
    t1_judge_log.json    完整 prompt 与 response（审计用）
"""

import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUBRIC_PATH = os.path.join(HERE, 'rubric.md')
DEFAULT_RUN_DIR = os.path.join(HERE, 'runs', 't1', 'run_default')

# ---- API 配置（写死，不可通过参数修改）
BASE_URL = 'https://api.ofox.ai/v1'
MODEL = 'anthropic/claude-sonnet-5'
TEMPERATURE = 0
MAX_TOKENS = 4000
API_KEY_ENV = 'OFOXAI_API_KEY'

RETRY_TIMES = 3
RETRY_INTERVAL = 2
REQUEST_TIMEOUT = 180

# ---- 维度定义（与 rubric.md 权重一致）
DIMENSIONS = (
    ('report_integrity', '报告完整性', 0.30),
    ('statistical_correctness', '统计指标计算正确性', 0.30),
    ('format_compliance', '格式规范性', 0.20),
    ('readability', '可读性', 0.10),
    ('analysis_depth', '分析深度', 0.10),
)

SYSTEM_PROMPT = "You are a strict grader. Output ONLY a valid JSON object. No markdown code blocks. No explanation text before or after. No comments inside JSON."


def read_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def build_user_prompt(rubric_text, report_text, autoscore_text):
    parts = [
        '## 评分标准（rubric.md 全文）\n\n%s' % rubric_text,
        '## 待评报告（t1_error_analysis.md 全文）\n\n%s' % report_text,
    ]
    if autoscore_text is not None:
        parts.append(
            '## 自动评分结果（t1_autoscore.json，供维度 1/2/3 核查取用）\n\n```json\n%s\n```'
            % autoscore_text)
    else:
        parts.append(
            '## 自动评分结果\n\n本次运行未提供 t1_autoscore.json。'
            '维度 2（统计指标计算正确性）无独立重算数据可比对，'
            '请依据报告自身呈现的指标是否完整、内部是否自洽给分，并在 reason 中说明该限制。')
    parts.append('请严格按 system prompt 规定的 JSON 结构输出评分结果。')
    return '\n\n---\n\n'.join(parts)


def call_api(system_prompt, user_prompt, api_key):
    """调用 OfoxAI Chat Completions；失败重试 RETRY_TIMES 次。

    返回 (content, error)：成功时 error 为 None，失败时 content 为 None。
    """
    messages = []
    if system_prompt and system_prompt.strip():
        messages.append({'role': 'system', 'content': system_prompt})
    messages.append({'role': 'user', 'content': user_prompt})

    payload = json.dumps({
        'model': MODEL,
        'temperature': TEMPERATURE,
        'max_tokens': MAX_TOKENS,
        'messages': messages,
    }).encode('utf-8')
    url = BASE_URL.rstrip('/') + '/chat/completions'
    last_err = None
    for attempt in range(1, RETRY_TIMES + 1):
        req = urllib.request.Request(url, data=payload, method='POST', headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % api_key,
        })
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                body = json.loads(resp.read().decode('utf-8'))
            return body['choices'][0]['message']['content'], None
        except urllib.error.HTTPError as e:
            detail = ''
            try:
                detail = e.read().decode('utf-8', 'replace')[:500]
            except Exception:
                pass
            last_err = 'HTTP %s: %s' % (e.code, detail or e.reason)
        except Exception as e:
            last_err = '%s: %s' % (type(e).__name__, e)
        if attempt < RETRY_TIMES:
            print('    [WARN] 第 %d/%d 次调用失败（%s），%d 秒后重试'
                  % (attempt, RETRY_TIMES, last_err, RETRY_INTERVAL))
            time.sleep(RETRY_INTERVAL)
    return None, last_err


def extract_json(text):
    """从模型回复中提取 JSON 对象；容忍 ```json 包裹与前后缀文字。"""
    stripped = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', text.strip())
    for candidate in (stripped, text):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    # 括号配对扫描，取第一个完整 JSON 对象
    start = text.find('{')
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start:i + 1])
                        if isinstance(data, dict):
                            return data
                    except Exception:
                        break
        start = text.find('{', start + 1)
    return None


def clamp_score(v):
    try:
        s = float(v)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, s))


def parse_scores(content):
    """解析各维度分数。

    返回 (scores, reasons, reasoning, parse_status)：
    parse_status ∈ {'OK', 'REGEX_FALLBACK', 'PARSE_ERROR'}。
    """
    scores, reasons = {}, {}
    data = extract_json(content)
    if data:
        for key, _, _ in DIMENSIONS:
            item = data.get(key)
            if isinstance(item, dict):
                scores[key] = clamp_score(item.get('score'))
                reasons[key] = item.get('reason')
            else:
                scores[key] = clamp_score(item)
                reasons[key] = None
        if all(scores[k] is not None for k, _, _ in DIMENSIONS):
            return scores, reasons, data.get('reasoning'), 'OK'

    # 正则兜底：按维度英文键名就近抓取数字
    for key, _, _ in DIMENSIONS:
        if scores.get(key) is not None:
            continue
        m = re.search(r'["\']?%s["\']?\s*[:：].{0,80}?(\d+(?:\.\d+)?)' % key,
                      content, re.IGNORECASE | re.DOTALL)
        scores[key] = clamp_score(m.group(1)) if m else None
        reasons.setdefault(key, None)

    if all(scores[k] is not None for k, _, _ in DIMENSIONS):
        return scores, reasons, None, 'REGEX_FALLBACK'
    return scores, reasons, None, 'PARSE_ERROR'


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def judge_one(run_dir, rubric_text, api_key, repeat=3):
    """对单个 run-dir 评分 repeat 次，取中位数；返回结果 dict。"""
    run_dir = os.path.abspath(run_dir)
    print('-' * 60)
    print('评分: %s  (repeat=%d, 取中位数)' % (run_dir, repeat))

    report_path = os.path.join(run_dir, 't1_error_analysis.md')
    autoscore_path = os.path.join(run_dir, 't1_autoscore.json')

    if not os.path.isdir(run_dir):
        print('    [ERROR] run-dir 不存在')
        return {'run_dir': run_dir, 'status': 'DIR_NOT_FOUND', 'judge_total': None}

    if not os.path.exists(report_path):
        print('    [ERROR] t1_error_analysis.md 不存在')
        return {'run_dir': run_dir, 'status': 'REPORT_MISSING', 'judge_total': None}

    report_text = read_text(report_path)
    autoscore_text = None
    if os.path.exists(autoscore_path):
        try:
            autoscore_text = json.dumps(json.load(open(autoscore_path, encoding='utf-8')),
                                        ensure_ascii=False, indent=2)
        except Exception as e:
            print('    [WARN] t1_autoscore.json 解析失败：%s' % e)

    # 构造 prompt（复用现有 grading_header 逻辑）
    grading_header = """You are grading an NLP benchmark report. Read the rubric and report below, then output ONLY a JSON object.

REQUIRED KEYS (exactly these 6 keys):
  "report_integrity": <integer 0-100>,
  "statistical_correctness": <integer 0-100>,
  "format_compliance": <integer 0-100>,
  "readability": <integer 0-100>,
  "analysis_depth": <integer 0-100>,
  "reasoning": "<brief summary under 100 chars>"

RULES:
- Output valid JSON only. No markdown code blocks. No text before or after.
- Each score must be an integer between 0 and 100.
- Do NOT use nested objects like {"score": 85}. Just use the integer directly.

SCORING GUIDE (be discriminating, use full 0-100 range):
- 90-100: Exceptional. Report exceeds requirements in depth, insight, and clarity.
- 75-89: Good. Report is complete, accurate, and well-organized, with meaningful analysis.
- 50-74: Acceptable. Report covers basics but lacks depth, insight, or polish.
- 25-49: Poor. Report is incomplete, superficial, or has significant errors.
- 0-24: Very poor. Report is nearly empty, missing, or fundamentally wrong.

IMPORTANT: 
- A report that merely lists errors without insightful categorization or actionable suggestions should score 50-69, NOT 70+.
- A report with thorough error taxonomy, representative cases, and concrete improvement plans should score 75+.
- Distinguish carefully between "has content" (50-69) and "has quality" (75+).

EXAMPLE:
{"report_integrity":85,"statistical_correctness":90,"format_compliance":80,"readability":75,"analysis_depth":70,"reasoning":"Good report"}

Now grade:"""

    user_prompt = grading_header + "\n\n=== RUBRIC ===\n" + rubric_text + "\n\n=== REPORT ===\n" + report_text
    if autoscore_text:
        user_prompt += "\n\n=== AUTOSCORE ===\n" + autoscore_text

    # 多次评分
    all_scores = []  # [{dim1: s1, dim2: s2, ...}, ...]
    all_logs = []
    all_statuses = []

    for i in range(1, repeat + 1):
        print('    [第 %d/%d 次评分]' % (i, repeat))
        content, err = call_api(SYSTEM_PROMPT, user_prompt, api_key)

        log = {
            'attempt': i,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'response': content,
            'api_error': err,
        }

        if not content or not content.strip():
            log['parse_status'] = 'API_ERROR'
            all_logs.append(log)
            all_statuses.append('API_ERROR')
            all_scores.append({k: None for k, _, _ in DIMENSIONS})
            continue

        scores, reasons, reasoning, status = parse_scores(content)
        log['parse_status'] = status
        log['parsed_scores'] = scores
        all_logs.append(log)
        all_statuses.append(status)

        if scores:
            all_scores.append({k: scores.get(k, None) for k, _, _ in DIMENSIONS})
        else:
            all_scores.append({k: None for k, _, _ in DIMENSIONS})

    # 保存所有原始日志
    for i, log in enumerate(all_logs, 1):
        write_json(os.path.join(run_dir, 't1_judge_log_%03d.json' % i), log)

    # 计算中位数（忽略 None）
    import statistics
    final_scores = {}
    final_reasons = {}
    for key, label, weight in DIMENSIONS:
        vals = [s[key] for s in all_scores if s.get(key) is not None]
        if vals:
            final_scores[key] = round(statistics.median(vals), 2)
        else:
            final_scores[key] = None

    # 取 reasoning：用中位数对应那次，或最后一次有 reasoning 的
    reasoning = None
    for log in all_logs:
        if log.get('response'):
            d = extract_json(log['response'])
            if d and 'reasoning' in d:
                reasoning = d['reasoning']
                break

    # 计算总分
    total = 0.0
    valid_dims = 0
    dimensions = {}
    for key, label, weight in DIMENSIONS:
        s = final_scores.get(key)
        if s is not None:
            total += s * weight
            valid_dims += 1
        dimensions[key] = {
            'label': label,
            'score': s,
            'max': 100,
            'weight': weight,
            'raw_scores': [round(sc[key], 2) if sc.get(key) is not None else None for sc in all_scores],
        }

    result = {
        'task': 'T1',
        'run_dir': run_dir,
        'judge_model': MODEL,
        'temperature': TEMPERATURE,
        'repeat': repeat,
        'score_source': 'median_of_%d' % repeat,
        'dimensions': dimensions,
        'judge_total': round(total, 2) if valid_dims == len(DIMENSIONS) else None,
        'judge_score_10': round(total / 10.0, 2) if valid_dims == len(DIMENSIONS) else None,
        'reasoning': reasoning,
        'status': 'OK' if all(s == 'OK' or s == 'REGEX_FALLBACK' for s in all_statuses) else 'PARTIAL_ERROR',
    }

    write_json(os.path.join(run_dir, 't1_judgescore.json'), result)

    print('    中位数结果:')
    for key, label, weight in DIMENSIONS:
        d = dimensions[key]
        raw = d['raw_scores']
        print('    %-22s %5s / 100  (原始: %s)' % (
            label,
            '—' if d['score'] is None else '%.0f' % d['score'],
            str(raw)))
    print('    Judge 合计: %.2f / 100  ->  Judge 分: %.2f / 10   [%s]'
          % (result['judge_total'] or 0, (result['judge_score_10'] or 0), result['status']))
    return result


def main():
    ap = argparse.ArgumentParser(
        description='T1 LLM-as-Judge 评分（Claude Sonnet 5 via OfoxAI，temperature=0）')
    ap.add_argument('--run-dir', nargs='+', default=[DEFAULT_RUN_DIR],
                    help='Agent 产出目录，可传多个（默认 runs/t1/run_default）')
    ap.add_argument('--batch', nargs='+', default=None,
                    help='通配符批量模式，如 --batch "runs/t1/*/run_*"')
    ap.add_argument('--rubric', default=DEFAULT_RUBRIC_PATH,
                    help='rubric 文件路径（默认 judge.py 同目录 rubric.md）')
    ap.add_argument('--repeat', type=int, default=3,
                    help='每个 run 评分次数，取中位数（默认 3）')
    args = ap.parse_args()

    api_key = os.environ.get(API_KEY_ENV, '').strip()
    if not api_key:
        print('[FATAL] 未设置环境变量 %s' % API_KEY_ENV)
        print('        请先执行：export %s="sk-..."' % API_KEY_ENV)
        sys.exit(2)

    rubric_path = os.path.abspath(args.rubric)
    if not os.path.exists(rubric_path):
        print('[FATAL] rubric 文件不存在：%s' % rubric_path)
        sys.exit(2)
    rubric_text = read_text(rubric_path)

    if args.batch:
        run_dirs = []
        for pattern in args.batch:
            matched = [p for p in sorted(glob.glob(pattern)) if os.path.isdir(p)]
            if not matched:
                print('[WARN] 通配符无匹配目录：%s' % pattern)
            run_dirs.extend(matched)
    else:
        run_dirs = list(args.run_dir)

    if not run_dirs:
        print('[FATAL] 没有待评分的 run-dir')
        sys.exit(2)

    print('=' * 60)
    print('T1 LLM-as-Judge  |  模型: %s  |  temperature: %d' % (MODEL, TEMPERATURE))
    print('rubric: %s' % rubric_path)
    print('待评分 run 数: %d' % len(run_dirs))

    results = []
    for rd in run_dirs:
        try:
            results.append(judge_one(rd, rubric_text, api_key, args.repeat))
        except Exception as e:
            print('    [ERROR] 未预期异常，跳过该 run：%s: %s' % (type(e).__name__, e))
            results.append({'run_dir': os.path.abspath(rd), 'judge_total': None,
                            'status': 'UNEXPECTED_ERROR', 'error': str(e)})

    print('=' * 60)
    ok = [r for r in results if r.get('judge_total') is not None]
    print('汇总：%d/%d 成功' % (len(ok), len(results)))
    for r in results:
        t = r.get('judge_total')
        print('  %-8s %s  %s' % (
            r.get('status', '—'),
            '   —  ' if t is None else '%6.2f' % t,
            r['run_dir']))
    if ok:
        avg = sum(r['judge_total'] for r in ok) / len(ok)
        print('  成功项 judge_total 均值: %.2f / 100（Judge 分 %.2f / 10）'
              % (avg, avg / 10.0))
    print('=' * 60)


if __name__ == '__main__':
    main()
