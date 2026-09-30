"""Build packs/quest1, the Quest I content as a Quest Deluxe pack, from the original game.

    python tools/make_pack.py            ->  packs/quest1/

Sources: TheQuest.zip (the original's data files, decoded), quest2/content (the level scripts and
the monsdeath2() rewards ported from the exe) and sprites/ (the pictures, whose file names also
carry the names). The pack is plain text, JSON and PNG, so it can be read, edited and compared
by hand; docs/QUEST_PACKS.md describes every file. Deluxe playing this pack plays exactly like
the classic port (tests/lockstep.py checks that).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))                     # deluxe/
CLASSIC = os.path.join(os.path.dirname(ROOT), 'classic')      # the original's data and the port's sprites
sys.path[:0] = [ROOT, CLASSIC]

from quest2.formats import DataSource, level_filename  # noqa: E402
from quest2.bgi import FONT_FILES  # noqa: E402
from deluxe.packio import write_text, write_json, write_table, tiles_text, map_text  # noqa: E402

OUT = os.path.join(ROOT, 'packs', 'quest1')
SPRITES = os.path.join(CLASSIC, 'sprites')
CONTENT = os.path.join(CLASSIC, 'quest2', 'content')
SPRITE_RE = re.compile(r'^(floor|wall|enemy|object|extra|spell)_(-?\d+)_?(?:\[(.*)\])?\.png$')
KIND_DIR = {'floor': 'floors', 'wall': 'walls', 'extra': 'decos', 'enemy': 'creatures', 'object': 'items',
            'spell': 'spells'}

ITEM_COLUMNS = ['req_str', 'req_int', 'atk', 'def', 'warm', 'marm', 'str', 'int', 'power', 'kind', 'dex', 'acc']
SPELL_COLUMNS = ['req_int', 'mana', 'range', 'power', 'duration']
CREATURE_COLUMNS = ['life', 'power', 'atk', 'def', 'warm', 'marm', 'range', 'att']


# how the combat log (Deluxe) names creatures whose editor names tell variants apart
LOG_NAMES = {-102: 'summoned scorpion', -101: 'summoned stone knight', -100: 'summoned skeleton',
             -12: 'aristocrat', -11: 'aristocrat', 13: 'tribal elite', 16: 'pirate', 18: 'knight',
             19: 'knight', 20: 'knight', 21: 'knight', 22: 'wraith', 23: 'wraith', 24: 'Oculus Overlord',
             25: 'oculus', 26: 'elite archer', 27: 'archer', 38: 'cleric', 39: 'holy knight',
             40: 'stone knight', 43: 'Spider Demon Ruler', 44: 'kamikaze spider demon', 45: 'Death Bringer',
             46: 'Death Bringer', 47: 'pirate'}


def creature_traits(c: int) -> dict:
    """What the original hardcodes per creature type (combat.py, ai.py, rules.py, world.py), as
    named traits. Deluxe reads these; new creatures can mix them freely."""
    t = {}
    if c in (6, 7, -100, -101) or 28 <= c <= 34:
        t['bleeds'] = False                       # skeletons and stone creatures
        t['corpse'] = 'bones'                     # the necromancer can raise these
    if c in (22, 23, 46):
        t['corpse'] = 'none'
    if c == 22:
        t['invisible'] = True                     # not drawn, not targeted
        t['reveals_as'] = 23                      # ... until it attacks
    if c == 23:
        t['hides_as'] = 22                        # invisible again once the hero leaves the screen
    if c in (22, 23, 24, 25):
        t['magic_attack'] = True                  # its blows are stopped by magic armour
    if c in (12, -102):
        t['poison_melee'] = 2                     # poisons on a hit, 1 time in 2
    if c == 27:
        t['poison_ranged'] = 2
    if c == 33:
        t['poison_cast'] = 20
    missile = {3: 'sthit', 17: 'arhit', 26: 'arhit', 27: 'arhit', 30: 'arhit', 39: 'bolthit'}
    if c in missile:
        t['missile_anim'] = missile[c]
    cast = {5: ['afireball', 1], 8: ['aflame', 1], -11: ['aflame', 1], 11: ['alightning', 1], 31: ['adrain', 3],
            33: ['agflame', 1], 42: ['ainferno', 1], 43: ['ainferno', 1]}
    if c in cast:
        t['cast_anim'] = cast[c]
    if c == 38:
        t['heals_allies'] = True
    if c == 32:
        t['raises_dead'] = 33                     # turns bones into this creature
    if c == 44:
        t['explodes'] = 6                         # blasts the hero this many times, then dies
    if c == 31:
        t['drains_life'] = True                   # heals itself by the damage its spell does
    if c == 45:
        t['deceiver'] = {'becomes': 44, 'att': 9, 'power': 25, 'marm': 15, 'atk': 0, 'life': 40}
        t['rests_after_moving'] = True
    if c in (4, 12):
        t['animal'] = True                        # doesn't fight people; killing it earns no reputation
    if c == 35:
        t['silences_witnesses'] = True            # nobody reports a killing while it is on the screen
    if c in LOG_NAMES:
        t['log_name'] = LOG_NAMES[c]              # Deluxe's combat log: the name a player reads
    return t


AMMO_GROUPS = {0: 'pebbles', 1: 'arrows', 2: 'poison arrows', 3: 'bolts'}


def item_traits(i: int) -> dict:
    """What the original decides from an item's number (the hundreds, 230+, 600+, 900+), as named
    fields. Deluxe reads these, so new items can have any number."""
    from quest2.invshop import item_name
    t = {}
    if 0 < i < 9:
        t['type'], t['potion'] = 'potion', i          # drunk with key i; goes on the belt
    elif i in (12, 13, 14):
        t['type'], t['key'] = 'key', {12: 'yellow', 13: 'red', 14: 'blue'}[i]
    elif i == 15:
        t['type'] = 'chest'
    elif i == 999:
        t['type'] = 'teleporter'
    elif i == 1000:
        t['type'] = 'exit'
    elif 100 < i < 200:
        t['type'] = 'armour'
    elif 200 < i < 230:
        t['type'] = 'weapon'
    elif 230 <= i < 300:
        t['type'] = 'launcher'
    elif 300 < i < 400:
        t['type'] = 'shield'
    elif 400 < i < 500:
        t['type'] = 'helmet'
    elif 500 < i < 600:
        t['type'] = 'amulet'
    elif 600 < i < 700:
        g, n = (i - 601) // 20, (i - 601) % 20 + 1
        t['type'], t['ammo'], t['count'] = 'ammo', AMMO_GROUPS.get(g, f'group {g}'), n
    elif i >= 900:
        t['type'], t['quest'] = 'treasure', True       # a quest item: can't be sold or dropped
    elif i:
        t['type'] = 'treasure'
    fires = {230: ['pebbles', 'arrows'], 231: ['arrows', 'poison arrows'],
             232: ['arrows', 'poison arrows', 'bolts'], 233: ['bolts']}
    if i in fires:
        t['fires'] = fires[i]                         # main2(): which ammunition each launcher takes
        t['missile_anim'] = {230: 'sthit', 233: 'bolthit'}.get(i, 'arhit')
    if i in (230, 233):
        t['no_ammo_bonus'] = True                     # poisoned arrows don't double its power
    if 641 <= i <= 660:
        t['power_x2'] = True                          # doubles a bow's power
    if i in (503, 507, 511):
        t['power_bonus'] = 'melee'                    # adds its power to melee blows
    if i == 504:
        t['power_bonus'] = 'ranged'
    bag_name = item_name(i)
    if bag_name:
        t['bag_name'] = bag_name                      # the name inventory() prints under the map
    return t


def tile_traits(key: str, n: int) -> dict:
    """Walls, doors and locks (main2's movement), the automap colours (dmap()) and the
    decorations the engine puts down, as named fields."""
    t = {}
    if key == 'walls':
        if n >= 1:
            t['solid'] = True
        elif n == -1:
            t['door'] = 'plain'
        elif n in (-2, -3, -4):
            t['door'], t['key'] = 'locked', {-2: 'yellow', -3: 'red', -4: 'blue'}[n]
        elif n in (-5, -6):
            t['door'] = 'fake'
        colour = {2: [1, 1], 3: [10, 4], 4: [0, 5], -1: [0, 5]}.get(n)
        if 9 < n < 15:
            colour = [0, 5]
        if colour:
            t['map_colour'] = colour
        if n == 5:
            t['map_colour_on_level'] = {'5': [8, 2]}
        if n == 2:
            t['view3d'] = 'flat'                 # FPS mode: water lies on the ground
    elif key == 'floors':
        colour = {2: [8, 2], 7: [6, 3], 8: [6, 3], 6: [0, 5], 4: [0, 5]}.get(n)
        if colour:
            t['map_colour'] = colour
        if n in (4, 6):
            t['roof'] = 10                       # FPS mode: carpeted rooms are indoors
    else:
        t['role'] = {1: 'open_door', 2: 'open_chest', 3: 'remains', 4: 'blood', 5: 'remains2', 6: 'bones'}[n]
        if n >= 3:
            t['view3d'] = 'flat'                 # FPS mode: blood and remains lie on the ground
    return t


def spell_traits(n: int) -> dict:
    """cast(): what each spell does, as an effect with its parameters (magic.py runs the effects)."""
    return {
        1: {'effect': 'heal', 'anim': ['aheal']},
        2: {'effect': 'bolt', 'anim': ['aflame', 0]},
        3: {'effect': 'teleport'},
        4: {'effect': 'shield', 'anim': ['ashield', 1], 'absorb_power_of': 5},     # the original reads spell 5's power
        5: {'effect': 'freeze', 'anim': ['aicering'], 'freeze_power_of': 4},       # ... and this reads spell 4's
        6: {'effect': 'ward', 'anim': ['ablackward']},
        7: {'effect': 'invisibility', 'anim': ['ainvisibility'], 'fizzle': 50},
        8: {'effect': 'summon', 'creature': -100, 'anim': ['asskeleton', 1]},
        9: {'effect': 'bolt', 'anim': ['ainferno', 0]},
        10: {'effect': 'heal', 'anim': ['arestore']},
        11: {'effect': 'drain', 'needs_target': True},
        12: {'effect': 'bolt', 'anim': ['athunder'], 'repeat': 5},
        13: {'effect': 'fire_shield', 'anim': ['ashield', 2]},
        14: {'effect': 'bolt', 'anim': ['adeteriorate', 40], 'empties_mana': True, 'needs_target': True},
        15: {'effect': 'summon', 'creature': -101, 'anim': ['astoneknight']},
        16: {'effect': 'earthquake'},
        17: {'effect': 'heal', 'anim': ['acure']},
        18: {'effect': 'summon', 'creature': -102, 'anim': ['asscorpion']},
        19: {'effect': 'bolt', 'anim': ['adeaths']},
        20: {'effect': 'dark_hour', 'anim': ['adarkhour'], 'repeat': 6},
    }.get(n, {})


def compact_json(path: str, key: str, rows: list, comment: str):
    write_table(path, key, rows, comment)


def main():
    src = DataSource()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    # ── sprites: sprites/<kind>/<id>.png, names kept for the tables ──────────
    names: dict[tuple[str, int], str] = {}
    for f in sorted(os.listdir(SPRITES)):
        m = SPRITE_RE.match(f)
        path = os.path.join(SPRITES, f)
        if m:
            kind, n = m.group(1), int(m.group(2))
            names[(kind, n)] = m.group(3) or ''
            dest = os.path.join(OUT, 'sprites', KIND_DIR[kind], f'{n}.png')
        elif f.startswith('hero_') and f.endswith('.png'):
            dest = os.path.join(OUT, 'sprites', 'heroes', f[5:])
        elif f == 'gold.png':
            dest = os.path.join(OUT, 'sprites', 'gold.png')
        else:
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(path, dest)
    bag_ids = []
    for f in sorted(os.listdir(os.path.join(SPRITES, 'bag'))):
        if f.startswith('bag_') and f.endswith('.png'):
            n = int(f[4:-4])
            bag_ids.append(n)
            dest = os.path.join(OUT, 'sprites', 'bag', f'{n}.png')
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(os.path.join(SPRITES, 'bag', f), dest)

    # ── items: Items.dat, prices.dat, and every item that has a picture ──────
    stats = {r[0]: r for r in src.numbers('Items.dat')}
    prices = {r[0]: r[1] for r in src.numbers('prices.dat') if len(r) > 1}
    # the maps also hold two numbers the original has no data for: -5 (level 6, inside a tree) and 311 (a
    # blank "shield" on level 7); they're kept, typed by their number, so they behave as in the original
    on_maps = set()
    level = 1
    while src.exists(level_filename(level)):
        on_maps |= {int(line.split()[4]) for line in src.text(level_filename(level)).splitlines()
                    if len(line.split()) == 8}
        level += 1
    ids = sorted(set(stats) | set(prices) | {n for (k, n) in names if k == 'object'} | set(bag_ids) | on_maps - {0})
    ids = [0] + [i for i in ids if i != 0]
    items = []
    for i in ids:
        it = {'id': i, 'name': names.get(('object', i), '')}
        if i in prices:
            it['price'] = prices[i]
        if i in stats:
            it.update(dict(zip(ITEM_COLUMNS, stats[i][1:])))
        it.update(item_traits(i))
        items.append(it)
    compact_json(os.path.join(OUT, 'items.json'), 'items', items,
                 'Items: id, name, price (prices.dat) and the Items.dat columns: requirements, attack, '
                 'defence, weapon/magic armour, stat bonuses, power, weapon kind (0 normal, 1 double '
                 'strike, 2 parry, 3 magic, 4 ranged, 5 two-handed, 6 two-handed parry), type, and '
                 'the fields in docs/QUEST_PACKS.md (ammo, count, fires, quest, bag_name, ...). Pictures: '
                 'sprites/items/<id>.png on the map, sprites/bag/<id>.png in the bag and shops.')

    # ── spells ───────────────────────────────────────────────────────────────
    from quest2.rules import SPELL_NAMES
    spells = [{'id': r[0], 'name': SPELL_NAMES.get(r[0], ''), **dict(zip(SPELL_COLUMNS, r[1:])),
               **spell_traits(r[0])} for r in src.numbers('Spells.dat')]
    compact_json(os.path.join(OUT, 'spells.json'), 'spells', spells,
                 'Spells (Spells.dat): required intelligence, mana, range (0 = on the caster), power, '
                 'duration; effect (heal, bolt, teleport, shield, fire_shield, freeze, ward, dark_hour, '
                 'invisibility, summon, drain, earthquake) and its settings: anim = [animation, '
                 'arguments...], repeat, creature, fizzle (% chance), empties_mana, needs_target. '
                 'Icons: sprites/spells/<id>.png.')

    # ── creatures: MONSTERS.DAT, the monsdeath2() rewards, names ─────────────
    with open(os.path.join(CONTENT, 'monsters.json')) as fh:
        rewards = {int(k): v for k, v in json.load(fh).items() if not k.startswith('_')}
    mstats = {r[0]: r for r in src.numbers('MONSTERS.DAT')}
    cids = sorted(set(mstats) | set(rewards) | {n for (k, n) in names if k == 'enemy'})
    creatures = []
    for c in cids:
        cr = {'id': c, 'name': names.get(('enemy', c), '')}
        if c in mstats:
            cr.update(dict(zip(CREATURE_COLUMNS, mstats[c][1:])))
        cr.update(rewards.get(c, {}))
        cr.update(creature_traits(c))
        creatures.append(cr)
    compact_json(os.path.join(OUT, 'creatures.json'), 'creatures', creatures,
                 'Creatures: monsters (id > 0), people (-99..-1; -5 = shopkeeper) and summoned allies '
                 '(<= -100). MONSTERS.DAT stats: life, power, attack, defence, weapon/magic armour, '
                 'range (1 = melee), attitude. monsdeath2() rewards: exp, and loot rules [lo, hi, '
                 '"gold", n, base] / [lo, hi, "item", id] tried with roll = random(100) + 1 (the first '
                 'with lo < roll <= hi applies). Traits (docs/QUEST_PACKS.md): bleeds, corpse, invisible, '
                 'reveals_as, hides_as, magic_attack, poison_melee/ranged/cast, missile_anim, cast_anim, '
                 'heals_allies, raises_dead, explodes, drains_life, deceiver, rests_after_moving, animal, '
                 'silences_witnesses; log_name is how Deluxe\'s combat log names it. '
                 'Pictures: sprites/creatures/<id>.png.')

    # ── map tiles ────────────────────────────────────────────────────────────
    tiles = {}
    for kind, key in (('floor', 'floors'), ('wall', 'walls'), ('extra', 'decos')):
        tiles[key] = [{'id': n, 'name': names[(k, n)], **tile_traits(key, n)}
                      for (k, n) in sorted(names) if k == kind]
    tiles['_comment'] = ('Walls: solid (blocks the way), or door: plain (opens when walked into), fake (a '
                         'secret wall that opens the same way) or locked (needs the key of that colour). '
                         'map_colour: [EGA colour, priority] on the automap (the higher priority of the '
                         'floor and the wall wins; grass-green 2 at priority 0 otherwise); '
                         'map_colour_on_level overrides it on one level. Decorations: role is what the '
                         'engine uses them for (open_door, open_chest, remains, remains2, blood, bones). '
                         'FPS mode: view3d is how a wall or decoration shows in 3D (block, billboard or '
                         'flat; left out, opaque wall pictures are blocks and the rest billboards); roof '
                         'is the wall picture drawn overhead on a floor (indoors).')
    write_text(os.path.join(OUT, 'tiles.json'), tiles_text(tiles))

    # ── text: the original's own files, decoded (the game reads them character by character) ──
    write_text(os.path.join(OUT, 'text', 'talk.txt'), src.text('Talk.dat').replace('\r\n', '\n'))
    write_text(os.path.join(OUT, 'text', 'stories.txt'), src.text('story.dat').replace('\r\n', '\n'))
    write_text(os.path.join(OUT, 'text', 'questions.txt'), src.text('qs.dat').replace('\r\n', '\n'))

    # ── levels: map, script, shops ───────────────────────────────────────────
    level = 1
    while src.exists(level_filename(level)):
        d = os.path.join(OUT, 'levels', str(level))
        rows = [line.split() for line in src.text(level_filename(level)).splitlines() if line.split()]
        write_text(os.path.join(d, 'map.txt'), map_text(rows))
        with open(os.path.join(CONTENT, 'levels', f'level{level}.qs'), encoding='utf-8') as fh:
            script = fh.read()
        if level == 2:
            # monsmove(): on level 2's first screen people and allies leave the monsters alone
            script = script.replace('\nSHOPS', '\nPEACEFUL_SCREENS = [(1, 1)]   # screens where people and allies '
                                    "don't attack monsters\nSHOPS", 1)
            assert 'PEACEFUL_SCREENS' in script
        write_text(os.path.join(d, 'script.qs'), script.replace('\r\n', '\n'))
        for shop in range(1, 10):
            name = f'S0000{level}{shop}.dat'
            if src.exists(name):
                write_text(os.path.join(d, 'shops', f'{shop}.txt'), src.text(name).replace('\r\n', '\n'))
        level += 1
    with open(os.path.join(CONTENT, 'levels', 'common.qs'), encoding='utf-8') as fh:
        write_text(os.path.join(OUT, 'levels', 'common.qs'), fh.read())

    # ── fonts ────────────────────────────────────────────────────────────────
    os.makedirs(os.path.join(OUT, 'fonts'))
    for f in FONT_FILES.values():
        with open(os.path.join(OUT, 'fonts', f), 'wb') as fh:
            fh.write(src.read(f))

    # ── classes and skills: creation(), newgame(), levelup(), guy2() ─────────
    classes = [
        {'id': 1, 'name': 'Knight', 'life': 50, 'mana': 0, 'str': 20, 'int': 10, 'dex': 10, 'acc': 10,
         'growth': [7, 3], 'skill': 'amb', 'no_fault': 'cow', 'look': {'colour': 5, 'shield_and_sword': True},
         'bag': {'12,4': 201, '16,4': 301}, 'spells': []},
        {'id': 2, 'name': 'Mage', 'life': 20, 'mana': 30, 'str': 10, 'int': 20, 'dex': 10, 'acc': 10,
         'growth': [1, 5], 'skill': 'mem', 'no_fault': 'ras', 'look': {'colour': 4},
         'bag': {'12,4': 201}, 'spells': [1, 2, 3]},
        {'id': 3, 'name': 'Rogue', 'life': 35, 'mana': 15, 'str': 10, 'int': 10, 'dex': 15, 'acc': 15,
         'growth': [4, 4], 'skill': 'mar', 'no_fault': 'hon', 'look': {'colour': 8},
         'bag': {'12,4': 201, '12,8': 230, '13,8': 620}, 'spells': []},
        {'id': 4, 'name': 'Monk', 'life': 30, 'mana': 20, 'str': 15, 'int': 15, 'dex': 10, 'acc': 10,
         'growth': [3, 3], 'skill': 'sch', 'look': {'colour': 15},
         'bag': {'12,4': 201, '14,6': 502}, 'spells': [1]},
    ]
    compact_json(os.path.join(OUT, 'classes.json'), 'classes', classes,
                 'Hero classes: starting life, mana and stats; growth = [life, mana] gained per level; '
                 'skill = the skill it gets free (skills.json); no_fault = the fault it may not take; '
                 'look = how guy2() draws it (body colour, the Knight\'s shield and sword); bag = starting '
                 'items by bag cell "column,row" (12,4 weapon, 16,4 off hand, 14,2 helmet, 14,4 armour, '
                 '14,6 amulet, 12-15,8-11 backpack); spells = known at the start, in spell-book order.')
    skills = [
        {'id': 'bar', 'name': 'Bargaining', 'kind': 'skill', 'story': 'You are good at bargaining.'},
        {'id': 'amb', 'name': 'Ambidexterity', 'kind': 'skill', 'story': 'You are ambidextrous.'},
        {'id': 'mem', 'name': 'Memorization', 'kind': 'skill', 'story': 'You excel at spell memorization.'},
        {'id': 'mar', 'name': 'Marksmanship', 'kind': 'skill', 'story': 'You excel at marksmanship.',
         'only_free': True},
        {'id': 'sch', 'name': 'Scholar', 'kind': 'skill', 'story': 'You are a scholar.'},
        {'id': 'cow', 'name': 'Cowardice', 'kind': 'fault', 'story': 'You are a coward.'},
        {'id': 'ras', 'name': 'Rashness', 'kind': 'fault', 'story': 'You are often very rash.'},
        {'id': 'hon', 'name': 'Honor', 'kind': 'fault', 'story': 'You are extremely honorable.'},
    ]
    compact_json(os.path.join(OUT, 'skills.json'), 'skills', skills,
                 'Skills and faults, in creation()\'s order. What each does is part of the engine '
                 '(docs/QUEST_PACKS.md); story = the line story 1 prints about it. only_free: it can only '
                 'come free with a class, and is only listed for that class.')

    write_json(os.path.join(OUT, 'quest.json'), {
        'title': 'The Quest',
        'author': 'Alex Kutsenok',
        'year': 2001,
        'engine': 'deluxe',
        'format': 1,
        'levels': level - 1,
        'first_level': 1,
        'start_potions': {'6': 1},
        'story_order': ['amb', 'sch', 'mar', 'mem', 'bar', 'ras', 'cow', 'hon'],
        'reclass': True,
    })
    print(f'{OUT}: {len(items)} items, {len(spells)} spells, {len(creatures)} creatures, {level - 1} levels')


if __name__ == '__main__':
    main()
