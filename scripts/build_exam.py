# -*- coding: utf-8 -*-
"""Build a single, offline, touch-first HTML analysis page from exam JSON.

Usage:
    python scripts/build_exam.py data/sample_exam.json -o output/sample_exam.html
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from validate_exam import validate  # noqa: E402

GAP_RE = re.compile(r"\{\{(\d+)\}\}")
PUA_RE = re.compile(r"[\ue000-\ue0ff]")

KIND_LABEL = {
    "reading": "READING",
    "seven": "SEVEN-CHOICE",
    "cloze": "CLOZE",
    "grammar": "GRAMMAR",
}
SELECT_LABEL = {
    "reading-a": "阅读理解A篇",
    "reading-b": "阅读理解B篇",
    "reading-c": "阅读理解C篇",
    "reading-d": "阅读理解D篇",
    "seven": "七选五",
    "cloze": "完形填空",
    "grammar": "语法填空",
}
VOCAB_TAGS = {
    "core": "核心高频",
    "polysemy": "熟词生义",
    "synonym": "同义替换",
    "phrase": "短语搭配",
    "derivation": "词性转换",
}

WORDLIST_SECTION = {
    "reading-a": "阅读A",
    "reading-b": "阅读B",
    "reading-c": "阅读C",
    "reading-d": "阅读D",
    "seven": "七选五",
    "cloze": "完形",
    "grammar": "语法",
}
# Keep the word list conservative: only core high-frequency words.
# Data may set "wordlist": true/false per vocab item.  If the field is absent,
# fall back to level=core minus technical/compound exclusions.
WORDLIST_EXCLUDE = {
    "open-air", "plant-based", "dietary", "influencers", "nutritionists",
    "jet fuel", "bio-fuel", "fossil fuels", "scaling up", "self-awareness",
    "personalized", "a fuller picture", "human chain", "gateway", "pathway",
    "temperate", "latitude", "hemisphere", "equator", "evaporation",
    "anticyclones", "deciduous", "savannas", "carnivore", "ketogenic",
    "cholesterol", "mediterranean", "aviation", "hydrothermal liquefaction",
    "circular economy",
}
REL_LABEL = {
    "synonym": "同义",
    "paraphrase": "改写",
    "antonym": "反义",
    "logic": "逻辑",
    "collocation": "搭配",
    "inference": "推断",
    "reference": "指代",
}
REL_CLASS = {
    "synonym": "",
    "paraphrase": "",
    "antonym": "is-ant",
    "logic": "is-logic",
    "collocation": "is-collocation",
    "inference": "is-inference",
    "reference": "is-logic",
}


def norm(text: str) -> str:
    return GAP_RE.sub(lambda m: chr(0xE000 + int(m.group(1))), text)


def esc(text: object) -> str:
    return html.escape(str(text), quote=False)


def attr(text: object) -> str:
    return html.escape(str(text), quote=True)


def parts(phrase: str) -> list[str]:
    return [p.strip() for p in phrase.split("...") if p.strip()]


def gap_button(n: str) -> str:
    return (
        f'<button class="gap" type="button" data-gap="{attr(n)}" '
        f'aria-label="第 {attr(n)} 空，查看解析">{esc(n)}</button>'
    )


def gap_blank(n: str) -> str:
    return f'<span class="blank" aria-label="第 {attr(n)} 空">____</span>'


def stable_link_id(qid: str, key: str, source: str) -> str:
    digest = hashlib.md5(source.encode("utf-8")).hexdigest()[:8]
    return f"{qid}-{key}-{digest}"


def render_segment(text: str, gap_mode: str = "button") -> str:
    # Keep a gap and the punctuation after it on the same line.
    text = re.sub(r"([\ue000-\ue0ff])([.,;:!?)\]])", lambda m: m.group(1) + "\u2060" + m.group(2), text)
    txt = esc(text)
    if gap_mode == "blank":
        return PUA_RE.sub(lambda m: gap_blank(str(ord(m.group(0)) - 0xE000)), txt)
    return PUA_RE.sub(lambda m: gap_button(str(ord(m.group(0)) - 0xE000)), txt)


def annotate(text: str, anns: list[dict], gap_mode: str = "button") -> str:
    if not anns:
        return render_segment(text, gap_mode)
    anns = [a for a in anns if a["start"] < a["end"]]
    if not anns:
        return render_segment(text, gap_mode)
    points = {0, len(text)}
    for a in anns:
        points.add(max(0, min(len(text), a["start"])))
        points.add(max(0, min(len(text), a["end"])))
    points = sorted(points)
    out = []
    for a, b in zip(points, points[1:]):
        if a >= b:
            continue
        active = [x for x in anns if x["start"] <= a and x["end"] >= b]
        active.sort(key=lambda x: x.get("priority", 5))
        piece = render_segment(text[a:b], gap_mode)
        for x in reversed(active):
            open_tag = x["open"]
            if 'class="lex ' in open_tag:
                marks = []
                if a == x["start"]:
                    marks.append("lex-start")
                if b == x["end"]:
                    marks.append("lex-end")
                if marks:
                    open_tag = open_tag.replace(
                        'class="lex ',
                        'class="lex ' + " ".join(marks) + " ",
                        1,
                    )
            piece = open_tag + piece + x["close"]
        for x in active:
            if x.get("after") and b == x["end"]:
                piece += x["after"]
        out.append(piece)
    return "".join(out)


def add_ann(anns, start, end, priority, open_tag, close_tag="</span>", after=""):
    if start is None or end is None or start >= end:
        return
    anns.append(
        {
            "start": start,
            "end": end,
            "priority": priority,
            "open": open_tag,
            "close": close_tag,
            "after": after,
        }
    )


def find_phrase(text: str, phrase: str) -> tuple[int, int] | None:
    p = norm(phrase)
    i = text.find(p)
    if i < 0:
        return None
    return i, i + len(p)


def block_annotations(sec: dict, block_id: str, text: str) -> list[dict]:
    anns = []
    for q in sec.get("questions", []):
        qid = str(q["id"])
        for ev in q.get("evidence", []):
            if ev.get("block") != block_id:
                continue
            rng = find_phrase(text, ev.get("quote", ""))
            if not rng:
                continue
            supports = " ".join(ev.get("supports", []))
            refutes = " ".join(ev.get("refutes", []))
            add_ann(
                anns,
                rng[0],
                rng[1],
                2,
                f'<span class="ev" data-q="{attr(qid)}" data-support="{attr(supports)}" '
                f'data-refute="{attr(refutes)}" data-ev="{attr(ev.get("id", ""))}">',
            )

        for link in q.get("links", []):
            for p in parts(link.get("sourcePhrase", "")):
                rng = find_phrase(text, p)
                if not rng:
                    continue
                link_id = stable_link_id(qid, str(link.get("optionKey")), link.get("sourcePhrase", ""))
                rel = link.get("type", "paraphrase")
                add_ann(
                    anns,
                    rng[0],
                    rng[1],
                    3,
                    f'<span class="lex lex-{attr(rel)}" data-link="{attr(link_id)}">',
                )

    for v in sec.get("vocab", []):
        if v.get("block") != block_id:
            continue
        ctx = v.get("context", "")
        rng_ctx = find_phrase(text, ctx)
        if not rng_ctx:
            continue
        word = v.get("word", "")
        wi = norm(ctx).find(word)
        if wi < 0:
            continue
        s = rng_ctx[0] + wi
        e = s + len(word)
        add_ann(
            anns,
            s,
            e,
            4,
            f'<span class="vocab" data-vocab="{attr(v.get("id", ""))}" role="button" '
            f'tabindex="0" aria-label="查看 {attr(word)} 的释义">',
        )

    for c in sec.get("complex", []):
        if c.get("block") != block_id:
            continue
        rng = find_phrase(text, c.get("quote", ""))
        if not rng:
            continue
        cid = c.get("id", "")
        add_ann(
            anns,
            rng[0],
            rng[1],
            1,
            f'<span class="cx" data-complex="{attr(cid)}" role="button" tabindex="0" '
            f'aria-label="查看长难句结构分析">',
            after=(
                f'<span class="cx-mark" data-complex="{attr(cid)}" role="button" '
                f'tabindex="0" aria-label="长难句解析">析</span>'
            ),
        )
    return anns


def render_option_text(q: dict, option: dict) -> str:
    text = norm(option.get("text", ""))
    anns = []
    for link in q.get("links", []):
        if link.get("optionKey") != option.get("key"):
            continue
        for p in parts(link.get("optionPhrase", "")):
            rng = find_phrase(text, p)
            if not rng:
                continue
            rel = link.get("type", "paraphrase")
            link_id = stable_link_id(str(q["id"]), str(option["key"]), link.get("sourcePhrase", ""))
            add_ann(
                anns,
                rng[0],
                rng[1],
                1,
                f'<span class="lex lex-{attr(rel)}" data-link="{attr(link_id)}">',
            )
    return annotate(text, anns)


def render_quote(q: dict, quote: str) -> str:
    text = norm(quote)
    anns = []
    for link in q.get("links", []):
        for p in parts(link.get("sourcePhrase", "")):
            rng = find_phrase(text, p)
            if not rng:
                continue
            rel = link.get("type", "paraphrase")
            link_id = stable_link_id(str(q["id"]), str(link.get("optionKey")), link.get("sourcePhrase", ""))
            add_ann(
                anns,
                rng[0],
                rng[1],
                1,
                f'<span class="lex lex-{attr(rel)}" data-link="{attr(link_id)}">',
            )
    return annotate(text, anns, gap_mode="blank")


def word_count(sec: dict) -> int:
    text = " ".join(b.get("text", "") for b in sec.get("passage", {}).get("blocks", []))
    text = GAP_RE.sub(" ", text)
    return len(re.findall(r"[A-Za-z][A-Za-z'’\-]*", text))


def build_passage(sec: dict) -> str:
    out = []
    for block in sec.get("passage", {}).get("blocks", []):
        kind = block.get("kind", "paragraph")
        bid = attr(block.get("id", ""))
        if kind == "figure":
            src = str(block.get("src", ""))
            if not src.startswith("data:image/"):
                continue
            alt = esc(block.get("alt", "原文图表"))
            out.append(
                f'<figure class="passage-figure" data-block="{bid}">'
                f'<img src="{attr(src)}" alt="{alt}" loading="lazy" decoding="async">'
                f'<figcaption>{alt}</figcaption></figure>'
            )
            continue
        text = norm(block.get("text", ""))
        anns = block_annotations(sec, block.get("id"), text)
        body = annotate(text, anns)
        if kind == "heading":
            out.append(f'<h3 class="heading" data-block="{bid}">{body}</h3>')
        elif kind == "bullet-heading":
            out.append(f'<div class="bullet-heading" data-block="{bid}">{body}</div>')
        elif kind == "bullet-gap":
            out.append(f'<div class="bullet-gap" data-block="{bid}">{body}</div>')
        else:
            out.append(f'<p data-block="{bid}">{body}</p>')
            if block.get("zh"):
                zh_text = re.sub(r"\{\{\d+\}\}", "", block["zh"])
                out.append(f'<div class="zh" data-zh-for="{bid}">{esc(zh_text)}</div>')
    return "\n".join(out)


def build_options(sec: dict, q: dict) -> str:
    if not q.get("options"):
        return ""
    answer = str(q.get("answer", ""))
    out = ['<div class="options">']
    for o in q["options"]:
        key = o["key"]
        active = " is-correct" if key == answer else ""
        state = "答案" if key == answer else "定位"
        out.append(
            f'<button class="option{active}" type="button" data-q="{attr(q["id"])}" '
            f'data-opt="{attr(key)}" aria-pressed="false">'
            f'<span class="opt-key">{esc(key)}</span>'
            f'<span class="opt-text">{render_option_text(q, o)}</span>'
            f'<span class="opt-state">{state}</span>'
            "</button>"
        )
    out.append("</div>")
    return "\n".join(out)


def relation_label(rel: str) -> str:
    return REL_LABEL.get(rel, rel or "关联")


def build_links(q: dict) -> str:
    links = q.get("links", [])
    if not links:
        return ""
    out = ['<div class="link-chips">']
    for link in links:
        rel = link.get("type", "paraphrase")
        cls = REL_CLASS.get(rel, "")
        key = link.get("optionKey", "")
        out.append(
            f'<button class="link-chip {cls}" type="button" data-link-jump="1" '
            f'data-q="{attr(q["id"])}" data-opt="{attr(key)}" '
            f'title="点击定位该选项的原文依据">'
            f'<span class="rel">{esc(relation_label(rel))}</span>'
            f'<span>{esc(link.get("optionPhrase", ""))}</span>'
            f'<span class="arrow">↔</span>'
            f'<span>{esc(link.get("sourcePhrase", ""))}</span>'
            "</button>"
        )
    out.append("</div>")
    return "\n".join(out)


def build_notes(sec: dict, q: dict, *, details: bool = False) -> str:
    notes = q.get("optionNotes", {})
    if not notes:
        return ""
    answer = str(q.get("answer", ""))
    rows = []
    for key in sorted(notes.keys()):
        correct = " correct" if key == answer else ""
        rows.append(
            f'<div class="note-row{correct}"><span class="note-key">{esc(key)}</span>'
            f'<span>{esc(notes[key])}</span></div>'
        )
    body = "\n".join(rows)
    if details:
        return (
            '<details class="notes"><summary>其余选项为什么不行</summary>'
            f"{body}</details>"
        )
    return f'<div class="notes">{"".join(rows)}</div>'


def build_grammar(q: dict) -> str:
    g = q.get("grammar", {})
    if not g:
        return ""
    rows = []
    for label, key in [("考点", "point"), ("线索", "cue"), ("规则", "rule")]:
        if g.get(key):
            rows.append(
                f'<div class="grammar-row"><span class="label">{label}</span>'
                f'<span class="value">{esc(g[key])}</span></div>'
            )
    trans = f'<div class="grammar-trans">{esc(g.get("translation", ""))}</div>' if g.get("translation") else ""
    return f'<div class="grammar-box">{"".join(rows)}{trans}</div>'


def build_evidence(q: dict) -> str:
    out = ['<div class="evidence-box">']
    out.append('<div class="evidence-label">原文依据</div>')
    for i, ev in enumerate(q.get("evidence", []), 1):
        quote = render_quote(q, ev.get("quote", ""))
        out.append(f'<div class="evidence-quote">“{quote}”</div>')
        if ev.get("translation"):
            out.append(f'<div class="evidence-trans">译：{esc(ev["translation"])}</div>')
        if ev.get("note"):
            out.append(f'<p class="evidence-note">{esc(ev["note"])}</p>')
    out.append(build_links(q))
    out.append("</div>")
    return "\n".join(out)


def build_question_card(sec: dict, q: dict, idx: int) -> str:
    qid = str(q["id"])
    answer = str(q.get("answer", ""))
    answer_display = esc(answer)
    answer_cls = " is-text" if sec["kind"] == "grammar" else ""
    source = q.get("answerSource", sec.get("answerSource", "inferred"))
    source_label = "答案页" if source == "key" else "AI 推断"
    conf = q.get("confidence")
    conf_txt = f" · {round(float(conf) * 100)}%" if conf is not None and source != "key" else ""
    kind = sec["kind"]

    out = [
        f'<article class="q-card" data-q="{attr(qid)}" data-answer="{attr(answer)}" id="q-{attr(qid)}">',
        '<div class="q-head">',
        f'<span class="q-num">{esc(qid)}</span>',
        f'<button class="q-reveal" type="button" data-reveal="{attr(qid)}" aria-expanded="false">显示答案</button>',
        f'<span class="q-type">{esc(q.get("typeLabel", ""))}</span>',
        f'<span class="q-answer{answer_cls}">{answer_display}</span>',
        f'<span class="q-source{" is-key" if source == "key" else ""}">{source_label}{conf_txt}</span>',
        "</div>",
        f'<h3 class="q-stem">{esc(q.get("stem", ""))}</h3>',
    ]

    if kind == "seven":
        bank = {o["key"]: o["text"] for o in sec.get("optionBank", [])}
        if answer in bank:
            out.append(
                f'<div class="q-answer-text"><b>{esc(answer)}.</b> {esc(bank[answer])}</div>'
            )
    if kind in {"reading", "cloze"}:
        out.append(build_options(sec, q))
    if kind == "grammar":
        out.append(build_grammar(q))

    out.append('<div class="q-feedback" hidden></div>')
    out.append(build_evidence(q))
    if kind == "seven":
        out.append(build_notes(sec, q, details=True))
    else:
        out.append(build_notes(sec, q))
    if q.get("takeaway"):
        out.append(
            f'<div class="takeaway"><b>方法</b>{esc(q["takeaway"])}</div>'
        )
    out.append("</article>")
    return "\n".join(out)


def build_bank(sec: dict) -> str:
    bank = sec.get("optionBank", [])
    if not bank:
        return ""
    out = ['<div class="bank">']
    out.append(
        '<div class="bank-title"><span>OPTIONS A–G</span>'
        "<span>先选答案，再逐题核对</span></div>"
    )
    for o in bank:
        out.append(
            f'<div class="bank-item">'
            f'<span class="bank-key">{esc(o["key"])}</span>'
            f'<span class="bank-text">{esc(o["text"])}</span></div>'
        )
    out.append("</div>")
    return "\n".join(out)


def build_q_index(sec: dict) -> str:
    out = ['<div class="q-index" aria-label="题目快速跳转">']
    for i, q in enumerate(sec.get("questions", [])):
        current = ' aria-current="true"' if i == 0 else ' aria-current="false"'
        out.append(
            f'<button class="q-chip" type="button" data-qjump="{attr(q["id"])}"{current}>'
            f'{esc(q["id"])}</button>'
        )
    out.append("</div>")
    return "\n".join(out)


def build_context(sec: dict) -> tuple[str, str]:
    title = sec.get("topic") or sec.get("title") or ""
    meta = f'{sec.get("genre", "")} · {sec.get("pages", "")} · 约 {word_count(sec)} 词 · {len(sec.get("questions", []))} 题'
    return esc(title), esc(meta)


def build_select(data: dict) -> str:
    rows = []
    for i, sec in enumerate(data.get("sections", [])):
        label = SELECT_LABEL.get(sec.get("id"), sec.get("label") or sec.get("title") or sec.get("id"))
        selected = " selected" if i == 0 else ""
        rows.append(f'<option value="{attr(sec.get("id", ""))}"{selected}>{esc(label)}</option>')
    return "\n".join(rows)


def vocab_question_label(sec: dict, v: dict) -> str:
    qids = []
    for q in sec.get("questions", []):
        for ev in q.get("evidence", []):
            if ev.get("block") == v.get("block"):
                qids.append(str(q.get("id")))
                break
    if not qids:
        return "本节"
    if len(qids) == 1:
        return f"Q{qids[0]}"
    try:
        nums = [int(x) for x in qids]
        if nums == list(range(min(nums), max(nums) + 1)):
            return f"Q{min(nums)}–{max(nums)}"
    except ValueError:
        pass
    return "Q" + "/".join(qids[:3]) + ("…" if len(qids) > 3 else "")


def build_wordlist(data: dict) -> str:
    return ""


def build_vocab_panel(sec: dict) -> str:
    vocab = sec.get("vocab", [])
    if not vocab:
        return ""
    rows = []
    for v in vocab:
        word = esc(v.get("word", ""))
        ipa = esc(v.get("ipa", ""))
        pos = esc(v.get("pos", ""))
        meaning = esc(v.get("meaning", ""))
        qlabel = esc(vocab_question_label(sec, v))
        beyond = " is-beyond" if v.get("level") == "beyond" else ""
        rows.append(
            f'<button class="vocab-row{beyond}" type="button" data-vocab="{attr(v.get("id", ""))}" '
            f'aria-label="查看 {attr(v.get("word", ""))} 的音标、词性和释义">'
            f'<span class="vw-main"><span class="vw-word">{word}</span>'
            f'<span class="vw-ipa">{ipa}</span><span class="vw-pos">{pos}</span></span>'
            f'<span class="vw-meaning">{meaning}</span>'
            f'<span class="vw-q">{qlabel}</span>'
            "</button>"
        )
    return f"""
