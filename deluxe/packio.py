"""Reading and writing quest-pack files in their house style, shared by tools/make_pack.py and the
editor, so a pack saved by either comes out the same: tables with one entry per line, maps as one
square per line, text with Unix line ends."""
from __future__ import annotations

import json
import os

MAP_HEADER = '# x y floor wall item creature gold deco'
MAP_SIZE = 100


def write_text(path: str, text: str):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def read_text(path: str) -> str:
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def write_json(path: str, data):
    write_text(path, json.dumps(data, indent=1, ensure_ascii=False) + '\n')


def read_json(path: str):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def table_text(key: str, rows: list, comment: str = '') -> str:
    """{"_comment": ..., key: [one object per line]}"""
    lines = ['{' + (f'"_comment": {json.dumps(comment, ensure_ascii=False)},' if comment else ''),
             f' "{key}": [']
    lines += [' ' + json.dumps(r, ensure_ascii=False) + (',' if i < len(rows) - 1 else '') for i, r in enumerate(rows)]
    lines += [' ]', '}']
    if not comment:
        lines[0] = '{'
    return '\n'.join(lines) + '\n'


def write_table(path: str, key: str, rows: list, comment: str = ''):
    write_text(path, table_text(key, rows, comment))


def tiles_text(tiles: dict) -> str:
    """tiles.json: its comment, then floors / walls / decos with one tile per line."""
    tiles = dict(tiles)
    comment = tiles.pop('_comment', '')
    lines = [f'{{"_comment": {json.dumps(comment, ensure_ascii=False)},' if comment else '{']
    for n, (key, rows) in enumerate(tiles.items()):
        lines.append(f' "{key}": [')
        lines += ['  ' + json.dumps(r, ensure_ascii=False) + (',' if i < len(rows) - 1 else '') for i, r in enumerate(rows)]
        lines.append(' ]' + (',' if n < len(tiles) - 1 else ''))
    return '\n'.join(lines + ['}']) + '\n'


def map_text(rows) -> str:
    """rows: (x, y, floor, wall, item, creature, gold, deco) in file order."""
    return MAP_HEADER + '\n' + '\n'.join(' '.join(str(v) for v in r) for r in rows) + '\n'


def read_map(path: str) -> list[list[int]]:
    """The square lines of a map file, as lists of 8 numbers, in file order."""
    out = []
    for line in read_text(path).splitlines():
        parts = line.split()
        if parts and not parts[0].startswith('#') and len(parts) == 8:
            out.append([int(v) for v in parts])
    return out
