"""The Items tab: weapons, armour, shields, helmets, amulets, ammunition, potions, keys and treasures."""
from __future__ import annotations

from tkinter import simpledialog, messagebox

from .table_tab import TableTab, Field
from .tiles_tab import key_choices

TYPES = [('weapon', 'Weapon (melee)'), ('launcher', 'Launcher (sling, bow)'), ('ammo', 'Ammunition'),
         ('armour', 'Armour'), ('shield', 'Shield'), ('helmet', 'Helmet'), ('amulet', 'Amulet'),
         ('potion', 'Potion'), ('treasure', 'Treasure / quest item'), ('key', 'Key'), ('chest', 'Chest'),
         ('teleporter', 'Teleporter pad'), ('exit', 'Level exit')]
WORN = ('weapon', 'launcher', 'armour', 'shield', 'helmet', 'amulet')
KINDS = [(0, '0 normal'), (1, '1 double strike (1 in 5)'), (2, '2 parry (1 in 5)'), (3, '3 magic (ignores armour)'),
         (4, '4 ranged (a launcher)'), (5, '5 two-handed'), (6, '6 two-handed, parry')]
POTIONS = [(1, '1 Minor Health'), (2, '2 Full Health'), (3, '3 Minor Mana'), (4, '4 Full Mana'),
           (5, '5 Minor Restoration'), (6, '6 Full Restoration'), (7, '7 Cure Poison'), (8, '8 Berserker')]
MISSILES = [(None, '(none)'), ('sthit', 'a stone (sthit)'), ('arhit', 'an arrow (arhit)'), ('bolthit', 'a bolt (bolthit)')]
STATS = ['req_str', 'req_int', 'atk', 'def', 'warm', 'marm', 'str', 'int', 'dex', 'acc', 'power', 'kind']


def is_(*types):
    return lambda r: r.get('type') in types



ITEM_LOOKS = [(None, '(by type: stairs and pads flat, chests full size, the rest small)'),
              ('small', 'small: half size, standing'), ('billboard', 'full size, standing'),
              ('flat', 'flat: on the ground')]

class ItemsTab(TableTab):
    TABLE = 'items'
    ICON_LAYER = 'item'
    LIST_ICON = 'bag'                      # bag pictures read better than map pictures at list size
    PICTURES = [('On the map', 'items', False), ('In the bag and shops', 'bag', True)]
    INTRO = ('Everything the hero can find, carry, wear or buy. What an item does comes from its type and '
             'numbers; its pictures are 40 x 40 in the 16 EGA colours (imported pictures are converted). '
             'Ammunition comes in stacks of 1 to 20: each size is its own item (New ammo kind makes all 20).')

    def __init__(self, master, app):
        super().__init__(master, app)
        from tkinter import ttk
        ttk.Button(self.buttons, text='New ammo kind...', command=self.new_ammo_kind).pack(side='left', padx=2)

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
            Field('quest', 'Quest item', 'bool', hint="can't be sold or dropped", when=is_('treasure', 'weapon', 'launcher', 'armour',
                                                                        'shield', 'helmet', 'amulet')),
        ]

    def after_change(self, row, key, old):
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

    def uses(self, row):
        return self.app.project.uses('item', row['id'])
