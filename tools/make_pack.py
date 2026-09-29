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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from quest2.formats import DataSource, level_filename  # noqa: E402
from quest2.bgi import FONT_FILES  # noqa: E402

OUT = os.path.join(ROOT, 'packs', 'quest1')
SPRITES = os.path.join(ROOT, 'sprites')
CONTENT = os.path.join(ROOT, 'quest2', 'content')
SPRITE_RE = re.compile(r'^(floor|wall|enemy|object|extra|spell)_(-?\d+)_?(?:\[(.*)\])?\.png$')
KIND_DIR = {'floor': 'floors', 'wall': 'walls', 'extra': 'decos', 'enemy': 'creatures', 'object': 'items',
            'spell': 'spells'}

ITEM_COLUMNS = ['req_str', 'req_int', 'atk', 'def', 'warm', 'marm', 'str', 'int', 'power', 'kind', 'dex', 'acc']
SPELL_COLUMNS = ['req_int', 'mana', 'range', 'power', 'duration']
CREATURE_COLUMNS = ['life', 'power', 'atk', 'def', 'warm', 'marm', 'range', 'att']


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


def write_text(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def write_json(path: str, data):
    write_text(path, json.dumps(data, indent=1, ensure_ascii=False) + '\n')


def compact_json(path: str, key: str, rows: list, comment: str):
    """One object per line: easy to read and to compare."""
    lines = [f'{{"_comment": {json.dumps(comment)},', f' "{key}": [']
    lines += [' ' + json.dumps(r, ensure_ascii=False) + (',' if i < len(rows) - 1 else '') for i, r in enumerate(rows)]
    lines += [' ]', '}']
    write_text(path, '\n'.join(lines) + '\n')


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
    ids = sorted(set(stats) | set(prices) | {n for (k, n) in names if k == 'object'} | set(bag_ids))
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
    spells = [{'id': r[0], 'name': SPELL_NAMES.get(r[0], ''), **dict(zip(SPELL_COLUMNS, r[1:]))}
              for r in src.numbers('Spells.dat')]
    compact_json(os.path.join(OUT, 'spells.json'), 'spells', spells,
                 'Spells (Spells.dat): required intelligence, mana, range (0 = on the caster), power, '
                 'duration. Icons: sprites/spells/<id>.png.')

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
                 'silences_witnesses. Pictures: sprites/creatures/<id>.png.')

    # ── map tiles ────────────────────────────────────────────────────────────
    tiles = {}
    for kind, key in (('floor', 'floors'), ('wall', 'walls'), ('extra', 'decos')):
        tiles[key] = [{'id': n, 'name': names[(k, n)]} for (k, n) in sorted(names) if k == kind]
    write_json(os.path.join(OUT, 'tiles.json'), tiles)

    # ── text: the original's own files, decoded (the game reads them character by character) ──
    write_text(os.path.join(OUT, 'text', 'talk.txt'), src.text('Talk.dat').replace('\r\n', '\n'))
    write_text(os.path.join(OUT, 'text', 'stories.txt'), src.text('story.dat').replace('\r\n', '\n'))
    write_text(os.path.join(OUT, 'text', 'questions.txt'), src.text('qs.dat').replace('\r\n', '\n'))

    # ── levels: map, script, shops ───────────────────────────────────────────
    level = 1
    while src.exists(level_filename(level)):
        d = os.path.join(OUT, 'levels', str(level))
        rows = [line.split() for line in src.text(level_filename(level)).splitlines() if line.split()]
        body = '\n'.join(' '.join(r) for r in rows)
        write_text(os.path.join(d, 'map.txt'),
                   '# x y floor wall item creature gold deco\n' + body + '\n')
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
    shutil.copyfile(os.path.join(CONTENT, 'levels', 'common.qs'), os.path.join(OUT, 'levels', 'common.qs'))

    # ── fonts ────────────────────────────────────────────────────────────────
    os.makedirs(os.path.join(OUT, 'fonts'))
    for f in FONT_FILES.values():
        with open(os.path.join(OUT, 'fonts', f), 'wb') as fh:
            fh.write(src.read(f))

    write_json(os.path.join(OUT, 'quest.json'), {
        'title': 'The Quest',
        'author': 'Alex Kutsenok',
        'year': 2001,
        'engine': 'deluxe',
        'format': 1,
        'levels': level - 1,
        'first_level': 1,
    })
    print(f'{OUT}: {len(items)} items, {len(spells)} spells, {len(creatures)} creatures, {level - 1} levels')


if __name__ == '__main__':
    main()
