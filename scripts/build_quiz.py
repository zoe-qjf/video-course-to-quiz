#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Render a self-check quiz HTML page from a questions JSON file.

Usage:
    python build_quiz.py questions.json out.html [--template <path>]

The JSON schema:

{
  "title": "价格行为 01 · 认识K线形态 · 自测题",
  "subtitle": "视频标题 · 频道 · 时长",
  "source": "题目依据视频实际讲解内容编写，时间戳对应原视频进度。",
  "knowledge_points": ["要点一", "要点二", "..."],
  "questions": [
    {"type": "judge",  "ts": "02:11", "q": "...", "options": ["正确","错误"], "answer": [1], "explain": "..."},
    {"type": "single", "ts": "04:57", "q": "...", "options": ["A","B","C","D"], "answer": [2], "explain": "..."},
    {"type": "multi",  "ts": "08:29", "q": "...", "options": ["A","B","C"], "answer": [0,2], "explain": "..."},
    {"type": "open",   "ts": "24:44", "q": "...", "sample": "参考答案全文"}
  ]
}

Answer indexes are 0-based. `explain` may contain <q>...</q> to quote the source.
"""
import argparse
import html
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(HERE, "..", "assets", "quiz_template.html")

LABEL = {"judge": "判断题", "single": "单选题", "multi": "多选题", "open": "简答题"}


def validate(data):
    qs = data.get("questions") or []
    if not qs:
        raise SystemExit("questions is empty")
    problems = []
    for i, q in enumerate(qs, 1):
        t = q.get("type")
        if t not in LABEL:
            problems.append("#%d unknown type %r" % (i, t))
            continue
        if not q.get("q"):
            problems.append("#%d missing q" % i)
        if t == "open":
            if not q.get("sample"):
                problems.append("#%d open question without sample" % i)
            continue
        opts = q.get("options") or []
        ans = q.get("answer") or []
        if not opts:
            problems.append("#%d missing options" % i)
        if not ans:
            problems.append("#%d missing answer" % i)
        if any(not isinstance(a, int) or a < 0 or a >= len(opts) for a in ans):
            problems.append("#%d answer index out of range" % i)
        if t != "multi" and len(ans) != 1:
            problems.append("#%d %s must have exactly one answer" % (i, t))
        if t == "multi" and len(ans) < 2:
            problems.append("#%d multi needs >=2 answers" % i)
        if not q.get("explain"):
            problems.append("#%d missing explain" % i)
    if problems:
        raise SystemExit("invalid questions:\n  " + "\n  ".join(problems))
    return qs


def tally(qs):
    from collections import Counter
    c = Counter(q["type"] for q in qs)
    parts = [k for k in ("judge", "single", "multi", "open") if c[k]]
    text = " · ".join("%s %d" % (LABEL[k], c[k]) for k in parts)
    objective = sum(c[k] for k in ("judge", "single", "multi"))
    return "%s（共 %d 题，客观题计分 %d）" % (text, len(qs), objective)


def build_kb(points):
    if not points:
        return "<p>（本讲未提供知识点清单）</p>"
    items = "\n".join("        <li>%s</li>" % p for p in points)
    return "      <ul>\n%s\n      </ul>" % items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("questions_json")
    ap.add_argument("out_html")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    args = ap.parse_args()

    with open(args.questions_json, encoding="utf-8") as fh:
        data = json.load(fh)
    qs = validate(data)

    with open(args.template, encoding="utf-8") as fh:
        tpl = fh.read()

    payload = json.dumps(qs, ensure_ascii=False, indent=2)
    # keep the JSON literal safe inside a <script> block
    payload = payload.replace("</", "<\\/")

    repl = {
        "{{TITLE}}": html.escape(data.get("title") or "视频课程自测题"),
        "{{SUBTITLE}}": data.get("subtitle") or "",
        "{{SOURCE}}": data.get("source") or "",
        "{{TALLY}}": tally(qs),
        "{{KB_HTML}}": build_kb(data.get("knowledge_points")),
        "{{QUESTIONS_JSON}}": payload,
    }
    for key, value in repl.items():
        tpl = tpl.replace(key, value)

    leftover = [k for k in ("{{TITLE}}", "{{QUESTION") if k in tpl]
    if leftover:
        print("[warn] unresolved placeholders: %s" % leftover)

    with open(args.out_html, "w", encoding="utf-8") as fh:
        fh.write(tpl)
    print("[ok] %d questions -> %s" % (len(qs), os.path.abspath(args.out_html)))


if __name__ == "__main__":
    main()
