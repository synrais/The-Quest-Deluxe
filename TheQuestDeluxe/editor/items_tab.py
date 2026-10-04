"""The Items tab: weapons, armour, shields, helmets, amulets, ammunition, potions, keys and treasures."""
from __future__ import annotations

from tkinter import simpledialog, messagebox

from .table_tab import TableTab, Field
from .tiles_tab import key_choices

TYPES = [('weapon', 'Weapon (melee)'), ('launcher', 'Launcher (sling, bow)'), ('ammo', 'Ammunition'),
         ('armour', 'Armour'), ('shield', 'Shield'), ('helmet', 'Helmet'), ('amulet', 'Amulet'),
         ('potion', 'Potion'), ('treasure', 'Treasure / quest item'), ('key', 'Key'), ('chest', 'Chest'),
         ('teleporter', 'Teleporter pad'), ('exit', 'Level exit'),
         ('ladder', 'Ladder (to another level)'), ('rope', 'Rope (to another level)'),
         ('stairs', 'Stairs (to another level)'), ('hole', 'Hole (one way down)'),
         ('jump_pad', 'Jump pad (one way)')]
EATEN = ('treasure', 'potion')
WORN = ('weapon', 'launcher', 'armour', 'shield', 'helmet', 'amulet')
KINDS = [(0, '0 normal'), (1, '1 double strike (1 in 5)'), (2, '2 parry (1 in 5)'), (3, '3 magic (ignores armour)'),
         (4, '4 ranged (a launcher)'), (5, '5 two-handed'), (6, '6 two-handed, parry')]
POTIONS = [(1, '1 Minor Health'), (2, '2 Full Health'), (3, '3 Minor Mana'), (4, '4 Full Mana'),
           (5, '5 Minor Restoration'), (6, '6 Full Restoration'), (7, '7 Cure Poison'), (8, '8 Berserker')]
MISSILES = [(None, '(none)'), ('sthit', 'a stone (sthit)'), ('arhit', 'an arrow (arhit)'), ('bolthit', 'a bolt (bolthit)')]
STATS = ['req_str', 'req_int', 'atk', 'def', 'warm', 'marm', 'str', 'int', 'dex', 'acc', 'power', 'kind']


COLOURS = [(None, '(from its bag picture)')] + [(i, f'{i} {n}') for i, n in enumerate((
    'black', 'blue', 'green', 'cyan', 'red', 'magenta', 'brown', 'light grey', 'dark grey', 'light blue', 'light green',
    'light cyan', 'light red', 'light magenta', 'yellow', 'white'))]
STAND_ON = [(None, '(nothing)'), ('blood', 'a pile of blood'), ('deco', 'a decoration (number)'),
            ('floor', 'a floor (number)'), ('item', 'an item lying there')]
STAND_EFFECTS = [(None, '(nothing)'), ('berserk', 'Berserker rage'), ('heal', 'Heals him'), ('hurt', 'Hurts him'),
                 ('mana', 'Gives mana'), ('drain_mana', 'Drains mana'), ('poison', 'Poisons him'),
                 ('cure_poison', 'Cures poison')]
ELEMENTS = [(None, '(none)'), ('fire', 'Fire (burns it)'), ('ice', 'Ice (freezes it)'),
            ('poison', 'Poison'), ('drain', 'Drain (heals the hero)')]


def has(key):
    return lambda r: bool(r.get(key))


def is_(*types):
    return lambda r: r.get('type') in types



ITEM_LOOKS = [(None, '(by type: stairs and pads flat, chests full size, the rest small)'),
              ('small', 'small: half size, standing'), ('billboard', 'full size, standing'),
              ('flat', 'flat: on the ground')]

