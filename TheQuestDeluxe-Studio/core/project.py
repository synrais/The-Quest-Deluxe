"""The editor's model of a quest pack: everything in memory, saved back in the pack's own format
(engine/packio.py), only the parts that changed."""
from __future__ import annotations

import ast
import io
import os
import re
import shutil

from engine import packio
from engine.pack import PACKS_DIR, base_of, sprite_files, sprite_find

TABLES = {'items': 'items.json', 'creatures': 'creatures.json', 'spells': 'spells.json',
          'classes': 'classes.json', 'skills': 'skills.json'}
TEXTS = {'talk': 'talk.txt', 'stories': 'stories.txt', 'questions': 'questions.txt'}
LAYERS = ('floor', 'wall', 'item', 'mon', 'gold', 'deco')          # a square's fields, in Grid order
SIZE = packio.MAP_SIZE

LEVEL_SCRIPT = '''"""Level {n} events. See docs/EVENTS.md for the handlers and what they can use."""

START = (5, 5)                      # where the hero arrives
STORIES = []                        # story screens shown before the level
SHOPS = {{}}                          # screen (column, row) -> shop number (levels/{n}/shops/<k>.txt)
'''
COMMON_SCRIPT = '''"""Events that run on every level. See docs/EVENTS.md."""
'''


class Grid:
    """A level's 100 x 100 squares: grid[x][y] = [floor, wall, item, creature, gold, deco], 1-based."""

    def __init__(self, rows=None):
        self.sq = [[[1, 0, 0, 0, 0, 0] for _ in range(SIZE + 1)] for _ in range(SIZE + 1)]
        for x, y, fl, wa, it, mo, go, de in rows or ():
            if 1 <= x <= SIZE and 1 <= y <= SIZE:
                self.sq[x][y] = [fl, wa, it, mo, go, de]

    def get(self, x, y) -> list:
        return self.sq[x][y]

    def rows(self):
        """File order: x outer, y inner, as the original writes its maps."""
        for x in range(1, SIZE + 1):
            for y in range(1, SIZE + 1):
                fl, wa, it, mo, go, de = self.sq[x][y]
                yield x, y, fl, wa, it, mo, go, de


