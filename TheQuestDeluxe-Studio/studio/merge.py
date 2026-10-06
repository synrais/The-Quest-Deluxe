"""Merging one quest into another: bring creatures, items, spells, hero classes, tiles, levels, stories, chatter and settings from a source
pack into the open pack, saying beforehand what would be added, what is already the same, what would be overwritten or lost, with an
example of each. Nothing here knows about windows.

    plan = build_plan(source_project, target_project)       # what is there and how it compares
    plan.choose(kind, True)                                  # what to bring; plan.act(kind, key, 'renumber' | 'replace' | 'skip')
    warnings(plan, source, target)                           # [Warning] to show first
    apply(session, source, plan)                             # one undoable edit on the open pack; returns a Report

A thing whose number the target already uses for something different is a *clash*: it can be brought under a free number (every
place it is used, in what comes with it, follows the new number), replace the target's, or be left behind.
"""
from __future__ import annotations

import ast
import copy
import re
from dataclasses import dataclass, field

from core.project import SIZE, LEVEL_SCRIPT, Grid

from . import storytext

# kind -> (title, where its rows are, sprite folders, how a person says it)
TABLE_KINDS = {
    'creatures': ('Creatures', ('table', 'creatures'), ['creatures'], 'creature'),
    'items': ('Items', ('table', 'items'), ['items', 'bag'], 'item'),
    'spells': ('Spells', ('table', 'spells'), ['spells'], 'spell'),
    'classes': ('Hero classes', ('table', 'classes'), ['heroes'], 'hero class'),
    'skills': ('Skills and faults', ('table', 'skills'), [], 'skill'),
    'floors': ('Floors', ('tiles', 'floors'), ['floors'], 'floor'),
    'walls': ('Walls and doors', ('tiles', 'walls'), ['walls'], 'wall'),
    'decos': ('Decorations', ('tiles', 'decos'), ['decos'], 'decoration'),
}
KINDS = list(TABLE_KINDS) + ['levels', 'stories', 'talk', 'settings']
TITLES = {k: v[0] for k, v in TABLE_KINDS.items()}
TITLES.update({'levels': 'Levels (with their shops, events, stories and what people say there)', 'stories': 'Story pages',
               'talk': 'What people say (the everyday chatter)', 'settings': 'Quest settings'})
SCOPE = {'creatures': 'creatures', 'items': 'items', 'spells': 'spells', 'classes': 'classes', 'skills': 'skills',
         'floors': 'tiles', 'walls': 'tiles', 'decos': 'tiles'}
SETTING_KEYS = ['title', 'author', 'year', 'first_level', 'reclass', 'start_potions', 'story_order', 'fixes', 'mods', 'map_fixes']
RESERVED_STORIES = {0, 1, 8, 9}
LAYER_OF = {'creatures': 3, 'items': 2, 'floors': 0, 'walls': 1, 'decos': 5}


@dataclass
class Entry:
    kind: str
    key: object                        # its number in the source (a skill's key is its short name)
    name: str
    status: str                        # 'new' | 'same' | 'clash'
    mine: str = ''                     # the target's own thing under that number (a clash)
    action: str = 'add'                # 'add' | 'skip' | 'renumber' | 'replace'
    new_key: object = None
    uses: list = field(default_factory=list)       # where the target uses the thing that would be replaced


@dataclass
class Warning:
    severity: str                      # 'lost' (something of the target's goes), 'changed', 'check' (look at it afterwards), 'note'
    title: str
    detail: str


@dataclass
class Report:
    added: dict = field(default_factory=dict)      # kind -> how many
    replaced: dict = field(default_factory=dict)
    skipped: dict = field(default_factory=dict)
    first_level: int | None = None
    notes: list = field(default_factory=list)

    def summary(self) -> str:
        bits = []
        for k in KINDS:
            n, r = self.added.get(k, 0), self.replaced.get(k, 0)
            if n or r:
                bits.append(f'{TITLES[k].split(" (")[0].lower()}: {n} added' + (f', {r} replaced' if r else ''))
        return '; '.join(bits) or 'Nothing was brought over.'


