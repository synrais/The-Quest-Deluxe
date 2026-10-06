"""Mods: what The Quest Deluxe adds to the original game, each of which a pack can switch off (quest.json `mods`).

    "mods": {"links": false, "thieves_and_drops": false}

A mod that is switched off makes the pack play as if it never used that feature. For the ones that live in a pack's data
(an item's `regen`, a creature's `steal_gold`, a level's `LINKS` ...) the fields are simply left out when the pack is
loaded, so the editor still shows them and nothing is lost: switch the mod back on and they work again. The rest are
switches in the engine (FPS mode, the combat log, the hero showing what he wears). The Mods tab of the editor lists them
all with a check box each; docs/MODS.md describes them.

The original quest (packs/TheQuest) uses none of the data fields below, so it plays the same with every mod off.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Mod:
    key: str
    title: str
    about: str
    group: str
    items: tuple = ()          # item fields it adds
    creatures: tuple = ()      # creature fields
    spells: tuple = ()
    walls: tuple = ()          # tile fields (walls)
    floors: tuple = ()         # tile fields (floors and decorations)
    quest: tuple = ()          # quest.json keys
    constants: tuple = ()      # level script constants
    engine: str = ''           # what the engine checks (nothing to strip: the engine asks `pack.mod(key)`)
    switch: bool = True        # False: listed, but always on


MODS = [
    # ── seeing the game ───────────────────────────────────────────────────────
    Mod('fps_mode', 'FPS mode', 'F switches to the world through the hero\'s eyes: a retro raycaster drawn from the '
        'pack\'s own pictures, with the weapon in his hand, arrows in flight and the Map box. Off: the F key does nothing.',
        'Seeing the game', engine='the F key'),
    Mod('combat_log', 'Combat log', 'D shows "You hit the imp for 4." and the like over the bottom of the map, and numbers '
        'rising off whoever took a hit (settings.ini floating_numbers). Off: no log.', 'Seeing the game',
        engine='the D key and every log line'),
    Mod('hero_gear', 'The hero shows what he wears', 'On the map the hero is drawn from a base figure with what he wears '
        'on him: a weapon in his hand, a shield, a helmet, armour, a cape (and its hood colour), an amulet on his clasp '
        'that can flash. Off: the original\'s drawing of the hero (settings.ini show_gear must be on too).',
        'Seeing the game', items=('cape', 'hood_colour', 'show_on_hero', 'worn_colour', 'worn_dx', 'worn_dy', 'worn_rotate',
                                  'worn_behind', 'worn_from', 'clasp_colour', 'clasp_when', 'clasp_alt', 'clasp_mode'),
        engine='how the hero is drawn'),
    # ── building ──────────────────────────────────────────────────────────────
    Mod('links', 'Ladders, stairs, exits to any level, entries', 'Ladders, ropes, stairs, holes and jump pads that lead to '
        'another level (the Map tab\'s Link tool), exits that lead to any level or to a named entry of one, and levels with '
        'several entries. Off: they lead nowhere, and every exit goes on to the next level.', 'Building',
        constants=('LINKS', 'ENTRIES')),
    Mod('big_creatures', 'Creatures on 2 x 2 squares', 'A creature (`size` 2) fills 2 x 2 squares: found from any, '
        'moves whole, fights from its nearest square. Off: every creature is one square.', 'Building',
        creatures=('size',)),
    Mod('item_walls', 'Walls an item moves, walls that freeze', 'A boulder and a crowbar, a thorn hedge and a billhook: '
        'a wall that gives way to an item (`needs_item`), water that freezes to ice (`freezes_to`).', 'Building',
        walls=('needs_item', 'becomes', 'becomes_deco', 'consumes', 'message', 'blocked_message', 'freezes_to')),
    Mod('size_changes', 'Small and giant heroes', 'Potions and items that make the hero small (through small gaps) or a '
        'giant (smashing walls, taking up several squares).', 'Building',
        items=('makes_small', 'makes_giant'), walls=('giant_breaks', 'small_only'), quest=('giant_size',)),
    Mod('peaceful_screens', 'Peaceful screens', 'Screens where people and allies leave monsters alone.', 'Building',
        constants=('PEACEFUL_SCREENS',)),
    Mod('light_and_dark', 'Dark screens and light', 'Screens where only the hero shows, and items (a torch, a lantern) '
        'that light a few squares round him.', 'Building', items=('light',), constants=('DARK_SCREENS',)),
    Mod('stand_effects', 'Things that happen where he stands', 'Rage in blood, healing on a spring, lava that burns, '
        'an item that does something while he stands on another item.', 'Building',
        items=('stand_on', 'stand_id', 'stand_effect', 'stand_amount'), floors=('hurts', 'heals')),
    Mod('death_and_return', 'Underworld and respawn', 'When the hero dies he wakes at a respawn square with a kit, or '
        'fights his way back from an Underworld level to his body.', 'Building',
        constants=('UNDERWORLD', 'UNDERWORLD_RETURN', 'UNDERWORLD_LIFE', 'UNDERWORLD_STORY', 'UNDERWORLD_KIT',
                   'UNDERWORLD_STRIP', 'REVIVE_LIFE', 'RESPAWN', 'RESPAWN_LIFE', 'RESPAWN_GOLD_LOSS', 'RESPAWN_LIMIT',
                   'RESPAWN_KIT')),
    # ── items ─────────────────────────────────────────────────────────────────
    Mod('worn_powers', 'Powers while worn', 'Items that heal him or give him mana each turn, hurt who hits him, steal life '
        'with his blows, let him see further or the invisible, keep poison off or walk on water.', 'Items',
        items=('regen', 'mana_regen', 'thorns', 'lifesteal', 'sight', 'poison_immune', 'see_invisible', 'water_walk')),
    Mod('elements', 'Fire, ice, poison and drain', 'Weapons, launchers and arrows that burn, freeze, poison or drain, '
        'creatures that resist them, spells that burn blood off the ground or freeze water.', 'Items',
        items=('element', 'element_chance', 'element_power', 'element_turns'), creatures=('resists',),
        spells=('burns', 'freezes_water')),
    Mod('item_effects', 'Eat, drink and use effects', 'Any item that heals, restores mana, cures poison or makes him grow '
        'or shrink when it is used from the bag or picked up (`use`, `pickup`).', 'Items', items=('use', 'pickup')),
    Mod('extra_potions_keys', 'Potions 9 and 10, more key colours', 'Potions beyond the original\'s eight, and key '
        'colours beyond yellow, red and blue.', 'Items', quest=('potions', 'keys')),
    # ── creatures ─────────────────────────────────────────────────────────────
    Mod('thieves_and_drops', 'Thieves and drops', 'Creatures that steal gold or drain mana, that drop gold or items when '
        'hit or killed (with chances), and the rules for what a hit leaves.', 'Creatures',
        creatures=('steal_gold', 'drain_mana', 'hit_gold', 'hit_item', 'hit_item_chance', 'death_gold', 'hit_drops')),
    Mod('creature_behaviour', 'New creature behaviour', 'Creatures that only come for the hero within a range, run '
        'from him, rise again from blood, turn into another creature when hurt or killed, or burst into others.',
        'Creatures', creatures=('chase_range', 'flees_within', 'regenerates_from_blood', 'rise_limit', 'becomes_on_death',
                                'bursts_into', 'transforms_into', 'transforms_below', 'transforms_damage')),
    # ── always on ─────────────────────────────────────────────────────────────
    Mod('data_packs', 'Everything is data in a pack', 'Items, creatures, classes, spells, tiles, stories, dialogue, shops '
        'and level scripts are plain files in a quest pack, which the editor changes. The original quest is the pack '
        'packs/TheQuest.', 'Always on', switch=False),
    Mod('past_limits', 'Past the original\'s limits', 'More than 20 spells (a spell book with pages), new classes in class '
        'changes and the questionnaire, and levels beyond the seventh.', 'Always on', switch=False),
    Mod('bug_fixes', 'The original\'s bugs, fixed', 'The Shield / Ring of Ice swap, the shop that remembers the last shop, '
        'the item in a tree and more. settings.ini (fixes) or the Quest tab chooses which.', 'Always on', switch=False),
    Mod('player_settings', 'Display and sound choices', 'items drawn over the creatures, smooth scaling, render quality, '
        'FPS quality, fog and view distance, sound: settings.ini.', 'Always on', switch=False),
    Mod('custom_maps', 'Custom Maps and switching packs', 'Packs you make live in Custom Maps; P on the title and load '
        'screens switches between The Quest and them, each with its own saves.', 'Always on', switch=False),
]

BY_KEY = {m.key: m for m in MODS}
SWITCHABLE = [m for m in MODS if m.switch]


def off(quest: dict) -> set:
    """The mods a quest.json switches off."""
    given = (quest or {}).get('mods') or {}
    return {k for k, v in given.items() if v is False and k in BY_KEY and BY_KEY[k].switch}


def strip(pack) -> None:
    """Leave out of a loaded pack the fields of every mod it switches off (the files are untouched)."""
    pack.mods_off = off(pack.quest)
    for key in pack.mods_off:
        m = BY_KEY[key]
        for rows, names in ((pack.items.values(), m.items), (pack.creatures.values(), m.creatures),
                            (pack.spells.values(), m.spells), (pack.walls.values(), m.walls),
                            (pack.floors.values(), m.floors), (pack.decos.values(), m.floors)):
            for row in rows:
                for name in names:
                    row.pop(name, None)
        for name in m.quest:
            pack.quest.pop(name, None)


def uses(tables: dict, quest: dict, has_constant, mod: Mod) -> list:
    """What in a pack uses a mod, as words: ['3 items', '1 level script'] (empty: nothing). tables: {'items': [rows], ...};
    has_constant(name) -> how many levels set that constant."""
    out = []
    for label, rows, names in (('item', tables.get('items', ()), mod.items), ('creature', tables.get('creatures', ()), mod.creatures),
                               ('spell', tables.get('spells', ()), mod.spells), ('wall', tables.get('walls', ()), mod.walls),
                               ('floor or decoration', list(tables.get('floors', ())) + list(tables.get('decos', ())), mod.floors)):
        n = sum(1 for r in rows if any(name in r for name in names))
        if n:
            out.append(f'{n} {label}{"" if n == 1 else "s"}')
    if any(name in (quest or {}) for name in mod.quest):
        out.append('the quest settings')
    levels = max((has_constant(name) for name in mod.constants), default=0)
    if levels:
        out.append(f'{levels} level{"" if levels == 1 else "s"}')
    return out
