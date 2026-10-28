# -*- coding: utf-8 -*-
"""Validate an exam JSON before rendering it into a single HTML file.

Usage:
    python scripts/validate_exam.py data/sample_exam.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

GAP_RE = re.compile(r"\{\{(\d+)\}\}")


def norm(text: str) -> str:
    """Normalize gap tokens to one character so quotes keep stable offsets."""
    return GAP_RE.sub(lambda m: chr(0xE000 + int(m.group(1))), text)


def parts(phrase: str) -> list[str]:
    return [p.strip() for p in phrase.split("...") if p.strip()]


def add(errors, message):
    errors.append(message)


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    section_ids = set()
    question_ids = set()
    for section in data.get("sections", []):
        sid = section.get("id")
        if not sid:
            add(errors, "section missing id")
            continue
        if sid in section_ids:
            add(errors, f"duplicate section id: {sid}")
        section_ids.add(sid)
        kind = section.get("kind")
        if kind not in {"reading", "seven", "cloze", "grammar"}:
            add(errors, f"{sid}: unknown kind {kind!r}")

        passage_blocks = section.get("passage", {}).get("blocks", [])
        blocks = {b.get("id"): b.get("text", "") for b in passage_blocks if b.get("kind") != "figure"}
        if not blocks and not any(b.get("kind") == "figure" for b in passage_blocks):
            add(errors, f"{sid}: no passage blocks")
        for b in passage_blocks:
            if b.get("kind") == "figure":
                if not str(b.get("src", "")).startswith("data:image/"):
                    add(errors, f"{sid}/figure {b.get('id')}: src must be an inline data:image URI")
                if not b.get("alt"):
                    add(errors, f"{sid}/figure {b.get('id')}: alt text is required")

        questions = section.get("questions", [])
        if not questions:
            add(errors, f"{sid}: no questions")
        qids = [str(q.get("id")) for q in questions]
        for qid in qids:
            if qid in question_ids:
                add(errors, f"duplicate question id: {qid}")
            question_ids.add(qid)

        option_bank = {o["key"]: o["text"] for o in section.get("optionBank", [])}
        for q in questions:
            qid = str(q.get("id"))
            qlabel = f"{sid}/Q{qid}"
            options = {o["key"]: o["text"] for o in q.get("options", [])}
            notes = q.get("optionNotes", {})
            answer = str(q.get("answer", ""))
            if kind in {"reading", "cloze"}:
                if len(options) != 4:
                    add(errors, f"{qlabel}: expected 4 options, got {len(options)}")
                if answer not in options:
                    add(errors, f"{qlabel}: answer {answer!r} not in options")
                for k in notes:
                    if k not in options:
                        add(errors, f"{qlabel}: optionNotes key {k!r} not an option")
            elif kind == "seven":
                if options:
                    add(errors, f"{qlabel}: seven-choice should not have per-question options")
                if answer not in option_bank:
                    add(errors, f"{qlabel}: answer {answer!r} not in option bank")
                for k in notes:
                    if k not in option_bank:
                        add(errors, f"{qlabel}: optionNotes key {k!r} not in option bank")
            elif kind == "grammar":
                if options:
                    add(errors, f"{qlabel}: grammar should not have options")
                if not answer:
                    add(errors, f"{qlabel}: empty grammar answer")

            if not q.get("evidence"):
                add(errors, f"{qlabel}: no evidence")
            for ev in q.get("evidence", []):
                bid = ev.get("block")
                quote = ev.get("quote", "")
                if bid not in blocks:
                    add(errors, f"{qlabel}/{ev.get('id')}: unknown block {bid!r}")
                    continue
                if norm(quote) not in norm(blocks[bid]):
                    add(errors, f"{qlabel}/{ev.get('id')}: quote not found in {bid}")
                supports = ev.get("supports", [])
                refutes = ev.get("refutes", [])
                valid_keys = set(option_bank if kind == "seven" else options)
                for key in supports + refutes:
                    if key not in valid_keys:
                        add(errors, f"{qlabel}/{ev.get('id')}: unknown option key {key!r}")

            for link in q.get("links", []):
                key = link.get("optionKey")
                otext = options.get(key, option_bank.get(key, ""))
                if not otext:
                    add(errors, f"{qlabel}: link optionKey {key!r} has no matching option")
                    continue
                for p in parts(link.get("optionPhrase", "")):
                    if p not in otext:
                        add(errors, f"{qlabel}: option phrase {p!r} not found in option {key}")
                source = link.get("sourcePhrase", "")
                if not parts(source):
                    add(errors, f"{qlabel}: empty sourcePhrase")
                # The source phrase may be spread over one or more evidence quotes
                # inside the same block.  Check against the union of the question's
                # evidence text and the whole block.
                ev_text = "\n".join(e.get("quote", "") for e in q.get("evidence", []))
                for p in parts(source):
                    if p not in ev_text and not any(p in t for t in blocks.values()):
                        add(errors, f"{qlabel}: source phrase {p!r} not found in passage/evidence")

        # gap coverage
        if kind in {"seven", "cloze", "grammar"}:
            all_text = "\n".join(blocks.values())
            found = GAP_RE.findall(all_text)
            if len(found) != len(set(found)):
                add(errors, f"{sid}: duplicate gap token(s)")
            expected = set(qids)
            actual = set(found)
            if expected != actual:
                add(errors, f"{sid}: gap mismatch; questions={sorted(expected)} tokens={sorted(actual)}")

        for v in section.get("vocab", []):
            bid = v.get("block")
            if bid not in blocks:
                add(errors, f"{sid}/vocab {v.get('id')}: unknown block {bid!r}")
                continue
            ctx = v.get("context", "")
            if norm(ctx) not in norm(blocks[bid]):
                add(errors, f"{sid}/vocab {v.get('id')}: context not found in {bid}")
            if v.get("word", "") not in ctx:
                add(errors, f"{sid}/vocab {v.get('id')}: word not in context")

        for c in section.get("complex", []):
            bid = c.get("block")
            if bid not in blocks:
                add(errors, f"{sid}/complex {c.get('id')}: unknown block {bid!r}")
                continue
            if norm(c.get("quote", "")) not in norm(blocks[bid]):
                add(errors, f"{sid}/complex {c.get('id')}: quote not found in {bid}")

    if data.get("meta", {}).get("answerSource") == "inferred":
        # Not an error: the UI must surface this.
        pass
    return errors


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    data = json.loads(args.path.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        print(f"FAIL: {len(errors)} error(s)")
        for e in errors:
            print(" -", e)
        return 1
    secs = data.get("sections", [])
    qcount = sum(len(s.get("questions", [])) for s in secs)
    print(f"OK: {len(secs)} sections, {qcount} questions")
    for s in secs:
        print(f"  {s['id']:<10} {len(s.get('questions', [])):>2} questions  {s.get('pages','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