<details class="vocab-panel" open>
  <summary>
    <span class="vp-title">单词清单</span>
    <span class="vp-count">{len(vocab)} 个</span>
    <span class="vp-hint">点词看音标、词性、释义</span>
  </summary>
  <div class="vocab-list">
    {''.join(rows)}
  </div>
</details>
"""


def _blocks_attr(blocks) -> str:
    vals = [str(b) for b in (blocks or []) if b]
    return f' data-blocks="{attr(",".join(vals))}"' if vals else ""


def build_vocab_tab(sec: dict) -> str:
    vocab = [
        v for v in sec.get("vocab", [])
        if v.get("level") == "core" and v.get("wordlist") is not False
    ]
    rows = []
    counts = {}
    for v in vocab:
        cat = v.get("category", "core")
        if cat not in VOCAB_TAGS:
            cat = "core"
        counts[cat] = counts.get(cat, 0) + 1
        replace = str(v.get("replace") or "").strip()
        meaning = esc(v.get("meaning", ""))
        if replace:
            meaning += f' <span class="vw-eq">= {esc(replace)}</span>'
        rows.append(
            f'<button class="vocab-row cat-{cat}" type="button" data-vocab="{attr(v.get("id", ""))}" '
            f'aria-label="查看 {attr(v.get("word", ""))} 的考点、搭配和例句">'
            f'<span class="vw-main"><span class="vw-word">{esc(v.get("word", ""))}</span>'
            f'<span class="vw-ipa">{esc(v.get("ipa", ""))}</span>'
            f'<span class="vw-pos">{esc(v.get("pos", ""))}</span></span>'
            f'<span class="vw-meaning">{meaning}</span>'
            f'<span class="vw-tag tag-{cat}">{VOCAB_TAGS[cat]}</span></button>'
        )
    if not rows:
        return '<div class="tab-empty">本篇暂无词汇表。</div>'
    summary = " · ".join(f"{VOCAB_TAGS[k]} {counts[k]}" for k in VOCAB_TAGS if counts.get(k))
    return f"""