class Plan:
    def __init__(self):
        self.entries: dict[str, list[Entry]] = {k: [] for k in KINDS}
        self.chosen: set[str] = set()
        self.level_picks: list[int] = []               # the source levels to bring, in order
        self.setting_picks: list[str] = []
        self.with_pictures = True

    def choose(self, kind: str, on: bool = True):
        (self.chosen.add if on else self.chosen.discard)(kind)

    def act(self, kind, key, action, new_key=None):
        e = next(e for e in self.entries[kind] if e.key == key)
        e.action = action
        if new_key is not None:
            e.new_key = new_key

    def entry(self, kind, key):
        return next((e for e in self.entries[kind] if e.key == key), None)


# ── reading both ─────────────────────────────────────────────────────────────────
def rows_of(project, kind):
    where, name = TABLE_KINDS[kind][1]
    return project.tables[name] if where == 'table' else project.tiles.get(name, [])


def _name(row, key):
    return str(row.get('name') or f'#{key}')


def _key_of(kind, row):
    return row['id']


def build_plan(src, dst) -> Plan:
    plan = Plan()
    for kind in TABLE_KINDS:
        mine = {_key_of(kind, r): r for r in rows_of(dst, kind)}
        for r in rows_of(src, kind):
            k = _key_of(kind, r)
            if k not in mine:
                e = Entry(kind, k, _name(r, k), 'new', action='add')
            elif mine[k] == r:
                e = Entry(kind, k, _name(r, k), 'same', action='skip')
            else:
                e = Entry(kind, k, _name(r, k), 'clash', mine=_name(mine[k], k), action='renumber' if kind != 'skills' else 'skip')
                if kind in LAYER_OF:
                    e.uses = _uses_in(dst, kind, k)
            plan.entries[kind].append(e)
    # stories
    mine = {s.number: s for s in storytext.stories(dst)}
    for s in storytext.stories(src):
        if s.number not in mine:
            plan.entries['stories'].append(Entry('stories', s.number, f'Story {s.number}', 'new', action='add'))
        elif mine[s.number].lines == s.lines:
            plan.entries['stories'].append(Entry('stories', s.number, f'Story {s.number}', 'same', action='skip'))
        else:
            plan.entries['stories'].append(Entry('stories', s.number, f'Story {s.number}', 'clash',
                                                 mine=(mine[s.number].lines[:1] or [''])[0][:40], action='renumber' if s.number not in RESERVED_STORIES else 'skip'))
    # chatter (level 0 talk) by (person, number)
    have = _talk_map(dst.texts['talk'])
    for (lv, npc, idx), text in _talk_map(src.texts['talk']).items():
        if lv != 0:
            continue
        key = (npc, idx)
        if (0, npc, idx) not in have:
            plan.entries['talk'].append(Entry('talk', key, text[:40], 'new', action='add'))
        elif have[(0, npc, idx)] == text:
            plan.entries['talk'].append(Entry('talk', key, text[:40], 'same', action='skip'))
        else:
            plan.entries['talk'].append(Entry('talk', key, text[:40], 'clash', mine=have[(0, npc, idx)][:40], action='skip'))
    # settings
    for k in SETTING_KEYS:
        if k in src.quest:
            same = dst.quest.get(k) == src.quest[k]
            status = 'same' if same else ('clash' if k in dst.quest else 'new')
            plan.entries['settings'].append(Entry('settings', k, k, status, mine=str(dst.quest.get(k))[:40],
                                                  action='replace' if status == 'new' else 'skip'))     # (yours are kept unless you say so)
    plan.level_picks = list(range(1, src.levels + 1))
    for n in plan.level_picks:
        plan.entries['levels'].append(Entry('levels', n, _level_title(src, n), 'new', action='add'))
    return plan


def _level_title(project, n):
    t = project.constant(n, 'TITLE', None)
    return f'{n}  {t}' if t else f'Level {n}'


def _uses_in(project, kind, key):
    out = []
    if kind in ('creatures', 'items'):
        try:
            out = project.uses('mon' if kind == 'creatures' else 'item', key)
        except Exception:                                                   # noqa: BLE001 - a hint, never a reason to stop
            out = []
    return out


# ── talk.txt ─────────────────────────────────────────────────────────────────────
def _talk_blocks(text: str) -> list:
    out, cur = [], []
    for line in text.split('\n'):
        if not line.strip() and not cur:
            continue
        cur.append(line)
        if line.rstrip().endswith(';'):
            out.append('\n'.join(cur))
            cur = []
    return out


