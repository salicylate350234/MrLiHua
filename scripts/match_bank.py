# -*- coding: utf-8 -*-
"""Match OCR questions to a local question bank and emit a review report.

Free/local only: RapidFuzz is optional; the fallback uses difflib.
"""
from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import unicodedata
from pathlib import Path

Q_RE = re.compile(r"^\s*(\d{1,2})\s*[.．、)]\s*(.*)$")
O_RE = re.compile(r"^\s*([A-D])\s*[.．、)]\s*(.*)$")
SECTION_RE = re.compile(r"(第[一二三四五六七八九十]+部分|第[一二三四五六七八九十]+节|阅读理解|完形填空|语法填空|七选五)")


def norm(text: str) -> str:
    s = unicodedata.normalize("NFKC", str(text or "")).lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^a-z0-9]+", "", s)


def ratio(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def option_score(ocr_options: dict, bank_options: dict) -> float | None:
    if not bank_options:
        return None
    if not ocr_options:
        return 0.0
    bank = [norm(v) for v in bank_options.values() if norm(v)]
    ocr = [norm(v) for v in ocr_options.values() if norm(v)]
    if not bank or not ocr:
        return 0.0
    best = [max((difflib.SequenceMatcher(None, b, o).ratio() for o in ocr), default=0.0) for b in bank]
    coverage = sum(1 for x in best if x >= 0.55) / len(best)
    return 0.8 * (sum(best) / len(best)) + 0.2 * coverage


def segment_questions(ocr: dict) -> list[dict]:
    questions = []
    current = None
    for page in ocr.get("pages", []):
        for line in page.get("lines", []):
            text = str(line.get("text", "")).strip()
            if not text:
                continue
            qm = Q_RE.match(text)
            if qm:
                current = {
                    "number": qm.group(1),
                    "stem": qm.group(2).strip(),
                    "options": {},
                    "lastOption": None,
                    "page": page.get("source", ""),
                    "side": page.get("side", ""),
                    "conf": [float(line.get("conf", 0) or 0)],
                }
                questions.append(current)
                continue
            if current is None:
                continue
            om = O_RE.match(text)
            if len(current["options"]) >= 4:
                # A new A-D block without a recognizable question number can be
                # an orphan caused by OCR failing on the stem (e.g. Q24).  Keep
                # it so option-based recovery can still find the bank question.
                if om and om.group(1) == "A":
                    current = {
                        "number": "",
                        "stem": "",
                        "options": {},
                        "lastOption": None,
                        "page": page.get("source", ""),
                        "side": page.get("side", ""),
                        "conf": [],
                    }
                    questions.append(current)
                else:
                    continue
            if om:
                key = om.group(1)
                current["options"][key] = om.group(2).strip()
                current["lastOption"] = key
                current["conf"].append(float(line.get("conf", 0) or 0))
            elif current["lastOption"]:
                current["options"][current["lastOption"]] += " " + text
            else:
                current["stem"] += " " + text
            current["conf"].append(float(line.get("conf", 0) or 0))
    return questions


def score_candidate(q: dict, bank_q: dict) -> dict:
    stem = ratio(q.get("stem", ""), bank_q.get("stem", ""))
    opt = option_score(q.get("options", {}), bank_q.get("options", {}))
    num = 1.0 if str(q.get("number", "")) == str(bank_q.get("number", "")) else 0.0
    if not norm(q.get("stem", "")) and opt is not None:
        # Recover an OCR block whose stem was unreadable but options survived.
        score = 0.85 * opt + 0.15 * num
    else:
        score = (0.9 * stem + 0.1 * num) if opt is None else (0.68 * stem + 0.27 * opt + 0.05 * num)
    return {
        "score": round(score, 4),
        "stem": round(stem, 4),
        "options": None if opt is None else round(opt, 4),
        "number": num,
    }


def status_for(best: float, margin: float) -> str:
    if best >= 0.92 and margin >= 0.06:
        return "high"
    if best >= 0.75:
        return "medium"
    return "low"


def option_diff(q: dict, bank_q: dict) -> str:
    rows = []
    for key in "ABCD":
        a = q.get("options", {}).get(key, "")
        b = bank_q.get("options", {}).get(key, "")
        sim = round(ratio(a, b) * 100) if a or b else 0
        rows.append(
            f"<tr><td>{key}</td><td>{html.escape(a)}</td><td>{html.escape(b)}</td><td>{sim}%</td></tr>"
        )
    return "<table><thead><tr><th>键</th><th>OCR</th><th>题库</th><th>相似</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def build_report(match_data: dict) -> str:
    s = match_data["summary"]
    rows = []
    for m in match_data["matches"]:
        q = m["ocr"]
        best = m["best"]
        cls = m["status"]
        top = m["candidates"][:3]
        ocr_opts = "".join(
            f"<li><b>{html.escape(k)}.</b> {html.escape(v)}</li>" for k, v in sorted(q.get("options", {}).items())
        ) or "<li>—</li>"
        bank_opts = "".join(
            f"<li><b>{html.escape(k)}.</b> {html.escape(v)}</li>" for k, v in sorted(best.get("question", {}).get("options", {}).items())
        ) or "<li>—</li>"
        top_html = "".join(
            f"<li>{html.escape(c['question'].get('sectionLabel', ''))} Q{c['question'].get('number', '')} · "
            f"<b>{c['score'] * 100:.1f}%</b> · {html.escape(c['question'].get('stem', '')[:80])}</li>"
            for c in top
        )
        rows.append(f"""
<article class="card {cls}">
  <div class="card-head">
    <div><span class="kicker">OCR Q{html.escape(q.get('number','') or '?')}</span>
</div>
    <div class="score">{m['score'] * 100:.1f}%</div>
  </div>
  <div class="pill {cls}">{ {'high':'高匹配','medium':'需确认','low':'低匹配'}[cls] }</div>
  <div class="grid">
    <section><h3>OCR 文本</h3><p>{html.escape(q.get('stem',''))}</p><ul>{ocr_opts}</ul></section>
    <section><h3>题库最佳候选</h3><p>{html.escape(best.get('question',{}).get('stem',''))}</p><ul>{bank_opts}</ul>
      <p class="answer">答案：<b>{html.escape(str(best.get('question',{}).get('answer','')))}</b></p></section>
  </div>
  <details><summary>Top 3 候选 / 选项对照</summary><ol>{top_html}</ol>
    {option_diff(q, best.get('question', {}))}
  </details>
</article>""")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCR × 题库匹配报告</title>
<style>
:root{{--bg:#faf9f5;--ink:#1d1c19;--muted:#6f6b63;--line:#e5ded2;--coral:#cc785c;--ok:#2f6b4f;--warn:#9a6b1f;--bad:#a23d2f}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:28px 18px 60px}}h1{{font-family:Georgia,serif;font-size:30px;margin:0 0 6px}}
.sub{{color:var(--muted);margin:0 0 20px}}.summary{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}}
.box{{border:1px solid var(--line);border-radius:10px;background:#fffdf9;padding:10px 14px;min-width:120px}}
.box b{{display:block;font-size:22px}}.card{{border:1px solid var(--line);border-left:4px solid var(--coral);border-radius:10px;background:#fffdf9;padding:16px 18px;margin:14px 0}}
.card.high{{border-left-color:var(--ok)}}.card.medium{{border-left-color:var(--warn)}}.card.low{{border-left-color:var(--bad)}}
.card-head{{display:flex;justify-content:space-between;align-items:center;gap:12px}}.kicker{{font-weight:700;color:var(--coral);font-size:13px;letter-spacing:.08em}}
.score{{font-family:Georgia,serif;font-size:28px}}
.pill{{display:inline-block;border-radius:999px;padding:1px 9px;font-size:11px;margin:4px 0 8px}}.pill.high{{background:#dff0e4;color:var(--ok)}}.pill.medium{{background:#f6e7bf;color:var(--warn)}}.pill.low{{background:#f4d8d1;color:var(--bad)}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}section h3{{font-size:12px;letter-spacing:.08em;color:var(--coral);margin:6px 0}}
p{{margin:4px 0 8px}}ul{{margin:4px 0 8px;padding-left:20px}}.answer{{color:var(--ok);font-weight:600}}
details{{margin-top:10px;border-top:1px solid var(--line);padding-top:8px}}summary{{cursor:pointer;color:var(--muted);font-size:13px}}
table{{border-collapse:collapse;width:100%;font-size:12px;margin-top:8px}}th,td{{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}}
th{{color:var(--muted);font-weight:600}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>OCR × 题库匹配报告</h1>
<p class="sub">本地 OCR 只用于定位；题库候选需人工确认。匹配度高不等于 OCR 一定正确。</p>
<div class="summary">
  <div class="box"><b>{s['total']}</b>OCR 题块</div>
  <div class="box"><b>{s['high']}</b>高匹配</div>
  <div class="box"><b>{s['medium']}</b>需确认</div>
  <div class="box"><b>{s['low']}</b>低匹配</div>
</div>
{''.join(rows)}
</main></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Match OCR questions to a local bank")
    ap.add_argument("ocr")
    ap.add_argument("--bank", required=True)
    ap.add_argument("--out", default="match.json")
    ap.add_argument("--report", default="match_report.html")
    args = ap.parse_args()

    ocr = json.loads(Path(args.ocr).read_text(encoding="utf-8"))
    bank = json.loads(Path(args.bank).read_text(encoding="utf-8"))
    questions = segment_questions(ocr)
    bank_questions = bank.get("questions", [])
    matches = []
    for q in questions:
        scored = []
        for bq in bank_questions:
            s = score_candidate(q, bq)
            scored.append({**s, "question": bq})
        scored.sort(key=lambda x: x["score"], reverse=True)
        best = scored[0] if scored else None
        second = scored[1] if len(scored) > 1 else None
        margin = 1.0 if best and not second else ((best["score"] - second["score"]) if best and second else 0.0)
        # An orphan A-D block may be a section option bank (e.g. 七选五), not
        # a question.  Keep option-only recovery only when it is convincing.
        if not q.get("number") and (not best or best["score"] < 0.60):
            continue
        q.pop("conf", None)
        q.pop("lastOption", None)
        matches.append({
            "ocr": q,
            "best": best,
            "candidates": scored,
            "score": best["score"] if best else 0.0,
            "margin": round(margin, 4),
            "status": status_for(best["score"] if best else 0.0, margin),
        })
    summary = {
        "total": len(matches),
        "high": sum(1 for m in matches if m["status"] == "high"),
        "medium": sum(1 for m in matches if m["status"] == "medium"),
        "low": sum(1 for m in matches if m["status"] == "low"),
    }
    data = {
        "version": 1,
        "ocrFile": str(args.ocr),
        "bankFile": str(args.bank),
        "summary": summary,
        "matches": matches,
    }
    out = Path(args.out)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    report = build_report(data)
    rp = Path(args.report)
    rp.write_text(report, encoding="utf-8")
    print(f"matched={summary['total']} high={summary['high']} medium={summary['medium']} low={summary['low']} report={rp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