class ItemsTab(TableTab):
    TABLE = 'items'
    ICON_LAYER = 'item'
    LIST_ICON = 'bag'                      # bag pictures read better than map pictures at list size
    PICTURES = [('On the map', 'items', False), ('In the bag and shops', 'bag', True),
                ('Worn on the hero', 'worn', False)]
    INTRO = ('Everything the hero can find, carry, wear or buy. What an item does comes from its type and '
             'numbers; its pictures are 40 x 40 in the 16 EGA colours (imported pictures are converted). '
             'Ammunition comes in stacks of 1 to 20: each size is its own item (New ammo kind makes all 20).')

    GROUPS = [
        ('Basics', True, 'what it is and what it costs', ['type', 'bag_name', 'price', 'view3d', 'quest', 'show_on_hero', 'worn_colour', 'cape', 'worn_dx', 'worn_dy', 'worn_flip', 'worn_behind',
                                                               'clasp_colour', 'clasp_when', 'clasp_alt', 'clasp_mode']),
        ('Numbers', True, 'what it adds to the hero when worn or wielded',
         ['power', 'kind', 'atk', 'def', 'warm', 'marm', 'req_str', 'req_int']),
        ('Stat bonuses', False, 'added to the hero while worn', ['str', 'int', 'dex', 'acc', 'power_bonus']),
        ('Launchers and ammunition', True, 'what a bow fires, and how it looks in FPS mode',
         ['fires', 'missile_anim', 'no_ammo_bonus', 'ammo', 'count', 'power_x2', 'fps_attack', 'fps_turn']),
        ('Potions and keys', True, '', ['potion', 'key']),
        ('Light', False, 'lights up a dark screen while he carries it', ['light']),
        ('Powers while worn', False, 'healing, sight, thorns, walking on water ...',
         ['regen', 'mana_regen', 'thorns', 'lifesteal', 'sight', 'poison_immune', 'see_invisible', 'water_walk',
          'makes_small', 'makes_giant']),
        ('Does something on certain ground', False, 'while worn: rage in blood, healing on a floor ...',
         ['stand_on', 'stand_id', 'stand_effect', 'stand_amount']),
        ('Elements', False, 'what a hit adds: fire, ice, poison ...',
         ['element', 'element_chance', 'element_power', 'element_turns']),
        ('Using or eating it', False, 'from the bag, or when picked up',
         ['use.life', 'use.mana', 'use.cure_poison', 'use.message', 'pickup.grow', 'pickup.shrink', 'pickup.life',
          'pickup.mana', 'pickup.foresight', 'pickup.poison', 'pickup.message']),
    ]

    def __init__(self, master, app):
        super().__init__(master, app)
        from tkinter import ttk
        ttk.Button(self.buttons, text='New ammo kind...', command=self.new_ammo_kind).pack(side='left', padx=2)

    def hero_parts(self, row):
        """What the hero tried on here wears: what was chosen to dress him, and the item being looked at."""
        from .hero_preview import place_of
        dress = self.__dict__.setdefault('_dress', {'class': 1})
        parts = {p: dress.get(p, 0) for p in ('armour', 'helmet', 'amulet', 'weapon', 'shield')}
        if row is not None and place_of(row):
            parts[place_of(row)] = row['id']
        return dress, parts

    def extra_previews(self, parent, column):
        """The hero to try the item on, and boxes to dress him with other items."""
        from .hero_preview import HeroPreview
        dress, _ = self.hero_parts(self.row)
        box = HeroPreview(parent, self.app.project, dress, self.place_on_hero)
        box.grid(row=0, column=column, sticky='n')
        box.show(self.row)

    def place_on_hero(self, key, value, final=True):
        """The hero preview moved, flipped or turned the item: keep it on the item (0 / off leaves the key out)."""
        row = self.row
        if row is None:
            return
        if value in (0, False, None):
            self.drop(row, key)
        else:
            self.put(row, key, value)
        self.app.project.touch(self.TABLE)
        self.app.changed()
        if final:
            self._show(row)

    def hero_dress(self, folder, row):
        """For the painter of Worn on the hero: the item being painted on each of the four heroes (and what else is on him)."""
        if folder != 'worn':
            return None
        from .hero_preview import class_colour, dressed
        project = self.app.project
        dress, parts = self.hero_parts(row)
        classes = sorted(c['id'] for c in project.tables['classes'])[:4]
        return lambda layer: [dressed(project, class_colour(project, c), parts, replace={row['id']: layer}, cls=c) for c in classes]

    def has_picture_kind(self, folder, row):
        return folder != 'worn' or row.get('type') in WORN

    def shown_picture(self, folder, row):
        """The Worn on the hero picture, or what the game makes from the map picture where there is none."""
        img = super().shown_picture(folder, row)
        if img is None and folder == 'worn' and row.get('type') in WORN:
            from engine import worn
            slot = worn.slot_of(row)
            img = worn.overlay(slot, row, self.app.project.picture('bag', row['id']),
                               self.app.project.picture('items', row['id']))
        return img

    def ammo_kinds(self):
        seen = []
        for r in self.rows:
            if r.get('type') == 'ammo' and r.get('ammo') not in seen:
                seen.append(r['ammo'])
        return seen

    def fields(self):
        kinds = [(k, k) for k in self.ammo_kinds()]
        return [
            Field('id', 'Number', 'readonly'),
            Field('name', 'Name', 'str', hint='in the editor and in messages'),
            Field('type', 'Type', 'choice', TYPES),
            Field('bag_name', 'Name in the bag', 'str', hint="printed under the map in the inventory "
                                                             "(Quest I's own spellings)"),
            Field('price', 'Price', 'int', hint='gold, in shops (empty: not sold)'),
            Field('view3d', 'In 3D', 'choice', ITEM_LOOKS, hint='how FPS mode shows it on the ground'),
            Field('req_str', 'Needs strength', 'int', when=is_(*WORN), default=0),
            Field('req_int', 'Needs intelligence', 'int', when=is_(*WORN), default=0),
            Field('power', 'Power', 'int', when=is_(*WORN), default=0,
                  hint="a weapon's damage; an amulet's added power (see below)"),
            Field('kind', 'Weapon kind', 'choice', KINDS, when=is_('weapon', 'launcher', 'shield'), default=0),
            Field('atk', 'Attack +', 'int', when=is_(*WORN), default=0),
            Field('def', 'Defence +', 'int', when=is_(*WORN), default=0),
            Field('warm', 'Weapon armour +', 'int', when=is_(*WORN), default=0, hint='stops weapon damage'),
            Field('marm', 'Magic armour +', 'int', when=is_(*WORN), default=0, hint='stops magic damage'),
            Field('str', 'Strength +', 'int', when=is_(*WORN), default=0),
            Field('int', 'Intelligence +', 'int', when=is_(*WORN), default=0),
            Field('dex', 'Dexterity +', 'int', when=is_(*WORN), default=0),
            Field('acc', 'Accuracy +', 'int', when=is_(*WORN), default=0),
            Field('fires', 'Fires', 'multi', kinds, when=is_('launcher')),
            Field('fps_attack', 'FPS mode attack', 'choice', [(None, '(by kind: thrust for spears, else swing; '
                                                                     'launchers shoot)'),
                                                              ('swing', 'swing'), ('thrust', 'thrust'),
                                                              ('shoot', 'shoot')], when=is_('weapon', 'launcher'),
                  hint='how the weapon in view moves when the hero attacks'),
            Field('fps_turn', 'FPS mode turn', 'int', when=is_('weapon', 'launcher'),
                  hint='degrees anticlockwise to stand the bag picture up in the hand (the crossbow: 90)'),
            Field('missile_anim', 'Hit animation', 'choice', MISSILES, when=is_('launcher')),
            Field('no_ammo_bonus', 'No poison bonus', 'bool', when=is_('launcher'),
                  hint="ammunition that doubles a launcher's power doesn't, with this one"),
            Field('ammo', 'Ammunition kind', 'readonly', when=is_('ammo')),
            Field('count', 'In this stack', 'readonly', when=is_('ammo')),
            Field('power_x2', 'Double power', 'bool', when=is_('ammo'), hint="doubles a launcher's power (poisoned arrows)"),
            Field('power_bonus', 'Adds its power to', 'choice', [(None, 'nothing'), ('melee', 'melee blows'),
                                                                 ('ranged', 'ranged shots')], when=is_('amulet')),
            Field('potion', 'Potion', 'choice', POTIONS + [
                (int(k), f'{k} {v.get("name", "")}') for k, v in sorted(
                    (self.app.project.quest.get('potions') or {}).items(), key=lambda kv: int(kv[0]))],
                  when=is_('potion'),
                  hint="the belt's potions 1-8 are the original's; 9 and 10 are defined on the Quest tab"),
            Field('key', 'Opens', 'choice', key_choices(self.app.project.quest, {
                'yellow': 'gold-key doors', 'red': 'red-key doors', 'blue': 'blue-key doors'}), when=is_('key'),
                  hint='yellow, red and blue are the original\'s; more colours are defined on the Quest tab'),
            Field('worn_colour', 'Colour on the hero', 'choice', COLOURS, when=is_(*WORN),
                  hint='armour or a cloak gives his cloak this colour; for other things, their colour on him '
                       '(empty: the commonest colour of its bag picture)'),
            Field('cape', 'Is a cape', 'choice', [(None, '(by its name)'), (True, 'a cape: worn behind him'),
                                                   (False, 'armour: worn on his body')], when=is_('armour'),
                  hint='a cape shows its inventory picture behind the hero; armour goes on his body'),
            Field('clasp_colour', 'Clasp colour', 'choice', COLOURS, when=is_('amulet'),
                  hint='the colour of the pixel under his chin while he wears it (empty: the amulet\'s colour on the hero)'),
            Field('clasp_when', 'Clasp changes when', 'choice',
                  [(None, '(never)'), ('always', 'always'), ('low_life', 'his life is low (a quarter)'),
                   ('hurt', 'he is hurt'), ('poisoned', 'he is poisoned'), ('shielded', 'a Shield spell is on him'),
                   ('invisible', 'he is invisible'), ('powered', 'a power potion works')], when=is_('amulet'),
                  hint='the circumstance that changes the clasp to the other colour'),
            Field('clasp_alt', 'Clasp then', 'choice', COLOURS, when=is_('amulet'),
                  hint='the colour it changes to (or flashes with) when that holds'),
            Field('clasp_mode', 'Clasp does', 'choice', [(None, 'changes colour'), ('flash', 'flashes between the two')],
                  when=is_('amulet'), hint='stays the other colour, or flashes between the two'),
            Field('worn_dx', 'Slide on hero: right', 'int', when=is_(*WORN),
                  hint='pixels to slide it right on the hero (negative: left); drag it in the hero preview'),
            Field('worn_dy', 'Slide on hero: down', 'int', when=is_(*WORN),
                  hint='pixels to slide it down on the hero (negative: up); drag it in the hero preview'),
            Field('worn_flip', 'Flipped on hero', 'bool', when=is_(*WORN),
                  hint='mirrored left to right where he wears or holds it'),
            Field('worn_behind', 'Behind the hero', 'bool', when=is_(*WORN),
                  hint='drawn behind his body instead of in front'),
            Field('show_on_hero', 'Shown on the hero', 'bool', default=True, when=is_(*WORN),
                  hint='the hero shows it on the map while he wears it (Worn on the hero picture, or a small copy of its map '
                       'picture)'),
            Field('quest', 'Quest item', 'bool', hint="can't be sold or dropped", when=is_('treasure', 'weapon', 'launcher', 'armour',
                                                                        'shield', 'helmet', 'amulet')),
            Field('regen', 'Heals each turn', 'int', when=is_(*WORN), hint='life gained every turn it is worn'),
            Field('mana_regen', 'Mana each turn', 'int', when=is_(*WORN), hint='mana gained every turn it is worn'),
            Field('thorns', 'Hurts attackers', 'int', when=is_(*WORN), hint='damage dealt to a creature that hits the hero'),
            Field('lifesteal', 'Steals life %', 'int', when=is_(*WORN), hint='percent of his melee damage the hero heals'),
            Field('sight', 'Sees further', 'int', when=is_(*WORN), hint='squares more in FPS mode'),
            Field('poison_immune', 'Poison cannot touch him', 'bool', when=is_(*WORN)),
            Field('see_invisible', 'Sees the invisible', 'bool', when=is_(*WORN)),
            Field('water_walk', 'Walks on water', 'bool', when=is_(*WORN),
                  hint='needs the water wall ticked "Is water" on the Tiles tab'),
            Field('stand_on', 'Does something on', 'choice', STAND_ON, when=is_(*WORN),
                  hint='while worn and he stands on it: blood, a decoration or floor, or an item lying there'),
            Field('stand_id', 'Which one (number)', 'int', when=lambda r: r.get('stand_on') in ('deco', 'floor', 'item'),
                  hint='the decoration, floor or item number (empty or 0: any item)'),
            Field('stand_effect', 'It does', 'choice', STAND_EFFECTS, when=has('stand_on')),
            Field('stand_amount', 'Amount (or turns)', 'int', when=has('stand_on'),
                  hint='life or mana a turn; for berserk, how many turns it lasts'),
            Field('light', 'Lights up (squares)', 'int',
                  hint='on a dark screen, he sees this many squares round him while he carries it (worn or in the bag)'),
            Field('makes_small', 'Makes him small', 'bool', when=is_(*WORN), hint='while worn (a ring of shrinking)'),
            Field('makes_giant', 'Makes him a giant', 'bool', when=is_(*WORN), hint='while worn (a belt of giants)'),
            Field('use.life', 'Used: restores life', 'int', when=lambda r: r.get('type') in EATEN,
                  hint='Enter on it in the inventory uses it up (food, a bandage); a minus hurts'),
            Field('use.mana', 'Used: restores mana', 'int', when=lambda r: r.get('type') in EATEN),
            Field('use.cure_poison', 'Used: cures poison', 'bool', when=lambda r: r.get('type') in EATEN),
            Field('use.message', 'Used: message', 'str', when=lambda r: r.get('type') in EATEN),
            Field('pickup.grow', 'Eaten: grows (turns)', 'int', when=lambda r: r.get('type') in EATEN,
                  hint='picked up with Enter, it is used at once (a mushroom)'),
            Field('pickup.shrink', 'Eaten: shrinks (turns)', 'int', when=lambda r: r.get('type') in EATEN),
            Field('pickup.life', 'Eaten: life', 'int', when=lambda r: r.get('type') in EATEN, hint='a minus hurts'),
            Field('pickup.mana', 'Eaten: mana', 'int', when=lambda r: r.get('type') in EATEN),
            Field('pickup.foresight', 'Eaten: foresight (turns)', 'int', when=lambda r: r.get('type') in EATEN),
            Field('pickup.poison', 'Eaten: poisons', 'bool', when=lambda r: r.get('type') in EATEN),
            Field('pickup.message', 'Eaten: message', 'str', when=lambda r: r.get('type') in EATEN),
            Field('element', 'Element', 'choice', ELEMENTS, when=is_('weapon', 'launcher', 'ammo'),
                  hint='what a hit adds: burns, poisons or freezes the creature, or heals the hero. '
                       'A bow and its arrows both count.'),
            Field('element_chance', 'Element chance %', 'int', when=has('element'), hint='of every hit (empty: always)'),
            Field('element_power', 'Element damage', 'int', when=lambda r: r.get('element') in ('fire', 'poison'),
                  hint='a turn, while it burns or is poisoned (empty: 3)'),
            Field('element_turns', 'Element turns', 'int', when=lambda r: r.get('element') in ('fire', 'poison', 'ice'),
                  hint='how long it burns, is poisoned or stays frozen (empty: 3)'),
        ]

    def after_change(self, row, key, old):
        if key == 'water_walk' and row.get('water_walk'):
            self._check_water()
        if key.startswith('element') and row.get('type') == 'ammo':      # every stack of the kind shoots alike
            for r in self.rows:
                if r is not row and r.get('type') == 'ammo' and r.get('ammo') == row.get('ammo'):
                    for k in ('element', 'element_chance', 'element_power', 'element_turns'):
                        if k in row:
                            r[k] = row[k]
                        else:
                            r.pop(k, None)
        if key == 'type':
            if row['type'] in WORN:
                for k in STATS:                        # worn things need every stat (the engine's table)
                    row.setdefault(k, 0)
                if row['type'] == 'launcher':
                    row['kind'] = 4
                    row.setdefault('fires', [])
            if row['type'] == 'potion':
                row.setdefault('potion', 1)
            if row['type'] == 'key':
                row.setdefault('key', 'yellow')
        if key == 'name' and row.get('bag_name') in (None, '', old):
            row['bag_name'] = row['name']              # the bag name follows the name while they match

    def label(self, row):
        return f'{row["id"]}  {row.get("name") or "(no name)"}'

    def new_row(self):
        v = self.app.project.next_id('items', 1001)       # new things start at 1001, clear of Quest I's
        row = {'id': v, 'name': 'New weapon', 'price': 10, 'type': 'weapon', 'bag_name': 'New weapon'}
        for k in STATS:
            row[k] = 0
        row['power'] = 4
        return row

    def new_ammo_kind(self):
        name = simpledialog.askstring('New ammunition', 'Its name (e.g. Darts):', parent=self)
        if not name:
            return
        name = name.strip()
        if name.lower() in (k.lower() for k in self.ammo_kinds()):
            messagebox.showerror('New ammunition', f'There is already ammunition called {name}.')
            return
        p = self.app.project
        first = p.next_id('items', 1001)
        while any(p.next_id('items', first + k) != first + k for k in range(20)):
            first += 1
        for n in range(1, 21):
            row = {'id': first + n - 1, 'name': f'{name}-{n:02d}', 'type': 'ammo', 'ammo': name.lower(),
                   'count': n, 'bag_name': name}
            if n == 20:
                row['price'] = 5
            self.rows.append(row)
        self.rows.sort(key=lambda r: r['id'])
        p.touch('items')
        self.app.changed()
        self.fill_list()
        self.select(first + 19)
        messagebox.showinfo('New ammunition', f'Made {name} in stacks of 1 to 20 (items {first} to {first + 19}). '
                                              f'Give the 20-stack a picture and a price; tick {name} under Fires '
                                              'on the launchers that shoot it.')

    def set_picture(self, folder, surface, is_bag=False):
        """A picture for an ammunition stack goes on every stack of that kind."""
        row = self.row
        super().set_picture(folder, surface, is_bag)
        if row.get('type') == 'ammo':
            p = self.app.project
            for r in self.rows:
                if r is not row and r.get('type') == 'ammo' and r.get('ammo') == row.get('ammo'):
                    p.set_picture(folder, r['id'], p.picture(folder, row['id']))
                    self.app.pictures_changed('item', r['id'])
            self.fill_list()

    def _check_water(self):
        """An item that walks on water needs a tile that is water: say so if none is marked, and offer to mark the
        walls named like water."""
        walls = self.app.project.tiles.get('walls', [])
        if any(w.get('water') or w.get('freezes_to') for w in walls):
            return
        named = [w for w in walls if 'water' in (w.get('name') or '').lower()]
        names = ', '.join(f'{w["id"]} {w.get("name")}' for w in named)
        if named and messagebox.askyesno('Walks on water', 'No tile is marked as water yet, so this would walk on '
                                         f'nothing. Mark these walls as water now?\n\n{names}'):
            for w in named:
                w['water'] = True
            self.app.project.touch('tiles')
            self.app.changed()
        elif not named:
            messagebox.showinfo('Walks on water', 'No tile is marked as water yet. On the Tiles tab, open the water '
                                                  'wall and tick "Is water": only then does this item walk on it.')

    def uses(self, row):
        return self.app.project.uses('item', row['id'])