def _talk_map(text: str) -> dict:
    out = {}
    for b in _talk_blocks(text):
        m = re.match(r'^(-?\d+)\s+(-?\d+)\s+(-?\d+)\s', b)
        if m:
            out[(int(m[1]), int(m[2]), int(m[3]))] = b.split(None, 3)[3]
    return out


# ── what a level uses ────────────────────────────────────────────────────────────
def level_usage(project, n) -> dict:
    """{'creatures': {id: squares}, 'items': {...}, 'floors': ..., 'walls': ..., 'decos': ...} for level n's map."""
    g = project.grid(n)
    out = {k: {} for k in LAYER_OF}
    for x in range(1, SIZE + 1):
        col = g.sq[x]
        for y in range(1, SIZE + 1):
            sq = col[y]
            for kind, idx in LAYER_OF.items():
                v = sq[idx]
                if v and not (kind == 'floors' and v == 0):
                    out[kind][v] = out[kind].get(v, 0) + 1
    return out


def _level_links(project, n):
    return project.constant(n, 'LINKS', {}) or {}


# ── the warnings ─────────────────────────────────────────────────────────────────
def warnings(plan: Plan, src, dst) -> list:
    out = []
    singular = {k: v[3] for k, v in TABLE_KINDS.items()}
    for kind in TABLE_KINDS:
        if kind not in plan.chosen:
            continue
        for e in plan.entries[kind]:
            if e.status == 'clash' and e.action == 'replace':
                where = ('  It is used in: ' + '; '.join(e.uses[:3]) + ('; ...' if len(e.uses) > 3 else '') + '.') if e.uses else ''
                out.append(Warning('lost', f'{singular[kind].capitalize()} {e.key} "{e.mine}" is replaced by "{e.name}"',
                                   f'Your {singular[kind]} {e.key} ("{e.mine}") is overwritten and its numbers and picture are gone '
                                   f'(Undo brings it back).{where}'))
            elif e.status == 'clash' and e.action == 'skip':
                out.append(Warning('changed', f'{singular[kind].capitalize()} {e.key} is not brought: you keep "{e.mine}"',
                                   f'The other pack\'s "{e.name}" has the same number as your "{e.mine}". Anything you bring that uses '
                                   f'{singular[kind]} {e.key} will use yours.'))
            elif e.status == 'clash' and e.action == 'renumber':
                out.append(Warning('note', f'{singular[kind].capitalize()} "{e.name}" comes in as number {e.new_key or "(a free one)"}',
                                   f'Number {e.key} is your "{e.mine}". Every place that uses it in what you bring follows the new number.'))
    if 'settings' in plan.chosen:
        for e in plan.entries['settings']:
            if e.status == 'clash' and e.action == 'replace':
                out.append(Warning('lost', f'Setting "{e.key}" is overwritten',
                                   f'Yours is {dst.quest.get(e.key)!r}; the other pack\'s is {src.quest.get(e.key)!r}.'))
    if 'stories' in plan.chosen:
        for e in plan.entries['stories']:
            if e.status == 'clash' and e.action == 'replace':
                out.append(Warning('lost', f'Story {e.key} is overwritten', f'Yours begins "{e.mine}"; it is replaced by the other pack\'s.'))
    if 'talk' in plan.chosen:
        for e in plan.entries['talk']:
            if e.status == 'clash' and e.action == 'replace':
                out.append(Warning('lost', f'What person {e.key[0]} says (number {e.key[1]}) is overwritten', f'Yours: "{e.mine}". Replaced by "{e.name}".'))
    if 'levels' in plan.chosen and plan.level_picks:
        first = dst.levels + 1
        out.append(Warning('note', f'{len(plan.level_picks)} level{"s" if len(plan.level_picks) != 1 else ""} are added after your last level',
                           f'They become levels {first} to {first + len(plan.level_picks) - 1}. Nothing of yours is changed, but the exit of '
                           f'your level {dst.levels} will now lead on into level {first}.'))
        picked = set(plan.level_picks)
        with_events = []
        for n in plan.level_picks:
            use = level_usage(src, n)
            for kind in LAYER_OF:
                for v, count in sorted(use[kind].items()):
                    e = plan.entry(kind, v)
                    if e is None:
                        mine = {r['id'] for r in rows_of(dst, kind)}
                        if v not in mine:
                            out.append(Warning('check', f'Level {n} uses {TABLE_KINDS[kind][3]} {v}, which neither pack has',
                                               f'{count} squares; they would show nothing or fail.'))
                        continue
                    name = e.name
                    if e.status == 'clash' and e.action == 'skip' and kind in LAYER_OF:
                        out.append(Warning('changed', f'Level {n}: {count} squares of {TABLE_KINDS[kind][3]} {v} will be "{e.mine}" (yours), not "{name}"',
                                           f'You chose to keep your {TABLE_KINDS[kind][3]} {v}.'))
                    elif e.status != 'same' and kind not in plan.chosen and e.status == 'new':
                        out.append(Warning('check', f'Level {n} uses {TABLE_KINDS[kind][3]} {v} "{name}", which you are not bringing',
                                           f'Your pack has no {TABLE_KINDS[kind][3]} {v}: {count} squares would show nothing or fail. Tick '
                                           f'{TITLES[kind].lower()} too.'))
            for pos, link in _level_links(src, n).items():
                tgt = link[0] if link else None
                if tgt and tgt not in picked:
                    out.append(Warning('check', f'An exit on level {n} at {pos} leads to level {tgt}, which you are not bringing',
                                       f'After the merge it would lead to your level {tgt}, if there is one.'))
            script = src.scripts.get(n, '')
            if re.search(r'^def \w+\(', script, flags=re.M):
                with_events.append(n)
    renumbered = [e for k in TABLE_KINDS for e in plan.entries[k] if e.status == 'clash' and e.action == 'renumber' and k in plan.chosen]
    if renumbered and with_events:
        out.append(Warning('check', 'Events on ' + ('level ' if len(with_events) == 1 else 'levels ') + ', '.join(map(str, with_events))
                           + ' may mention numbers that changed',
                           'A level\'s script is copied as it is. Where it names a creature, item or spell by number, check it after the merge '
                           f'(for example {renumbered[0].key} became {renumbered[0].new_key or "a free number"}).'))
    if not plan.chosen:
        out.append(Warning('note', 'Nothing is ticked', 'Tick what you want to bring over.'))
    return out