<div class="tab-head">
  <div>
    <div class="drawer-eyebrow">VOCABULARY / 本篇词汇</div>
    <h2 class="tab-title">本篇词汇 <span class="tab-count">{len(rows)} 个</span></h2>
    <div class="tab-sub">{summary}</div>
  </div>
</div>
<div class="vocab-list tab-vocab-list">{''.join(rows)}</div>
"""


def _exam_blocks(sec: dict, point: dict) -> list:
    qmap = {str(q.get("id")): q for q in sec.get("questions", [])}
    out = []
    for qid in point.get("questions", []):
        q = qmap.get(str(qid))
        if not q:
            continue
        for ev in q.get("evidence", []):
            b = ev.get("block")
            if b and b not in out:
                out.append(b)
    return out


def build_structure_tab(sec: dict) -> str:
    st = sec.get("structure") or {}
    m = sec.get("mainIdea") or {}
    parts = st.get("parts") or []
    flow = []
    for i, part in enumerate(parts, 1):
        flow.append(
            f'<button class="structure-flow-node" type="button"{_blocks_attr(part.get("blocks"))}>'
            f'<span class="node-index">{i:02d}</span>'
            f'<span class="node-label">{esc(part.get("function", ""))}</span>'
            f'<span class="node-main">{esc(part.get("main", ""))}</span>'
            f'<span class="node-jump">定位原文 →</span></button>'
        )

    chain = []
    for i, item in enumerate(sec.get("mainIdeaChain") or [], 1):
        chain.append(
            f'<button class="idea-step" type="button"{_blocks_attr(item.get("blocks"))}>'
            f'<span class="idea-index">{i}</span>'
            f'<span class="idea-body"><span class="idea-label">{esc(item.get("label", ""))}</span>'
            f'<span class="idea-text">{esc(item.get("idea", ""))}</span></span></button>'
        )

    main_rows = [
        ("写作目的", m.get("purpose", "")),
        ("主题", m.get("theme", "")),
        ("语气", m.get("tone", "")),
    ]
    main_grid = "".join(
        f'<div class="main-cell"><span class="k">{esc(k)}</span><span class="v">{esc(v)}</span></div>'
        for k, v in main_rows if v
    )

    if not flow and not chain and not m:
        return '<div class="tab-empty">本篇暂无结构分析。</div>'
    return f"""
