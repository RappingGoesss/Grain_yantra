"""Grain_yantra_1 - tiny math markup used for equations.

Syntax
  _x  or _{text}   subscript
  ^x  or ^{text}   superscript
  `text`           upright (roman) text, e.g. `rad`
  Greek letters and math symbols are written directly (π θ φ α κ Φ √ ≈ · × − ∫).

The parser returns runs: (text, style, level)
  style: 'it' (italic variable), 'rm' (upright), 'sym' (Greek / symbol)
  level: 0 normal, -1 subscript, 1 superscript
"""

import html as _html

SYMBOL_CHARS = set("αβγδεζηθικλμνξπρστυφϕχψωΓΔΘΛΞΠΣΦΨΩ−·×≈√∫≤≥±∞°∑∂≠")
FUNCTION_WORDS = ("arccos", "arcsin", "arctan", "sin", "cos", "tan", "max", "min", "ln", "exp", "sqrt", "mod")


def _classify(ch, in_group_word):
    if ch in SYMBOL_CHARS:
        return "sym"
    if ch.isalpha() and ch.isascii():
        return "rm" if in_group_word else "it"
    return "rm"


def _emit(out, text, level, force_rm=False):
    """Emit characters of text at a level; detect function words in base text."""
    i = 0
    n = len(text)
    word_group = force_rm or (level != 0 and len(text) > 1 and all(c.isalpha() or c in ",. " for c in text))
    while i < n:
        matched = False
        if level == 0 and not force_rm:
            for w in FUNCTION_WORDS:
                if text.startswith(w, i) and (i == 0 or not text[i - 1].isalpha()):
                    out.append((w, "rm", level))
                    i += len(w)
                    matched = True
                    break
        if matched:
            continue
        ch = text[i]
        out.append((ch, _classify(ch, word_group), level))
        i += 1


def parse(s):
    runs = []
    i = 0
    n = len(s)
    buf = ""
    while i < n:
        ch = s[i]
        if ch in "_^":
            if buf:
                _emit(runs, buf, 0)
                buf = ""
            level = -1 if ch == "_" else 1
            i += 1
            if i < n and s[i] == "{":
                j = s.find("}", i)
                if j < 0:
                    j = n
                grp = s[i + 1:j]
                i = j + 1
            else:
                grp = s[i:i + 1]
                i += 1
            _emit(runs, grp, level)
        elif ch == "`":
            if buf:
                _emit(runs, buf, 0)
                buf = ""
            j = s.find("`", i + 1)
            if j < 0:
                j = n
            _emit(runs, s[i + 1:j], 0, force_rm=True)
            i = j + 1
        else:
            buf += ch
            i += 1
    if buf:
        _emit(runs, buf, 0)
    # merge
    merged = []
    for t, st, lv in runs:
        if merged and merged[-1][1] == st and merged[-1][2] == lv:
            merged[-1] = (merged[-1][0] + t, st, lv)
        else:
            merged.append((t, st, lv))
    return merged


def to_html(s):
    parts = []
    for text, style, level in parse(s):
        t = _html.escape(text)
        if style == "it":
            t = "<i>" + t + "</i>"
        elif style == "sym":
            t = '<span class="m-sym">' + t + "</span>"
        if level == -1:
            t = "<sub>" + t + "</sub>"
        elif level == 1:
            t = "<sup>" + t + "</sup>"
        parts.append(t)
    return "".join(parts)


def to_plain(s):
    """Plain-text form (used for filenames / logs)."""
    out = []
    for text, style, level in parse(s):
        if level == -1:
            out.append("_" + text)
        elif level == 1:
            out.append("^" + text)
        else:
            out.append(text)
    return "".join(out)