# ── numbering ────────────────────────────────────────────────────────────────────
def free_key(kind, key, taken: set):
    """The nearest free number to `key` going away from zero (999 and 1000 are the game's own)."""
    if isinstance(key, str):
        n = 2
        while f'{key}{n}' in taken:
            n += 1
        return f'{key}{n}'
    step = 1 if key >= 0 else -1
    v = key + step
    while v in taken or v in (0, 999, 1000):
        v += step
    return v


def assign_numbers(plan: Plan, dst):
    """Give every renumbered entry its new number (the same ones every time it is asked)."""
    for kind in TABLE_KINDS:
        taken = {_key_of(kind, r) for r in rows_of(dst, kind)}
        for e in plan.entries[kind]:
            if e.status == 'new':
                taken.add(e.key)
        for e in plan.entries[kind]:
            if e.action == 'renumber':
                e.new_key = free_key(kind, e.key, taken)
                taken.add(e.new_key)
    taken = {s.number for s in storytext.stories(dst)}
    taken |= {e.key for e in plan.entries['stories'] if e.status == 'new'}
    for e in plan.entries['stories']:
        if e.action == 'renumber':
            v = max([9] + list(taken)) + 1
            e.new_key = v
            taken.add(v)


def number_map(plan: Plan, kind) -> dict:
    out = {}
    for e in plan.entries[kind]:
        if e.action == 'renumber' and e.new_key is not None:
            out[e.key] = e.new_key
    return out


# ── doing it ─────────────────────────────────────────────────────────────────────
def scopes_for(plan: Plan, dst, src) -> list:
    sc = []
    for kind in TABLE_KINDS:
        if kind in plan.chosen and any(e.action in ('add', 'renumber', 'replace') for e in plan.entries[kind]):
            sc.append(SCOPE[kind])
            for folder in TABLE_KINDS[kind][2]:
                for e in plan.entries[kind]:
                    if e.action in ('add', 'renumber', 'replace'):
                        sc.append(('pic', folder, e.new_key if e.action == 'renumber' else e.key))
    if 'stories' in plan.chosen or 'levels' in plan.chosen:
        sc.append('texts')
    if 'talk' in plan.chosen:
        sc.append('texts')
    if 'settings' in plan.chosen:
        sc.append('quest')
    if 'levels' in plan.chosen:
        sc.append('quest')
        for k in range(len(plan.level_picks)):
            n = dst.levels + 1 + k
            sc += [('map', n), ('script', n), ('shops', n)]
    return list(dict.fromkeys(sc))


