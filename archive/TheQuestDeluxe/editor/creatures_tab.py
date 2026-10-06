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


def fmt_rules(key):
    """A list of loot-style rules (lo-hi: gold n+base / item number) kept under `key`."""
    return lambda row: fmt_loot({'loot': row.get(key) or []})


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

    GROUPS = [
        ('Fighting', True, 'how hard it is to kill and how it attacks',
         ['life', 'power', 'atk', 'def', 'warm', 'marm', 'range', 'att', 'magic_attack', 'rests_after_moving',
          'missile_anim', 'cast_anim']),
        ('Rewards', True, 'what it gives when it dies',
         ['exp', 'loot', 'drop_on_level', 'death_gold.chance', 'death_gold.min', 'death_gold.max']),
        ('Gold and thieves', False, 'steals gold when it hits him; drops some when it is hit',
         ['steal_gold.chance', 'steal_gold.min', 'steal_gold.max', 'hit_gold.chance', 'hit_gold.min',
          'hit_gold.max', 'hit_item', 'hit_item_chance', 'hit_drops', 'drain_mana.chance', 'drain_mana.min',
          'drain_mana.max']),
        ('Poison and special attacks', False, 'poison, exploding, healing friends, raising the dead',
         ['poison_melee', 'poison_ranged', 'poison_cast', 'drains_life', 'heals_allies', 'raises_dead', 'explodes']),
        ('Body', True, 'how many squares big it is, and what it leaves when it dies',
         ['size', 'log_name', 'corpse', 'bleeds', 'silences_witnesses']),
        ('Behaviour', False, 'hiding, chasing, running away',
         ['invisible', 'reveals_as', 'hides_as', 'chase_range', 'flees_within', 'animal']),
        ('Changes and rising again', False, 'turning into something else, bursting, rising from blood',
         ['becomes_on_death', 'bursts_into', 'transforms_into', 'transforms_below', 'transforms_damage',
          'regenerates_from_blood', 'rise_limit', 'blood_range']),
        ('Resistances', False, 'what it shrugs off', ['resists']),
    ]

    def fields(self):
        opt = lambda k, label, hint='': Field(k, label, 'custom', fmt=fmt_key(k), parse=parse_int_or_none, hint=hint)
        monsters = [(None, '(none)')] + [(c['id'], self.label(c)) for c in
                                         sorted(self.rows, key=lambda c: c['id'])]
        pick = lambda k, label, hint='': Field(k, label, 'choice', monsters, hint=hint)
        items = [(None, '(nothing)')] + [(r['id'], f'{r["id"]} {r.get("name", "")}') for r in
                                        sorted(self.app.project.tables.get('items', []), key=lambda r: r['id'])]
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
            Field('hit_drops', 'Drops when hit', 'custom', fmt=fmt_rules('hit_drops'), parse=parse_loot,
                  hint='something falls each time it is hurt: rules like Loot, e.g. 1-30: gold 3+1; 30-40: item 620'),
            Field('death_gold.chance', 'Drops gold: chance %', 'int',
                  hint='when it dies: the chance (1-100) that it leaves gold, from min to max (empty: never)'),
            Field('death_gold.min', '... at least', 'int', when=lambda r: (r.get('death_gold') or {}).get('chance')),
            Field('death_gold.max', '... at most', 'int', when=lambda r: (r.get('death_gold') or {}).get('chance')),
            Field('steal_gold.chance', 'Steals gold: chance %', 'int',
                  hint='when its blow or shot hurts the hero: the chance (1-100) it takes gold, min to max. It carries '
                       'it and drops it when it dies'),
            Field('steal_gold.min', '... at least', 'int', when=lambda r: (r.get('steal_gold') or {}).get('chance')),
            Field('steal_gold.max', '... at most', 'int', when=lambda r: (r.get('steal_gold') or {}).get('chance')),
            Field('hit_gold.chance', 'Drops gold when hit: chance %', 'int',
                  hint='each time the hero hurts it: the chance (1-100) that gold falls, min to max'),
            Field('hit_gold.min', '... at least', 'int', when=lambda r: (r.get('hit_gold') or {}).get('chance')),
            Field('hit_gold.max', '... at most', 'int', when=lambda r: (r.get('hit_gold') or {}).get('chance')),
            Field('hit_item', 'Drops an item when hit', 'choice', items, hint='each time it is hurt (see the chance)'),
            Field('hit_item_chance', '... chance %', 'int', when=lambda r: r.get('hit_item'),
                  hint='1-100 (empty: every time)'),
            Field('drain_mana.chance', 'Drains mana: chance %', 'int',
                  hint='when its blow or shot hurts the hero: the chance (1-100) it takes mana, min to max'),
            Field('drain_mana.min', '... at least', 'int', when=lambda r: (r.get('drain_mana') or {}).get('chance')),
            Field('drain_mana.max', '... at most', 'int', when=lambda r: (r.get('drain_mana') or {}).get('chance')),
            Field('drop_on_level', 'Always drops', 'custom', fmt=fmt_pairs('drop_on_level'), parse=parse_pairs,
                  hint='level: item, e.g. 3: 12'),
            Field('corpse', 'Leaves', 'choice', CORPSES),
            Field('bleeds', 'Bleeds', 'bool', default=True),
            Field('magic_attack', 'Magic blows', 'bool', hint='stopped by magic armour, not weapon armour'),
            opt('poison_melee', 'Poisons (melee)', '1 time in n when its blow hits'),
            opt('poison_ranged', 'Poisons (missile)', '1 time in n'),
            opt('poison_cast', 'Poisons (spell)', '1 time in n'),
            Field('missile_anim', 'Missile', 'choice', MISSILES),
            Field('cast_anim', 'Spell animation', 'custom', fmt=fmt_anim, parse=parse_anim, suggest=CAST_ANIMS,
                  hint='animation and its arguments, e.g. aflame 1'),
            Field('heals_allies', 'Heals its side', 'bool', hint='instead of attacking'),
            pick('raises_dead', 'Raises bones as', 'the creature the bones turn into'),
            opt('explodes', 'Explodes', 'blasts the hero n times, then dies'),
            Field('drains_life', 'Drains life', 'bool', hint='heals itself by the damage its spell does'),
            Field('invisible', 'Invisible', 'bool'),
            pick('reveals_as', 'Shows itself as', 'the creature it turns into when it attacks'),
            pick('hides_as', 'Hides again as', 'when the hero leaves the screen'),
            Field('chase_range', 'Chases within', 'int', hint='a hostile creature only comes for the hero when he is '
                  'within this many squares (empty: as far as it sees); beyond it stays where it is'),
            Field('flees_within', 'Runs away within', 'int', hint='a hostile creature runs from the hero when he is '
                  'within this many squares; cornered, it fights'),
            Field('rests_after_moving', 'Rests after moving', 'bool', hint="doesn't attack in a turn it moved"),
            Field('animal', 'Animal', 'bool', hint="doesn't fight people; killing it earns no reputation"),
            Field('size', 'Size', 'int', width=4,
                  hint='1: one square. 2: a giant on 2 x 2 squares (3: 3 x 3): put it on the map at its top-left '
                       'square and leave the others free; the screen has 10 x 10. A 40 x 40 picture is stretched.'),
            pick('becomes_on_death', 'Turns into (on death)', 'instead of dying it becomes this creature, '
                 'at full life, where it stood'),
            Field('bursts_into', 'Bursts into', 'custom', fmt=fmt_pairs('bursts_into'), parse=parse_pairs,
                  hint='creatures that spring from its body when it dies: "creature: how many", e.g. 12: 3, 13: 1'),
            pick('transforms_into', 'Transforms into', 'the creature it becomes when hurt enough (see below)'),
            Field('transforms_below', 'Transforms at life %', 'int', when=lambda r: r.get('transforms_into'),
                  hint='when its life falls to this percent of its full life or less (empty: not by this)'),
            Field('transforms_damage', 'Transforms after damage', 'int', when=lambda r: r.get('transforms_into'),
                  hint='when it has taken this much damage in all (empty: not by this)'),
            Field('regenerates_from_blood', 'Rises from blood', 'bool',
                  hint='after it dies the nearest pile of blood on the screen slides to its body, and it rises again at full life'),
            Field('rise_limit', 'Times it can rise', 'int', when=lambda r: r.get('regenerates_from_blood'),
                  hint='1, 2 ...: how many times it can rise from blood (empty: for ever)'),
            Field('blood_range', 'Blood reaches', 'int', when=lambda r: r.get('regenerates_from_blood'),
                  hint='squares from its body that blood still feeds it (empty: the whole screen). It can rise '
                       'again and again while there is blood in reach, its own spilled blood included'),
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
