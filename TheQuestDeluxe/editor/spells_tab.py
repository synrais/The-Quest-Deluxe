"""The Spells tab: each spell's requirements, cost, reach, power and duration, and what it does (its
effect, with the effect's settings and animation)."""
from __future__ import annotations


from .table_tab import TableTab, Field

EFFECTS = [('heal', 'heal: the hero gains life (power)'), ('bolt', 'bolt: damage at a target'),
           ('ward', 'ward: damage on the 8 squares around the hero'),
           ('dark_hour', 'dark hour: the ward, repeated; mana to 0'), ('earthquake', 'earthquake: a cross of blows'),
           ('freeze', 'freeze: a creature stops for a while'), ('drain', 'drain: damage, and the hero heals by it'),
           ('summon', 'summon: brings an ally'), ('teleport', 'teleport: the hero jumps to a square'),
           ('shield', 'shield: stops blows up to a power'), ('fire_shield', 'fire shield: burns creatures next to the hero'),
           ('invisibility', 'invisibility: creatures lose sight of the hero')]
ANIMS = ['aheal', 'arestore', 'acure', 'aflame', 'afireball', 'agflame', 'ainferno', 'athunder', 'alightning',
         'adeaths', 'adeteriorate', 'ablackward', 'adarkhour', 'aearthq', 'aicering', 'adrain', 'ashield',
         'ainvisibility', 'asskeleton', 'astoneknight', 'asscorpion', 'ateleport']


def fmt_anim(row):
    return ' '.join(str(v) for v in row.get('anim') or [])


def parse_anim(text):
    words = text.split()
    if not words:
        return None
    if words[0] not in ANIMS:
        raise ValueError(f'the animations are {", ".join(ANIMS)}')
    return [words[0]] + [int(v) for v in words[1:]]


def opt_int(key):
    return lambda row: '' if row.get(key) is None else str(row.get(key))


def parse_opt(text):
    return int(text) if text.strip() else None


def eff(*names):
    return lambda r: r.get('effect') in names


class SpellsTab(TableTab):
    TABLE = 'spells'
    ICON_LAYER = 'spell'
    PICTURES = [('Spell book icon', 'spells', False)]
    INTRO = ('The spell book holds 20 spells a page; more than 20 add pages (the original has one). Range 0 casts on the hero; '
             'otherwise the hero picks a target that many squares away. Animations are the original\'s '
             '(engine/anim.py), with their arguments.')

    def fields(self):
        opt = lambda k, label, hint='', when=None: Field(k, label, 'custom', fmt=opt_int(k), parse=parse_opt,
                                                         hint=hint, when=when)
        creatures = sorted((c['id'], f'{c["id"]} {c.get("name", "")}') for c in self.app.project.tables['creatures']
                           if c['id'] <= -100)
        return [
            Field('id', 'Number', 'readonly'),
            Field('name', 'Name', 'str'),
            Field('req_int', 'Needs intelligence', 'int', default=0, hint='to learn and to cast it'),
            Field('mana', 'Mana', 'int', default=0),
            Field('range', 'Range', 'int', default=0, hint='0 = on the hero'),
            Field('power', 'Power', 'int', default=0),
            Field('duration', 'Duration', 'int', default=0, hint='turns (shields, invisibility, freeze)'),
            Field('effect', 'Effect', 'choice', EFFECTS),
            Field('anim', 'Animation', 'custom', fmt=fmt_anim, parse=parse_anim,
                  hint='e.g. aflame 0, athunder, asskeleton 1'),
            opt('repeat', 'Repeats', 'how many times the animation (or the ward) repeats',
                when=eff('bolt', 'dark_hour', 'ward')),
            Field('creature', 'Summons', 'choice', creatures, when=eff('summon'), hint='an ally (-100 and below)'),
            opt('fizzle', 'Fails', '% chance the spell fails'),
            Field('empties_mana', 'Empties the mana', 'bool'),
            Field('needs_target', 'Needs a creature', 'bool', hint='only castable at a creature'),
            opt('absorb_power_of', 'Uses the power of spell', "Quest I's Shield reads spell 5's power",
                when=eff('shield')),
            opt('freeze_power_of', 'Uses the power of spell', "Quest I's Ring of Ice reads spell 4's power",
                when=eff('freeze')),
        ]

    def new_row(self):
        used = {r['id'] for r in self.rows}
        v = next(n for n in range(1, len(used) + 2) if n not in used)
        return {'id': v, 'name': 'New spell', 'req_int': 10, 'mana': 5, 'range': 3, 'power': 10, 'duration': 0,
                'effect': 'bolt', 'anim': ['aflame', 0]}

    def duplicate_id(self, row):
        used = {r['id'] for r in self.rows}
        return next(n for n in range(1, len(used) + 2) if n not in used)

    def uses(self, row):
        out = [f'class {c["name"]} starts knowing it' for c in self.app.project.tables['classes']
               if row['id'] in c.get('spells', [])]
        return out