def _loot(rows, im):
    out = []
    for x in rows:
        x = list(x)
        if len(x) > 3 and x[2] == 'item':
            x[3] = im.get(x[3], x[3])
        out.append(x)
    return out


def _remap_row(kind, row, maps):
    """A row with the numbers it mentions changed to the ones the things were brought as."""
    r = copy.deepcopy(row)
    cm, im, sm = maps['creatures'], maps['items'], maps['spells']
    if kind == 'creatures':
        if r.get('loot'):
            r['loot'] = _loot(r['loot'], im)
        if r.get('drop_on_level'):
            r['drop_on_level'] = {k: im.get(v, v) for k, v in r['drop_on_level'].items()}
        for k in ('raises_dead', 'reveals_as', 'hides_as'):
            if r.get(k):
                r[k] = cm.get(r[k], r[k])
        if isinstance(r.get('deceiver'), dict) and r['deceiver'].get('becomes'):
            r['deceiver']['becomes'] = cm.get(r['deceiver']['becomes'], r['deceiver']['becomes'])
    elif kind == 'spells':
        if r.get('creature'):
            r['creature'] = cm.get(r['creature'], r['creature'])
    elif kind == 'classes':
        if r.get('bag'):
            r['bag'] = {k: im.get(v, v) for k, v in r['bag'].items()}
        if r.get('spells'):
            r['spells'] = [sm.get(v, v) for v in r['spells']]
    return r


def _remap_map(grid, maps):
    rows = []
    for x, y, fl, wa, it, mo, go, de in grid.rows():
        rows.append((x, y, maps['floors'].get(fl, fl), maps['walls'].get(wa, wa), maps['items'].get(it, it), maps['creatures'].get(mo, mo), go,
                     maps['decos'].get(de, de)))
    return rows


def _shop_text(text, im):
    if not im:
        return text
    lines = []
    for line in text.split('\n'):
        lines.append(' '.join(str(im.get(int(t), int(t))) if t.lstrip('-').isdigit() else t for t in line.split()))
    return '\n'.join(lines)


