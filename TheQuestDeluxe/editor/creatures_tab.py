"""The Creatures tab: monsters, people and summoned allies, with their stats, rewards and traits."""
from __future__ import annotations

from tkinter import simpledialog

from .table_tab import TableTab, Field

ATTITUDES = [(9, '9 hostile (sees 9 squares)'), (8, '8 hostile, sees the invisible'),
             (-1, '-1 neutral (turns hostile when hit)'), (-2, '-2 peaceful'), (-3, '-3 follows the hero'),
             (-4, '-4 caster that never melees')]
CORPSES = [(None, 'a body (blood and remains)'), ('bones', 'bones (can be raised)'), ('none', 'nothing')]
MISSILES = [(None, '(none)'), ('sthit', 'a stone (sthit)'), ('arhit', 'an arrow (arhit)'), ('bolthit', 'a bolt (bolthit)')]
CAST_ANIMS = ['afireball', 'aflame', 'agflame', 'alightning', 'athunder', 'ainferno', 'adrain', 'adarkhour',
              'aearthq', 'adeaths', 'aicering', 'ablackward', 'adeteriorate']


ELEMENT_NAMES = [('fire', 'fire'), ('ice', 'ice'), ('poison', 'poison'), ('drain', 'drain')]


def role(v: int) -> str:
    return 'monster' if v > 0 else 'shopkeeper' if v == -5 else 'person' if v > -100 else 'summoned ally'


def fmt_loot(row) -> str:
    parts = []
    for lo, hi, kind, *args in row.get('loot', []):
        if kind == 'gold':
            parts.append(f'{lo}-{hi}: gold {args[0]}+{args[1]}')
        else:
            parts.append(f'{lo}-{hi}: item {args[0]}')
    return '; '.join(parts)


def parse_loot(text: str) -> list:
    out = []
    for part in text.split(';'):
        part = part.strip()
        if not part:
            continue
        rng, what = part.split(':', 1)
        lo, hi = (int(v) for v in rng.split('-'))
        words = what.split()
        if words[0] == 'gold':
            n, base = (int(v) for v in words[1].split('+'))
            out.append([lo, hi, 'gold', n, base])
        elif words[0] == 'item':
            out.append([lo, hi, 'item', int(words[1])])
        else:
            raise ValueError('each rule is "lo-hi: gold n+base" or "lo-hi: item number"')
    return out


def fmt_pairs(key):
    return lambda row: ', '.join(f'{k}: {v}' for k, v in (row.get(key) or {}).items())


def parse_pairs(text: str) -> dict | None:
    out = {}
    for part in text.split(','):
        if part.strip():
            k, v = part.split(':')
            out[str(int(k))] = int(v)
    return out or None


def fmt_anim(row) -> str:
    return ' '.join(str(v) for v in row.get('cast_anim') or [])


def parse_anim(text: str):
    words = text.split()
    if not words:
        return None
    if words[0] not in CAST_ANIMS:
        raise ValueError(f'the animations are {", ".join(CAST_ANIMS)}')
    return [words[0]] + [int(v) for v in words[1:]]


def parse_int_or_none(text: str):
    return int(text) if text.strip() else None


def fmt_key(key):
    return lambda row: '' if row.get(key) is None else str(row.get(key))