class Project:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.quest = packio.read_json(self.path('quest.json'))
        self.tables, self.comments = {}, {}
        for key, f in TABLES.items():
            data = packio.read_json(self.path(f))
            self.tables[key] = data[key]
            self.comments[key] = data.get('_comment', '')
        self.tiles = packio.read_json(self.path('tiles.json'))
        self.texts = {k: packio.read_text(self.path('text', f)) for k, f in TEXTS.items()}
        self.scripts = {0: packio.read_text(self.path('levels', 'common.qs'))}
        self.shops: dict[int, dict[int, str]] = {}
        for n in range(1, self.levels + 1):
            self.scripts[n] = self._read_or(self.path('levels', str(n), 'script.qs'), LEVEL_SCRIPT.format(n=n))
            d = self.path('levels', str(n), 'shops')
            self.shops[n] = {int(f[:-4]): packio.read_text(os.path.join(d, f))
                             for f in sorted(os.listdir(d)) if f.endswith('.txt')} if os.path.isdir(d) else {}
        self.grids: dict[int, Grid] = {}
        self.pictures: dict[str, bytes | None] = {}    # sprites/<folder>/<id>.png waiting to be saved (None: delete)
        self.dirty: set = set()           # what save() must write: 'quest', table keys, 'tiles', ('map', n), ...

    # ── paths and basics ────────────────────────────────────────────────────
    def path(self, *parts) -> str:
        return os.path.join(self.root, *parts)

    @staticmethod
    def _read_or(path, default):
        return packio.read_text(path) if os.path.exists(path) else default

    @property
    def name(self) -> str:
        return os.path.basename(self.root)

    @property
    def levels(self) -> int:
        return int(self.quest.get('levels', 0))

    def grid(self, n: int) -> Grid:
        if n not in self.grids:
            p = self.path('levels', str(n), 'map.txt')
            self.grids[n] = Grid(packio.read_map(p) if os.path.exists(p) else None)
        return self.grids[n]

    def touch(self, what):
        self.dirty.add(what)

    # ── names for the palette and the status bar ───────────────────────────
    def entries(self, layer: str) -> list[dict]:
        """What can go in a layer: [{'id', 'name'}], sorted by id."""
        if layer == 'floor':
            rows = self.tiles.get('floors', [])
        elif layer == 'wall':
            rows = self.tiles.get('walls', [])
        elif layer == 'deco':
            rows = self.tiles.get('decos', [])
        elif layer == 'item':
            rows = [r for r in self.tables['items'] if r['id']]
        elif layer == 'mon':
            rows = self.tables['creatures']
        else:
            rows = []
        return sorted(rows, key=lambda r: r['id'])

    def item_type(self, v: int) -> str:
        return next((r.get('type', '') for r in self.tables['items'] if r['id'] == v), '') if v else ''

    def name_of(self, layer: str, v: int) -> str:
        if not v:
            return ''
        if layer == 'gold':
            return f'{v} gold'
        for r in self.entries(layer):
            if r['id'] == v:
                return r.get('name') or f'#{v}'
        return f'#{v}'

    SPRITE_DIRS = {'floor': 'floors', 'wall': 'walls', 'deco': 'decos', 'item': 'items', 'mon': 'creatures',
                   'bag': 'bag', 'spell': 'spells'}

    @property
    def base(self) -> str | None:
        """The pack its pictures fall back on (quest.json `base`), or None: this pack holds all its own."""
        return base_of(self.quest, self.root)

    def sprite_file(self, *parts) -> str | None:
        """A picture's file under sprites/: this pack's own, else the base's."""
        return sprite_find(self.root, self.base, *parts)

    def sprite(self, layer: str, v: int) -> str | None:
        return self.sprite_file(self.SPRITE_DIRS[layer], f'{v}.png')

    # ── pictures (kept here until saved) ────────────────────────────────────
    def picture(self, folder: str, v: int):
        """A picture as a pygame Surface (a pending one first), or None."""
        import pygame
        rel = f'{folder}/{v}.png'
        if rel in self.pictures:
            data = self.pictures[rel]
            return None if data is None else pygame.image.load(io.BytesIO(data), 'x.png')
        p = self.sprite_file(folder, f'{v}.png')
        return pygame.image.load(p) if p else None

    def picture_ids(self, folder: str) -> list[int]:
        """The numbers of the pictures in a sprite folder, those still to be saved included, those deleted not."""
        ids = set()
        ids |= {int(n[:-4]) for n in sprite_files(self.root, self.base, folder) if n.endswith('.png') and n[:-4].lstrip('-').isdigit()}
        for rel, data in self.pictures.items():
            head, _, name = rel.partition('/')
            if head == folder and name.endswith('.png') and name[:-4].lstrip('-').isdigit():
                (ids.add if data is not None else ids.discard)(int(name[:-4]))
        return sorted(ids)

    def set_picture(self, folder: str, v: int, surface):
        """Store a picture (a pygame Surface), or delete it (None), when the pack is saved."""
        import pygame
        rel = f'{folder}/{v}.png'
        if surface is None:
            self.pictures[rel] = None
        else:
            buf = io.BytesIO()
            pygame.image.save(surface, buf, 'x.png')
            self.pictures[rel] = buf.getvalue()
        self.touch('pictures')

    # ── where things are used (before deleting them) ────────────────────────
    def uses(self, kind: str, v: int) -> list[str]:
        """Where an item ('item') or a creature ('mon') appears: maps, shops, classes, loot, scripts."""
        out = []
        field = {'item': 2, 'mon': 3}[kind]
        for n in range(1, self.levels + 1):
            g = self.grid(n)
            count = sum(1 for x in range(1, SIZE + 1) for y in range(1, SIZE + 1) if g.sq[x][y][field] == v)
            if count:
                out.append(f'level {n} map: {count} square{"s" if count > 1 else ""}')
        word = re.compile(rf'(?<![\w.]){v}(?![\w.])')
        if kind == 'item':
            for n, shops in self.shops.items():
                for k, text in shops.items():
                    if str(v) in text.split():
                        out.append(f'level {n} shop {k}')
            for c in self.tables['classes']:
                if v in c.get('bag', {}).values():
                    out.append(f'class {c["name"]}: starting item')
            for c in self.tables['creatures']:
                if any(r[2] == 'item' and r[3] == v for r in c.get('loot', [])) or \
                        v in c.get('drop_on_level', {}).values():
                    out.append(f'creature {c["id"]} {c.get("name", "")}: loot')
        else:
            for c in self.tables['spells']:
                if c.get('creature') == v:
                    out.append(f'spell {c["name"]}: summons it')
            for c in self.tables['creatures']:
                if v in (c.get('raises_dead'), c.get('reveals_as'), c.get('hides_as')) or \
                        (c.get('deceiver') or {}).get('becomes') == v:
                    out.append(f'creature {c["id"]} {c.get("name", "")}')
        for n, text in self.scripts.items():
            if word.search(text):
                out.append(f'{"common" if n == 0 else f"level {n}"} script mentions {v}')
        return out

    def next_id(self, table: str, start: int) -> int:
        used = {r['id'] for r in self.tables[table]}
        v = start
        while v in used or v in (999, 1000):
            v += 1
        return v

    # ── level settings (the constants at the top of a level's script) ───────
    def constant(self, level: int, name: str, default=None):
        for line in self.scripts.get(level, '').splitlines():
            m = re.match(rf'^{name}\s*=\s*(.*)$', line)
            if m:
                value = m.group(1).split('#')[0].strip()
                try:
                    return ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    return default
        return default

    def remove_constant(self, level: int, name: str):
        lines = self.scripts.get(level, '').split('\n')
        kept = [line for line in lines if not re.match(rf'^{name}\s*=', line)]
        if kept != lines:
            self.scripts[level] = '\n'.join(kept)
            self.touch(('script', level))

    def set_constant(self, level: int, name: str, value, comment: str = ''):
        """Rewrite (or add) `NAME = value` at the top of the level's script, keeping its comment."""
        text = self.scripts.get(level, '')
        lines = text.split('\n')
        new = f'{name} = {value!r}'
        for i, line in enumerate(lines):
            m = re.match(rf'^{name}\s*=\s*(.*)$', line)
            if m:
                if '#' in m.group(1):                          # keep the comment where it was
                    col = line.index('#')
                    lines[i] = f'{new:<{col}}{line[col:]}' if len(new) < col else f'{new}  {line[col:]}'
                else:
                    lines[i] = new
                break
        else:
            # after the last top-level setting, or after the docstring
            at = 0
            for i, line in enumerate(lines):
                if re.match(r'^[A-Z_]+\s*=', line):
                    at = i + 1
            if at == 0:
                at = _after_docstring(lines)
            lines.insert(at, f'{new:<35} # {comment}'.rstrip() if comment else new)
        self.scripts[level] = '\n'.join(lines)
        self.touch(('script', level))

    # ── levels ──────────────────────────────────────────────────────────────
    def add_level(self) -> int:
        n = self.levels + 1
        self.quest['levels'] = n
        self.grids[n] = Grid()
        self.scripts[n] = LEVEL_SCRIPT.format(n=n)
        self.shops[n] = {}
        self.dirty |= {'quest', ('map', n), ('script', n)}
        return n

    def remove_last_level(self):
        n = self.levels
        if n <= 1:
            return
        self.quest['levels'] = n - 1
        for d in (self.grids, self.scripts, self.shops):
            d.pop(n, None)
        self.dirty.add('quest')
        self.dirty.add(('drop_level', n))

    # ── saving ──────────────────────────────────────────────────────────────
    def save(self):
        for what in sorted(self.dirty, key=str):
            if what == 'quest':
                packio.write_json(self.path('quest.json'), self.quest)
            elif what in TABLES:
                packio.write_table(self.path(TABLES[what]), what, self.tables[what], self.comments[what])
            elif what == 'tiles':
                packio.write_text(self.path('tiles.json'), packio.tiles_text(self.tiles))
            elif what in TEXTS:
                packio.write_text(self.path('text', TEXTS[what]), self.texts[what])
            elif isinstance(what, tuple) and what[0] == 'map' and what[1] in self.grids:
                packio.write_text(self.path('levels', str(what[1]), 'map.txt'),
                                  packio.map_text(self.grids[what[1]].rows()))
            elif isinstance(what, tuple) and what[0] == 'script' and what[1] in self.scripts:
                p = self.path('levels', 'common.qs') if what[1] == 0 else \
                    self.path('levels', str(what[1]), 'script.qs')
                packio.write_text(p, self.scripts[what[1]])
            elif isinstance(what, tuple) and what[0] == 'shops' and what[1] in self.shops:
                d = self.path('levels', str(what[1]), 'shops')
                if os.path.isdir(d):
                    shutil.rmtree(d)
                for k, text in self.shops[what[1]].items():
                    packio.write_text(os.path.join(d, f'{k}.txt'), text)
            elif what == 'pictures':
                for rel, data in self.pictures.items():
                    p = self.path('sprites', *rel.split('/'))
                    if data is None:
                        if self.base and os.path.exists(os.path.join(self.base, 'sprites', *rel.split('/'))):
                            os.makedirs(os.path.dirname(p), exist_ok=True)       # the base has it: an empty file hides it here
                            open(p, 'wb').close()
                        elif os.path.exists(p):
                            os.remove(p)
                    else:
                        os.makedirs(os.path.dirname(p), exist_ok=True)
                        with open(p + '.tmp', 'wb') as fh:
                            fh.write(data)
                        os.replace(p + '.tmp', p)
                self.pictures.clear()
            elif isinstance(what, tuple) and what[0] == 'drop_level' and what[1] > self.levels:
                shutil.rmtree(self.path('levels', str(what[1])), ignore_errors=True)
        self.dirty.clear()

    # ── new packs ───────────────────────────────────────────────────────────
    @staticmethod
    def create(dest: str, template: str, blank: bool) -> 'Project':
        """A new pack at dest: a copy of template (a pack folder), or with blank=True, the template's
        things (items, creatures, spells, classes, tiles, pictures, fonts) but one empty level, no
        story and only the everyday chatter. A new pack fixes all the original's bugs unless its template
        says otherwise (the Quest tab unticks them)."""
        if os.path.exists(dest):
            raise FileExistsError(dest)
        shipped = os.path.abspath(template) == os.path.abspath(PACKS_DIR + os.sep + 'TheQuest')
        shutil.copytree(template, dest, ignore=shutil.ignore_patterns('sprites') if shipped else None)
        q = packio.read_json(os.path.join(dest, 'quest.json'))
        if shipped:
            q['base'] = 'TheQuest'                      # a new pack holds only its own pictures: the rest come from the locked game
        if 'fixes' not in q or shipped:
            q.setdefault('fixes', True)
            packio.write_json(os.path.join(dest, 'quest.json'), q)
        if blank:
            for f in os.listdir(os.path.join(dest, 'levels')):
                p = os.path.join(dest, 'levels', f)
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            packio.write_text(os.path.join(dest, 'levels', 'common.qs'), COMMON_SCRIPT)
            talk = packio.read_text(os.path.join(dest, 'text', 'talk.txt'))
            keep = []
            for block in _talk_blocks(talk):
                if block.split()[0] == '0':
                    keep.append(block)
            packio.write_text(os.path.join(dest, 'text', 'talk.txt'), '\n'.join(keep) + '\n')
            packio.write_text(os.path.join(dest, 'text', 'stories.txt'), '')
            q = packio.read_json(os.path.join(dest, 'quest.json'))
            q.update({'title': os.path.basename(dest), 'author': '', 'year': None, 'levels': 1, 'first_level': 1})
            q.pop('map_fixes', None)                     # its levels are gone
            packio.write_json(os.path.join(dest, 'quest.json'), q)
            p = Project(dest)
            p.grids[1] = Grid()
            p.dirty |= {('map', 1), ('script', 1)}
            p.save()
            return p
        return Project(dest)


def _after_docstring(lines) -> int:
    """The line after a module docstring (and one blank line), else 0."""
    if not lines or not lines[0].lstrip().startswith(('"""', "'''")):
        return 0
    q = lines[0].lstrip()[:3]
    if lines[0].count(q) >= 2:
        return 2 if len(lines) > 1 and not lines[1].strip() else 1
    for i in range(1, len(lines)):
        if q in lines[i]:
            return i + 2 if i + 1 < len(lines) and not lines[i + 1].strip() else i + 1
    return 0


def _talk_blocks(text: str) -> list[str]:
    """talk.txt split into its entries (each ends with ';')."""
    out, cur = [], []
    for line in text.split('\n'):
        if not line.strip() and not cur:
            continue
        cur.append(line)
        if line.rstrip().endswith(';'):
            out.append('\n'.join(cur))
            cur = []
    return out


def packs() -> list[str]:
    return sorted(d for d in os.listdir(PACKS_DIR) if os.path.exists(os.path.join(PACKS_DIR, d, 'quest.json')))
