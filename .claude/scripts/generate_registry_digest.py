#!/usr/bin/env python3
"""Generate .claude/.scout-cache/registry-digest.md from the registry files.

The digest exists so an expensive agent can see every registry entry without
reading roughly 229,000 tokens of registry text. Two rules govern it, and the
first is the reason the mechanism exists at all:

  1. The index is COMPLETE. Every entry in every registry appears, always.
     A digest that omits a title hides exactly the entry the Data-First
     protocol exists to surface, and the architect then writes a parallel
     implementation of something that already existed.

  2. Only bodies are elided. A reader who wants one takes the file and line
     reference and reads that entry alone.

Run after editing any registry:

    py -3 .claude/scripts/generate_registry_digest.py

Exits non-zero if any emitted reference does not resolve, so a stale digest
fails loudly rather than misdirecting a reader.
"""
from __future__ import annotations

import os
import re
import sys

REG = '.claude/registries'
OUT = '.claude/.scout-cache/registry-digest.md'
DOMAINS = ['backend', 'frontend', 'data', 'trading', 'general']

BULLET = re.compile(r'^- \*\*(.+?)\*\*')          # MECHANISMS / VOCABULARY
DATED = re.compile(r'^#{2,3} (\d{4}-\d{2}-\d{2} .+)$')  # JOURNAL
HEADING = re.compile(r'^(#{2,3}) (.+)$')          # INTEGRATION