<div class="tab-head">
  <div>
    <div class="drawer-eyebrow">STRUCTURE / 篇章结构</div>
    <h2 class="tab-title">结构图 · 主旨链</h2>
    <div class="tab-sub">{esc(st.get("type", ""))}</div>
  </div>
</div>
<div class="structure-overview">{esc(st.get("overview", ""))}</div>
<div class="tab-hint is-strong">点按结构节点或主旨链，左侧原文会自动定位并高亮。</div>
<div class="tab-section-title">结构图</div>
<div class="structure-flow">{''.join(flow)}</div>
<div class="tab-section-title">主旨链</div>
<div class="idea-chain">{''.join(chain)}</div>
<div class="tab-section-title">一句话主旨</div>
<div class="main-statement">{esc(m.get("statement", ""))}</div>
<div class="main-grid">{main_grid}</div>
<div class="tab-hint">主旨题先看“对象 + 作者态度 + 写作目的”，不要只抓一个细节。</div>
{f'<div class="structure-note"><b>逻辑</b>{esc(st.get("logic", ""))}</div>' if st.get("logic") else ""}
{f'<div class="structure-note"><b>结构考点</b>{esc(st.get("examFocus", ""))}</div>' if st.get("examFocus") else ""}
"""


def build_exam_tab(sec: dict) -> str:
    points = []
    for p in sec.get("examPoints") or []:
        blocks = _exam_blocks(sec, p)
        words = "".join(f'<span class="exam-pill">{esc(w)}</span>' for w in (p.get("words") or []))
        qids = "".join(f'<span class="exam-pill is-q">Q{esc(q)}</span>' for q in (p.get("questions") or []))
        points.append(
            f'<button class="exam-card is-link" type="button"{_blocks_attr(blocks)}>'
            f'<span class="exam-kicker">{esc(p.get("kind", "高频考点"))}</span>'
            f'<span class="exam-title">{esc(p.get("title", ""))}</span>'
            f'<span class="exam-analysis">{esc(p.get("analysis", ""))}</span>'
            f'<span class="exam-meta">{words}{qids}</span></button>'
        )
    if not points:
        return '<div class="tab-empty">本篇暂无考点分析。</div>'
    return f"""