class CreaturesTab(TableTab):
    TABLE = 'creatures'
    ICON_LAYER = 'mon'
    PICTURES = [('Picture', 'creatures', False)]
    INTRO = ('Monsters (numbers above 0), people (-1 to -99; -5 is a shopkeeper, the others talk) and '
             'summoned allies (-100 and below). What people say is in the Text tab under their number. '
             'Loot: rules tried with a roll of 1-100, the first whose range holds it applies.')

    def fields(self):
        opt = lambda k, label, hint='': Field(k, label, 'custom', fmt=fmt_key(k), parse=parse_int_or_none, hint=hint)
        monsters = [(None, '(none)')] + [(c['id'], self.label(c)) for c in
                                         sorted(self.rows, key=lambda c: c['id'])]
        pick = lambda k, label, hint='': Field(k, label, 'choice', monsters, hint=hint)
        return [
            Field('id', 'Number', 'readonly'),
            Field('_role', 'Is a', 'readonly', default=None),
            Field('name', 'Name', 'str', hint='in the editor, and "the <name>" in messages'),
            Field('log_name', 'Name in the log', 'str',
                  hint='Deluxe\'s combat log: "The <name> hits you" (empty: the name, in lower case)'),
            Field('life', 'Life', 'int', default=0),
            Field('power', 'Power', 'int', default=0, hint='the damage of its blows or spells'),
            Field('atk', 'Attack', 'int', default=0, hint='to hit: attack - the defender\'s defence, in %'),
            Field('def', 'Defence', 'int', default=0),
            Field('warm', 'Weapon armour', 'int', default=0),
            Field('marm', 'Magic armour', 'int', default=0),
            Field('range', 'Range', 'int', default=1, hint='1 = melee; more = it shoots (or casts, with attack 0)'),
            Field('att', 'Attitude', 'choice', ATTITUDES, default=9),
            Field('exp', 'Experience', 'int', hint='for killing it'),
            Field('loot', 'Loot', 'custom', fmt=fmt_loot, parse=parse_loot,
                  hint='e.g. 20-100: gold 3+1; 10-20: item 620 (random(3)+1 gold, or item 620)'),
            Field('drop_on_level', 'Always drops', 'custom', fmt=fmt_pairs('drop_on_level'), parse=parse_pairs,
                  hint='level: item, e.g. 3: 12'),
            Field('corpse', 'Leaves', 'choice', CORPSES),
            Field('bleeds', 'Bleeds', 'bool', default=True),
            Field('magic_attack', 'Magic blows', 'bool', hint='stopped by magic armour, not weapon armour'),
            opt('poison_melee', 'Poisons (melee)', '1 time in n when its blow hits'),
            opt('poison_ranged', 'Poisons (missile)', '1 time in n'),
            opt('poison_cast', 'Poisons (spell)', '1 time in n'),
            Field('missile_anim', 'Missile', 'choice', MISSILES),
            Field('cast_anim', 'Spell animation', 'custom', fmt=fmt_anim, parse=parse_anim,
                  hint='animation and its arguments, e.g. aflame 1'),
            Field('heals_allies', 'Heals its side', 'bool', hint='instead of attacking'),
            pick('raises_dead', 'Raises bones as', 'the creature the bones turn into'),
            opt('explodes', 'Explodes', 'blasts the hero n times, then dies'),
            Field('drains_life', 'Drains life', 'bool', hint='heals itself by the damage its spell does'),
            Field('invisible', 'Invisible', 'bool'),
            pick('reveals_as', 'Shows itself as', 'the creature it turns into when it attacks'),
            pick('hides_as', 'Hides again as', 'when the hero leaves the screen'),
            Field('rests_after_moving', 'Rests after moving', 'bool', hint="doesn't attack in a turn it moved"),
            Field('animal', 'Animal', 'bool', hint="doesn't fight people; killing it earns no reputation"),
            Field('size', 'Size', 'int', default=1, width=4,
                  hint='1: one square. 2: a giant on 2 x 2 squares (3: 3 x 3): put it on the map at its top-left '
                       'square and leave the others free; the screen has 10 x 10. A 40 x 40 picture is stretched.'),
            Field('regenerates_from_blood', 'Rises from blood', 'bool',
                  hint='after it dies the nearest pile of blood on the screen slides to its body, and it rises again at full life'),
            Field('resists', 'Resists', 'multi', [(k, v) for k, v in ELEMENT_NAMES], hint='elements and spells it shrugs off'),
            Field('silences_witnesses', 'Silences witnesses', 'bool', hint='nobody reports a killing near it'),
        ]

    def _show(self, row):
        if row is not None:
            row['_role'] = role(row['id'])
        super()._show(row)
        if row is not None:
            row.pop('_role', None)

    def label(self, row):
        return f'{row["id"]}  {row.get("name") or "(no name)"}'

    def new_row(self):
        kind = simpledialog.askinteger('New creature', 'What is it?\n1 a monster\n2 a person (who talks)\n'
                                       '3 a summoned ally', minvalue=1, maxvalue=3, initialvalue=1, parent=self)
        if not kind:
            return None
        used = {r['id'] for r in self.rows}
        if kind == 1:
            v = 101
            while v in used:
                v += 1
        elif kind == 2:
            v = -20
            while v in used:
                v -= 1
            if v <= -100:
                return None
        else:
            v = -103
            while v in used:
                v -= 1
        return {'id': v, 'name': ['New monster', 'New person', 'New ally'][kind - 1], 'life': 10, 'power': 3,
                'atk': 60, 'def': 10, 'warm': 0, 'marm': 0, 'range': 1, 'att': [9, -2, -3][kind - 1],
                'exp': 10 if kind == 1 else 0, 'loot': []}

    def duplicate_id(self, row):
        """The next free number of the same kind: monsters 1 and up, people -1 to -99 (not -5, the
        shopkeeper), allies -100 and down."""
        used, v = {r['id'] for r in self.rows}, row['id']
        if v > 0:
            candidates = range(v, v + 10000)
        elif v > -100:
            candidates = [n for n in range(-6, -100, -1)] + [-1, -2, -3, -4]
        else:
            candidates = range(v, v - 10000, -1)
        return next((n for n in candidates if n not in used), v)

    def uses(self, row):
        return self.app.project.uses('mon', row['id'])