def read(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as fh:
        return fh.read().splitlines()


def entries(path, pattern, group=1):
    """Return (title, line_number) for every match, line numbers 1-based."""
    out = []
    for i, ln in enumerate(read(path), 1):
        m = pattern.match(ln)
        if m:
            out.append((m.group(group).strip(), i))
    return out


HEADING_LINE = re.compile(r'^#{1,6}\s')            # any heading ends an entry
SUB_BULLET = re.compile(r'^(\s+)[-*]\s')           # an indented bullet under an entry
JOURNAL_HEADER = re.compile(r'^###\s+(\d{4}-\d{2}-\d{2})\s+(?:—|--|-)\s+(.+?)\s*$')
TRIGGER_LINE = re.compile(r'^\s*-\s*\*\*Trigger:\*\*[ \t]*(.*?)\s*$')
SOURCE_LINE = re.compile(r'^\s*-\s*\*\*Source contract:\*\*[ \t]*(.*?)\s*$')
_UNSET_SOURCES = ('', 'none', 'n/a', 'na', 'unknown', 'tbd')


def _tier_of(line, tier):
    """The tier a heading line switches to, or the current one unchanged."""
    if line.startswith('## Universal'):
        return 'Universal'
    if line.startswith('## Project:'):
        return 'Project'
    return tier


def _tier_name(tier, per_domain):
    # An entry before any tier heading is filed as Project (what tier_split always did);
    # a per-domain file holds only Project entries.
    return 'Universal' if (tier == 'Universal' and not per_domain) else 'Project'


def entry_blocks(text, pattern, per_domain=False):
    """Every top-level entry of a registry TEXT, with its full shape.

    One dict per line matching ``pattern`` (group 1 is the title): ``title``, ``line``
    (1-based), ``tier`` (``Universal`` or ``Project``), ``text`` (the entry's own text, up to
    its first indented sub-bullet) and ``subs`` (each indented sub-bullet as ``line`` and
    ``text``, with any deeper continuation lines folded in). An entry ends at the next
    top-level match or at a heading. Takes text, never a path, so a caller that already holds
    the text (a hook) passes it through.
    """
    lines = text.splitlines()
    blocks, current, tier, sub_indent = [], None, None, None
    for i, ln in enumerate(lines, 1):
        if ln.startswith('## '):
            tier = _tier_of(ln, tier)
        m = pattern.match(ln)
        if m:
            current = {'title': m.group(1).strip(), 'line': i, 'tier': _tier_name(tier, per_domain),
                       'text': ln, 'subs': []}
            blocks.append(current)
            sub_indent = None
            continue
        if HEADING_LINE.match(ln):
            current = None
            continue
        if current is None:
            continue
        sub = SUB_BULLET.match(ln)
        if sub and (sub_indent is None or len(sub.group(1)) <= sub_indent):
            sub_indent = len(sub.group(1))
            current['subs'].append({'line': i, 'text': ln.strip()})
        elif current['subs']:
            current['subs'][-1]['text'] += '\n' + ln.strip() if ln.strip() else ''
        else:
            current['text'] += '\n' + ln
    for block in blocks:
        block['text'] = block['text'].rstrip()
    return blocks


def _source_value(raw):
    """A Source contract value: the rest of the line, backticks and padding trimmed; unset forms read empty."""
    value = raw.strip().strip('`').strip()
    if value.lower() in _UNSET_SOURCES or value.startswith('<'):
        return ''
    return value


def journal_entries(text, per_domain=False):
    """Every ``### YYYY-MM-DD — title`` entry of a journal TEXT.

    One dict per entry: ``sig`` (sha1 of ``date|title``), ``date``, ``title``, ``line``,
    ``tier`` (``## Universal`` / ``## Project:`` headings; Project before any heading or
    when ``per_domain``), ``trigger`` (lower-cased), ``source`` (the Source contract value,
    empty when unset) and ``text`` (the whole block, to the next entry or a ``##`` heading).
    """
    import hashlib
    lines = text.splitlines()
    heads, tier = [], None
    for i, ln in enumerate(lines):
        if ln.startswith('## '):
            tier = _tier_of(ln, tier)
        m = JOURNAL_HEADER.match(ln)
        if m:
            heads.append((i, m.group(1), m.group(2).strip(), _tier_name(tier, per_domain)))
    entries = []
    for n, (start, date, title, tier_name) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        for j in range(start + 1, end):
            if lines[j].startswith('## '):
                end = j
                break
        block = lines[start:end]
        trigger = source = ''
        for ln in block[1:]:
            tm = TRIGGER_LINE.match(ln)
            if tm and not trigger:
                trigger = tm.group(1).strip().lower()
            sm = SOURCE_LINE.match(ln)
            if sm and not source:
                source = _source_value(sm.group(1))
        entries.append({
            'sig': hashlib.sha1(f'{date}|{title}'.encode('utf-8', errors='ignore')).hexdigest(),
            'date': date, 'title': title, 'line': start + 1, 'tier': tier_name,
            'trigger': trigger, 'source': source, 'text': '\n'.join(block),
        })
    return entries


def tier_split(path, pattern):
    """Split a two-tier registry into (universal, project) entry lists."""
    uni, proj = [], []
    for block in entry_blocks('\n'.join(read(path)), pattern):
        (uni if block['tier'] == 'Universal' else proj).append((block['title'], block['line']))
    return uni, proj


def clean(title, limit=96):
    t = re.sub(r'\s+', ' ', title).strip()
    return t if len(t) <= limit else t[:limit - 1] + '…'


def emit_group(out, label, path, items, refs):
    if not items:
        return
    rel = path[len('.claude/'):]
    out.append(f'### {label} — `{rel}` ({len(items)} entries)')
    out.append('')
    for title, line in items:
        out.append(f'- {clean(title)} [{rel}:{line}]')
        refs.append((path, line, title))
    out.append('')


def main():
    out, refs = [], []
    out += [
        '# Registry Digest',
        '',
        'Complete index of every registry entry, with a file and line reference for each.',
        'Read an entry by opening its reference; do not read a whole registry.',
        '',
        '**Generated by** `.claude/scripts/generate_registry_digest.py`. Re-run it after editing',
        'any registry, or this file goes stale silently.',
        '',
        '**The index is never trimmed.** Every entry appears. Only bodies are elided — a digest',
        'that omitted a title would hide the very entry an architect needed to extend.',
        '',
        '---',
        '',
    ]

    # ---- MECHANISMS -------------------------------------------------------
    out += ['## Mechanisms', '']
    uni, proj = tier_split(f'{REG}/MECHANISMS.md', BULLET)
    emit_group(out, 'Universal', f'{REG}/MECHANISMS.md', uni, refs)
    if proj:
        emit_group(out, 'Project (top level)', f'{REG}/MECHANISMS.md', proj, refs)
    for d in DOMAINS:
        p = f'{REG}/MECHANISMS/{d}.md'
        emit_group(out, d.capitalize(), p, entries(p, BULLET), refs)

    # ---- VOCABULARY -------------------------------------------------------
    out += ['---', '', '## Vocabulary', '']
    uni, proj = tier_split(f'{REG}/VOCABULARY.md', BULLET)
    emit_group(out, 'Universal', f'{REG}/VOCABULARY.md', uni, refs)
    if proj:
        emit_group(out, 'Project (top level)', f'{REG}/VOCABULARY.md', proj, refs)
    for d in DOMAINS:
        p = f'{REG}/VOCABULARY/{d}.md'
        emit_group(out, d.capitalize(), p, entries(p, BULLET), refs)

    # ---- JOURNAL ----------------------------------------------------------
    out += ['---', '', '## Journal (lessons)', '']
    p = f'{REG}/JOURNAL.md'
    j = entries(p, DATED) or entries(p, BULLET)
    emit_group(out, 'Universal', p, j, refs)
    for d in DOMAINS:
        p = f'{REG}/JOURNAL/{d}.md'
        emit_group(out, d.capitalize(), p, entries(p, DATED), refs)

    # ---- INTEGRATION ------------------------------------------------------
    out += ['---', '', '## Integration surfaces', '']
    p = f'{REG}/INTEGRATION.md'
    heads = []
    for i, ln in enumerate(read(p), 1):
        m = HEADING.match(ln)
        if m:
            prefix = '' if len(m.group(1)) == 2 else '  '
            heads.append((prefix + m.group(2), i))
    emit_group(out, 'Sections', p, heads, refs)

    body = '\n'.join(out).rstrip() + '\n'
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(body)

    # ---- verification -----------------------------------------------------
    bad = []
    for path, line, title in refs:
        lines = read(path)
        if line < 1 or line > len(lines):
            bad.append((path, line, title, '<out of range>'))
            continue
        key = re.sub(r'[^a-z0-9]', '', title.lower())[:12]
        target = re.sub(r'[^a-z0-9]', '', lines[line - 1].lower())
        if key and key not in target:
            bad.append((path, line, title, lines[line - 1][:60]))

    approx_tokens = len(body) // 4
    print(f'wrote {OUT}')
    print(f'  entries indexed : {len(refs)}')
    print(f'  characters      : {len(body)}  (~{approx_tokens} tokens)')
    print(f'  bad references  : {len(bad)}')
    for p, l, t, a in bad[:10]:
        print(f'    {p}:{l} expected "{t[:40]}" got "{a}"')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