<div class="tab-head">
  <div>
    <div class="drawer-eyebrow">EXAM POINTS / 高频考点</div>
    <h2 class="tab-title">高频考点分析</h2>
    <div class="tab-sub">关键词 · 考法 · 原文对应</div>
  </div>
</div>
<div class="tab-hint is-strong">点按考点卡，左侧原文会自动定位并高亮。</div>
<div class="exam-list">{''.join(points)}</div>
"""


def build_section(sec: dict, idx: int) -> str:
    sid = sec["id"]
    hidden = "" if idx == 0 else " hidden"
    cards = "\n".join(build_question_card(sec, q, i) for i, q in enumerate(sec.get("questions", [])))
    bank = build_bank(sec) if sec.get("kind") == "seven" else ""
    qindex = build_q_index(sec)
    return f"""
<section class="exam-section" data-section="{attr(sid)}" data-kind="{attr(sec.get("kind", ""))}" id="{attr(sid)}"{hidden}>
  <div class="workspace">
    <button class="collapsed-rail rail-left" type="button" data-expand="passage" aria-label="展开原文">原文</button>
    <div class="pane passage-pane" aria-label="原文">
      <div class="pane-head">
        <span class="pane-label">PASSAGE / 原文</span>
        <div class="pane-tools">
          <button class="lang-toggle" type="button" aria-pressed="true">中英</button>
          <span class="pane-note">点按空格或“析”查看解析</span>
        </div>
      </div>
      <div class="passage-body is-bilingual">
        {build_passage(sec)}
      </div>
    </div>
    <div class="splitter" role="separator" aria-orientation="vertical" aria-valuemin="20" aria-valuemax="80" aria-valuenow="56" aria-label="拖动调整原文与解析比例，拖过八成自动收起" tabindex="0"></div>
    <div class="pane analysis-pane" aria-label="解析">
      <div class="analysis-tabs" role="tablist" aria-label="右栏视图">
        <button class="tab-btn is-active" type="button" role="tab" aria-selected="true" data-tab="analysis">解析</button>
        <button class="tab-btn" type="button" role="tab" aria-selected="false" data-tab="vocab">词汇</button>
        <button class="tab-btn" type="button" role="tab" aria-selected="false" data-tab="structure">结构</button>
        <button class="tab-btn" type="button" role="tab" aria-selected="false" data-tab="exam">考点</button>
      </div>
      <div class="analysis-body">
        <div class="tab-panel is-active" data-tab-panel="analysis">
          {bank}
          {qindex}
          {cards}
        </div>
        <div class="tab-panel" data-tab-panel="vocab" hidden>
          {build_vocab_tab(sec)}
        </div>
        <div class="tab-panel" data-tab-panel="structure" hidden>
          {build_structure_tab(sec)}
        </div>
        <div class="tab-panel" data-tab-panel="exam" hidden>
          {build_exam_tab(sec)}
        </div>
      </div>
    </div>
    <button class="collapsed-rail rail-right" type="button" data-expand="analysis" aria-label="展开解析">解析</button>
  </div>
