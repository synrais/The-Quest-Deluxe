"""The Spells tab: each spell's requirements, cost, reach, power and duration, and what it does (its
effect, with the effect's settings and animation)."""
from __future__ import annotations


from .table_tab import TableTab, Field

EFFECTS = [('heal', 'heal: the hero gains life (power)'), ('bolt', 'bolt: damage at a target'),
           ('ward', 'ward: damage on the 8 squares around the hero'),
           ('dark_hour', 'dark hour: the ward, repeated; mana to 0'), ('earthquake', 'earthquake: a cross of blows'),
           ('freeze', 'freeze: a creature stops for a while'), ('drain', 'drain: damage, and the hero heals by it'),
           ('summon', 'summon: brings an ally'),
           ('resurrect', 'resurrect: a dead creature (or person) rises and fights at the hero\'s side on this screen'),
           ('heal_target', 'heal a creature: any creature you target, friend or foe, gains life (power)'),
           ('shadow_clones', 'shadow clones: an ally on every square around the hero'),
           ('disguise', "disguise: the hero becomes a random creature; monsters leave him alone, people may not"), ('teleport', 'teleport: the hero jumps to a square'),
           ('shield', 'shield: stops blows up to a power'), ('fire_shield', 'fire shield: burns creatures next to the hero'),
           ('invisibility', 'invisibility: creatures lose sight of the hero')]
ANIMS = ['aheal', 'aheal2', 'arestore', 'acure', 'aflame', 'afireball', 'agflame', 'ainferno', 'athunder', 'alightning',
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
    GROUPS = [
        ('Casting', True, 'what it costs and how far it reaches',
         ['req_int', 'mana', 'range', 'needs_target', 'fizzle', 'empties_mana']),
        ('What it does', True, 'the effect and how strong it is',
         ['effect', 'power', 'duration', 'repeat', 'burns', 'freezes_water', 'absorb_power_of', 'freeze_power_of']),
        ('Summons and creatures', False, 'raising or calling creatures',
         ['creature', 'creatures', 'follows', 'clones_hero', 'npc_anger']),
        ('How it looks', False, 'the animation', ['anim']),
    ]
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
        monsters = [(c['id'], f'{c["id"]} {c.get("name", "")}') for c in
                    sorted(self.app.project.tables['creatures'], key=lambda c: c['id']) if c['id'] > 0]
        spells = [(None, '(its own)')] + [(r['id'], f'{r["id"]} {r.get("name", "")}')
                                          for r in sorted(self.rows, key=lambda r: r['id'])]
        return [
            Field('id', 'Number', 'readonly'),
            Field('name', 'Name', 'str'),
            Field('req_int', 'Needs intelligence', 'int', default=0, hint='to learn and to cast it'),
            Field('mana', 'Mana', 'int', default=0),
            Field('range', 'Range', 'int', default=0, hint='0 = on the hero'),
            Field('power', 'Power', 'int', default=0),
            Field('duration', 'Duration', 'int', default=0, hint='turns (shields, invisibility, freeze)'),
            Field('effect', 'Effect', 'choice', EFFECTS),
            Field('anim', 'Animation', 'custom', fmt=fmt_anim, parse=parse_anim, suggest=ANIMS,
                  hint='e.g. aflame 0, athunder, asskeleton 1'),
            opt('repeat', 'Repeats', 'how many times the animation (or the ward) repeats',
                when=eff('bolt', 'dark_hour', 'ward')),
            Field('creature', 'Summons', 'choice', creatures, when=eff('summon', 'shadow_clones'),
                  hint='an ally (-100 and below)'),
            opt('npc_anger', 'Friendly people turn on him %', 'each person near, when it is cast and when he walks into '
                'a screen (empty: 50)', when=eff('disguise')),
            Field('creatures', 'Can become', 'multi', monsters, when=eff('disguise'),
                  hint='the shapes it picks from (none ticked: any monster that shows)'),
            Field('follows', 'Follows him', 'bool', when=eff('resurrect'),
                  hint='the raised creature goes with the hero from screen to screen until it dies'),
            opt('clones_hero', 'Clones are % of the hero', "each clone's life, power and armour as this percent of "
                "the hero's (empty: the creature's own)", when=eff('shadow_clones')),
            opt('fizzle', 'Fails', '% chance the spell fails'),
            opt('burns', 'Burns blood away', 'a fire spell clears the blood on the ground within this many '
                'squares of where it lands (0: that square only; bones stay)'),
            opt('freezes_water', 'Freezes water', 'turns water (a wall with "Freezes to") within this many '
                'squares to ice for the Duration, 10 turns if none'),
            Field('empties_mana', 'Empties the mana', 'bool'),
            Field('needs_target', 'Needs a creature', 'bool', hint='only castable at a creature'),
            Field('absorb_power_of', 'Uses the power of spell', 'choice', spells,
                  hint="Quest I's Shield reads spell 5's power", when=eff('shield')),
            Field('freeze_power_of', 'Uses the power of spell', 'choice', spells,
                  hint="Quest I's Ring of Ice reads spell 4's power", when=eff('freeze')),
        ]

    TEMPLATES = [
        ('A bolt (a fire spell that burns blood away)', {'range': 3, 'power': 12, 'effect': 'bolt',
                                                         'anim': ['aflame', 0], 'burns': 1}),
        ('Frost (freezes water to ice and creatures)', {'range': 3, 'power': 10, 'duration': 10, 'effect': 'freeze',
                                                        'anim': ['aicering'], 'freezes_water': 1}),
        ('Shadow clones (allies all around the hero)', {'range': 0, 'power': 0, 'duration': 12,
                                                        'effect': 'shadow_clones', 'clones_hero': 50}),
        ('Disguise (a random creature, the reverse of hostile)', {'range': 0, 'power': 0, 'duration': 25,
                                                                  'effect': 'disguise', 'npc_anger': 50}),
        ('Resurrection (a body rises to fight beside the hero)', {'range': 4, 'power': 0, 'mana': 20,
                                                                  'effect': 'resurrect', 'needs_target': False, 'follows': True}),
        ('Mend (heals any creature you target, ally or enemy)', {'range': 4, 'power': 30, 'mana': 10,
                                                                  'effect': 'heal_target', 'anim': ['aheal2']}),
        ('A blank spell', {'range': 3, 'power': 10, 'effect': 'bolt', 'anim': ['aflame', 0]}),
    ]

    def new_row(self):
        from .uikit import choose
        pick = choose(self, 'New spell', 'Start from which kind of spell?', [t[0] for t in self.TEMPLATES])
        if pick is None:
            return None
        used = {r['id'] for r in self.rows}
        v = next(n for n in range(1, len(used) + 2) if n not in used)
        row = {'id': v, 'name': 'New spell', 'req_int': 10, 'mana': 5, 'range': 3, 'power': 10, 'duration': 0}
        row.update(self.TEMPLATES[pick][1])
        if row['effect'] in ('shadow_clones',) and self.app.project.tables['creatures']:
            allies = [c['id'] for c in self.app.project.tables['creatures'] if c['id'] <= -100]
            if allies:
                row['creature'] = allies[0]
        return row

    def duplicate_id(self, row):
        used = {r['id'] for r in self.rows}
        return next(n for n in range(1, len(used) + 2) if n not in used)

    def uses(self, row):
        out = [f'class {c["name"]} starts knowing it' for c in self.app.project.tables['classes']
               if row['id'] in c.get('spells', [])]
        return out


