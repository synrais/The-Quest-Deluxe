"""A compare loadout: the gear both heroes start in, chosen from the original's own items (so the DOS game can hold every piece).

A loadout is {'name', 'worn': {slot: item number}, 'bag': [item numbers]}. The same one is put on the hero given to the original (in the
save it loads) and on ours, so the two heroes wear and carry the same, and every fight, shop and character sheet starts equal.
Presets are kept in `Custom Maps/compare loadouts.json` (the Studio's Compare window edits them; "Send my edits" sends them).

Pure data: no windows. Needs only the original's items.json and the engine's slot places."""
from __future__ import annotations

import json
import os

ORIGINAL_PACK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'packs', 'TheQuest')
SLOTS = [('weapon', 'Weapon or launcher'), ('offhand', 'Shield'), ('helmet', 'Helmet'), ('armor', 'Armour'), ('amulet', 'Amulet')]
BAG_ROOM = 16
# which item types may go in which slot
FITS = {'weapon': ('weapon', 'launcher'), 'offhand': ('shield', 'weapon'), 'helmet': ('helmet',), 'armor': ('armour',), 'amulet': ('amulet',)}

BUILT_IN = {
    'Fighter': {'worn': {'weapon': 216, 'offhand': 303, 'helmet': 405, 'armor': 104, 'amulet': 503},
                'bag': [1, 2, 7, 8, 12, 13, 14]},
    'Archer': {'worn': {'weapon': 232, 'helmet': 402, 'armor': 101, 'amulet': 501}, 'bag': [640, 640, 1, 2, 7]},
    'Mage': {'worn': {'weapon': 214, 'helmet': 403, 'armor': 112, 'amulet': 505}, 'bag': [3, 4, 5, 1]},
    'Light and quick': {'worn': {'weapon': 205, 'offhand': 301, 'armor': 111}, 'bag': [1, 3]},
}


def original_items() -> dict:
    """{number: row} of the original's items (the only ones the DOS game knows)."""
    with open(os.path.join(ORIGINAL_PACK, 'items.json'), encoding='utf-8') as fh:
        return {r['id']: r for r in json.load(fh)['items']}


def file_path() -> str:
    from engine import pack
    return os.path.join(pack.CUSTOM_DIR, 'compare loadouts.json')


def user_presets(path: str | None = None) -> dict:
    try:
        with open(path or file_path(), encoding='utf-8') as fh:
            data = json.load(fh)
        return {k: v for k, v in (data.get('presets') or {}).items() if isinstance(v, dict)}
    except (OSError, ValueError):
        return {}


def presets(path: str | None = None) -> dict:
    """{name: {'worn', 'bag'}}: the built-in ones, then the person's own (a saved one with a built-in's name replaces it)."""
    out = {k: dict(v) for k, v in BUILT_IN.items()}
    out.update(user_presets(path))
    return out


def save_preset(name: str, worn: dict, bag: list, path: str | None = None):
    name = name.strip()
    if not name:
        raise ValueError('Give the loadout a name.')
    mine = user_presets(path)
    mine[name] = {'worn': {k: int(v) for k, v in worn.items() if v}, 'bag': [int(v) for v in bag if v]}
    _write(mine, path)


def delete_preset(name: str, path: str | None = None):
    mine = user_presets(path)
    if mine.pop(name, None) is not None:
        _write(mine, path)


def _write(mine: dict, path: str | None):
    path = path or file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump({'presets': mine}, fh, indent=1, sort_keys=True)
        fh.write('\n')


def problems(loadout: dict) -> list:
    """What is wrong with a loadout: an item the original does not have, one in the wrong slot, a bag that is too full."""
    items = original_items()
    out = []
    for slot, n in (loadout.get('worn') or {}).items():
        row = items.get(n)
        if row is None:
            out.append(f'item {n} is not in the original')
        elif row.get('type') not in FITS.get(slot, ()):
            out.append(f'{row.get("name")} does not go in the {slot} place')
    bag = loadout.get('bag') or []
    out += [f'item {n} is not in the original' for n in bag if n not in items]
    if len(bag) > BAG_ROOM:
        out.append(f'the bag holds {BAG_ROOM} things')
    return out


def apply(data, loadout: dict | None):
    """Put the loadout on a savefile.SaveData: the worn places, then the backpack (emptied first)."""
    if not loadout:
        return
    from engine import state
    places = {'weapon': state.SLOT_WEAPON, 'offhand': state.SLOT_OFFHAND, 'helmet': state.SLOT_HELMET, 'armor': state.SLOT_ARMOR,
              'amulet': state.SLOT_AMULET}
    for cell in places.values():
        data.bag[cell] = 0
    for slot, n in (loadout.get('worn') or {}).items():
        data.bag[places[slot]] = int(n)
    for cell in state.BACKPACK:
        data.bag[cell] = 0
    for cell, n in zip(state.BACKPACK, loadout.get('bag') or []):
        data.bag[cell] = int(n)


def describe(loadout: dict | None) -> str:
    if not loadout:
        return ''
    items = original_items()
    name = lambda n: items.get(n, {}).get('name') or f'#{n}'          # noqa: E731
    worn = ', '.join(name(n) for n in (loadout.get('worn') or {}).values())
    bag = ', '.join(name(n) for n in loadout.get('bag') or [])
    return f'{loadout.get("name", "a loadout")}: wearing {worn or "nothing"}; carrying {bag or "nothing"}'