</section>
"""


def build_nav(data: dict) -> str:
    out = []
    for i, sec in enumerate(data["sections"]):
        current = ' aria-current="true"' if i == 0 else ' aria-current="false"'
        count = len(sec.get("questions", []))
        out.append(
            f'<button class="section-tab" type="button" data-target="{attr(sec["id"])}"{current}>'
            f'{esc(sec.get("label", sec.get("title", sec["id"])))}'
            f'<span class="tab-count">{count}</span></button>'
        )
    return "\n".join(out)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=ROOT / "output" / "exam.html")
    ap.add_argument("--template", type=Path, default=ROOT / "templates" / "shell.html")
    ap.add_argument("--css", type=Path, default=ROOT / "assets" / "app.css")
    ap.add_argument("--js", type=Path, default=ROOT / "assets" / "app.js")
    args = ap.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        print(f"Refusing to build: {len(errors)} validation error(s)", file=sys.stderr)
        for e in errors:
            print(" -", e, file=sys.stderr)
        return 1

    meta = data.get("meta", {})
    sections_html = "\n".join(build_section(s, i) for i, s in enumerate(data["sections"]))
    select_html = build_select(data)
    wordlist_html = build_wordlist(data)
    first_context = build_context(data["sections"][0]) if data["sections"] else ("", "")

    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    css = args.css.read_text(encoding="utf-8")
    js = args.js.read_text(encoding="utf-8")
    shell = args.template.read_text(encoding="utf-8")

    replacements = {
        "{{TITLE}}": esc(meta.get("title", "英语试卷 · 交互解析")),
        "{{CONTEXT_TITLE}}": first_context[0],
        "{{CONTEXT_META}}": first_context[1],
        "{{SELECT}}": select_html,
        "{{WORDLIST}}": wordlist_html,
        "{{SECTIONS}}": sections_html,
        "{{JSON}}": data_json,
        "{{CSS}}": css,
        "{{JS}}": js,
    }
    html_out = shell
    for k, v in replacements.items():
        html_out = html_out.replace(k, v)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html_out, encoding="utf-8")
    print(f"built {args.output} ({args.output.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