def apply(session, src, plan: Plan) -> Report:
    """Do it: one undoable edit on the session's project."""
    dst = session.project
    assign_numbers(plan, dst)
    rep = Report()
    maps = {k: number_map(plan, k) for k in ('creatures', 'items', 'spells', 'floors', 'walls', 'decos', 'classes')}
    with session.edit('Merge from ' + src.name, *scopes_for(plan, dst, src)):
        # the tables and tiles, with their pictures
        for kind in TABLE_KINDS:
            if kind not in plan.chosen:
                continue
            where, name = TABLE_KINDS[kind][1]
            target = dst.tables[name] if where == 'table' else dst.tiles.setdefault(name, [])
            for e in plan.entries[kind]:
                if e.action in ('skip',) or e.status == 'same':
                    rep.skipped[kind] = rep.skipped.get(kind, 0) + 1
                    continue
                row = next(r for r in rows_of(src, kind) if r['id'] == e.key)
                new = _remap_row(kind, row, maps)
                if e.action == 'renumber':
                    new['id'] = e.new_key
                if e.action == 'replace':
                    i = next((i for i, r in enumerate(target) if r['id'] == e.key), None)
                    if i is None:
                        target.append(new)
                    else:
                        target[i] = new
                    rep.replaced[kind] = rep.replaced.get(kind, 0) + 1
                else:
                    target.append(new)
                    rep.added[kind] = rep.added.get(kind, 0) + 1
                if plan.with_pictures:
                    for folder in TABLE_KINDS[kind][2]:
                        pic = src.picture(folder, e.key)
                        if pic is not None:
                            dst.set_picture(folder, new['id'], pic)
            target.sort(key=lambda r: (str(r['id']) if isinstance(r['id'], str) else r['id']))
            dst.touch(SCOPE[kind])
        # story pages: the chosen ones, then the ones the levels need
        story_map = {}
        if 'stories' in plan.chosen:
            for e in plan.entries['stories']:
                if e.action in ('add', 'renumber', 'replace'):
                    s = storytext.get(src, e.key)
                    no = e.new_key if e.action == 'renumber' else e.key
                    if e.action == 'replace':
                        storytext.set_lines(dst, no, s.lines)
                        rep.replaced['stories'] = rep.replaced.get('stories', 0) + 1
                    else:
                        storytext.add_story(dst, s.lines, number=no)
                        rep.added['stories'] = rep.added.get('stories', 0) + 1
                    story_map[e.key] = no
        # what people say
        if 'talk' in plan.chosen:
            blocks = _talk_blocks(dst.texts['talk'])
            src_blocks = {}
            for b in _talk_blocks(src.texts['talk']):
                m = re.match(r'^(-?\d+)\s+(-?\d+)\s+(-?\d+)\s', b)
                if m and int(m[1]) == 0:
                    src_blocks[(int(m[2]), int(m[3]))] = b
            for e in plan.entries['talk']:
                if e.action in ('add', 'replace'):
                    b = src_blocks[e.key]
                    if e.action == 'replace':
                        blocks = [x for x in blocks if not re.match(rf'^0\s+{e.key[0]}\s+{e.key[1]}\s', x)]
                        rep.replaced['talk'] = rep.replaced.get('talk', 0) + 1
                    else:
                        rep.added['talk'] = rep.added.get('talk', 0) + 1
                    blocks.append(b)
            dst.texts['talk'] = '\n'.join(blocks) + '\n'
            dst.touch('talk')
        # settings
        if 'settings' in plan.chosen:
            for e in plan.entries['settings']:
                if e.action == 'replace':
                    dst.quest[e.key] = copy.deepcopy(src.quest[e.key])
                    rep.replaced['settings'] = rep.replaced.get('settings', 0) + 1
            dst.touch('quest')
        # levels
        if 'levels' in plan.chosen and plan.level_picks:
            first = dst.levels + 1
            rep.first_level = first
            number = {n: first + i for i, n in enumerate(plan.level_picks)}
            talk_new = []
            for n in plan.level_picks:
                new_n = number[n]
                dst.add_level()
                dst.scripts[new_n] = src.scripts.get(n, LEVEL_SCRIPT.format(n=new_n))
                dst.grids[new_n] = Grid(_remap_map(src.grid(n), maps))
                dst.shops[new_n] = {k: _shop_text(t, maps['items']) for k, t in src.shops.get(n, {}).items()}
                dst.dirty |= {'quest', ('map', new_n), ('script', new_n), ('shops', new_n)}
                # its story pages come with it, under free numbers
                stories = src.constant(n, 'STORIES', []) or []
                new_stories = []
                for s_no in stories:
                    if s_no in story_map:
                        new_stories.append(story_map[s_no])
                        continue
                    s = storytext.get(src, s_no)
                    if s is None:
                        new_stories.append(s_no)
                        continue
                    if s_no in RESERVED_STORIES:
                        new_stories.append(s_no)
                        continue
                    mine = storytext.get(dst, s_no)
                    if mine is not None and mine.lines == s.lines:
                        new_stories.append(s_no)
                        story_map[s_no] = s_no
                        continue
                    no = storytext.add_story(dst, s.lines)
                    story_map[s_no] = no
                    new_stories.append(no)
                    rep.added['stories'] = rep.added.get('stories', 0) + 1
                if stories:
                    dst.set_constant(new_n, 'STORIES', new_stories, 'story screens shown before the level')
                links = _level_links(src, n)
                if links:
                    fixed = {pos: (number.get(link[0], link[0]),) + tuple(link[1:]) for pos, link in links.items()}
                    dst.set_constant(new_n, 'LINKS', fixed, 'where the exits and ladders lead')
                # what people say on the level
                for b in _talk_blocks(src.texts['talk']):
                    m = re.match(r'^(-?\d+)(\s+.*)$', b, flags=re.S)
                    if m and int(m[1]) == n:
                        talk_new.append(f'{new_n}{m[2]}')
                rep.added['levels'] = rep.added.get('levels', 0) + 1
            if talk_new:
                dst.texts['talk'] = dst.texts['talk'].rstrip('\n') + '\n' + '\n'.join(talk_new) + '\n'
                dst.touch('talk')
            dst.touch('stories')
        dst.touch('quest')
    return rep
