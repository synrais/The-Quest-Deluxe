# Mods

What The Quest Deluxe adds to the original game, each of which a pack can switch off. The editor's **Mods** tab has a check box for each (it also says what in the pack uses it); the choice is kept in the pack's `quest.json`:

```json
"mods": {"links": false, "thieves_and_drops": false}
```

A mod that is switched off makes the pack play as if it never used that feature. The files are untouched: a mod's items, creatures, tiles and level settings stay in the editor, and ticking the mod again brings them back. The original quest (`packs/TheQuest`) uses none of these fields, so it plays the same with every mod off.

Where a mod lives in the pack's data, the fields are left out when the pack loads; the others are switches in the engine (`pack.mod("key")`). The list is `engine/mods.py`.

## Seeing the game

### FPS mode (`fps_mode`)

F switches to the world through the hero's eyes: a retro raycaster drawn from the pack's own pictures, with the weapon in his hand, arrows in flight and the Map box. Off: the F key does nothing.

Switches off:

- in the engine: the F key

### Combat log (`combat_log`)

D shows "You hit the imp for 4." and the like over the bottom of the map, and numbers rising off whoever took a hit (settings.ini floating_numbers). Off: no log.

Switches off:

- in the engine: the D key and every log line

### The hero shows what he wears (`hero_gear`)

On the map the hero is drawn from a base figure with what he wears on him: a weapon in his hand, a shield, a helmet, armour, a cape (and its hood colour), an amulet on his clasp that can flash. Off: the original's drawing of the hero (settings.ini show_gear must be on too).

Switches off:

- item fields: `cape`, `hood_colour`, `show_on_hero`, `worn_colour`, `worn_dx`, `worn_dy`, `worn_rotate`, `worn_behind`, `worn_from`, `clasp_colour`, `clasp_when`, `clasp_alt`, `clasp_mode`
- in the engine: how the hero is drawn

## Building

### Ladders, stairs, exits to any level, entries (`links`)

Ladders, ropes, stairs, holes and jump pads that lead to another level (the Map tab's Link tool), exits that lead to any level or to a named entry of one, and levels with several entries. Off: they lead nowhere, and every exit goes on to the next level.

Switches off:

- level script settings: `LINKS`, `ENTRIES`

### Creatures on 2 x 2 squares (`big_creatures`)

A creature (`size` 2) fills 2 x 2 squares: found from any, moves whole, fights from its nearest square. Off: every creature is one square.

Switches off:

- creature fields: `size`

### Walls an item moves, walls that freeze (`item_walls`)

A boulder and a crowbar, a thorn hedge and a billhook: a wall that gives way to an item (`needs_item`), water that freezes to ice (`freezes_to`).

Switches off:

- wall fields: `needs_item`, `becomes`, `becomes_deco`, `consumes`, `message`, `blocked_message`, `freezes_to`

### Small and giant heroes (`size_changes`)

Potions and items that make the hero small (through small gaps) or a giant (smashing walls, taking up several squares).

Switches off:

- item fields: `makes_small`, `makes_giant`
- wall fields: `giant_breaks`, `small_only`
- quest.json: `giant_size`

### Peaceful screens (`peaceful_screens`)

Screens where people and allies leave monsters alone.

Switches off:

- level script settings: `PEACEFUL_SCREENS`

### Dark screens and light (`light_and_dark`)

Screens where only the hero shows, and items (a torch, a lantern) that light a few squares round him.

Switches off:

- item fields: `light`
- level script settings: `DARK_SCREENS`

### Things that happen where he stands (`stand_effects`)

Rage in blood, healing on a spring, lava that burns, an item that does something while he stands on another item.

Switches off:

- item fields: `stand_on`, `stand_id`, `stand_effect`, `stand_amount`
- floor and decoration fields: `hurts`, `heals`

### Underworld and respawn (`death_and_return`)

When the hero dies he wakes at a respawn square with a kit, or fights his way back from an Underworld level to his body.

Switches off:

- level script settings: `UNDERWORLD`, `UNDERWORLD_RETURN`, `UNDERWORLD_LIFE`, `UNDERWORLD_STORY`, `UNDERWORLD_KIT`, `UNDERWORLD_STRIP`, `REVIVE_LIFE`, `RESPAWN`, `RESPAWN_LIFE`, `RESPAWN_GOLD_LOSS`, `RESPAWN_LIMIT`, `RESPAWN_KIT`

## Items

### Powers while worn (`worn_powers`)

Items that heal him or give him mana each turn, hurt who hits him, steal life with his blows, let him see further or the invisible, keep poison off or walk on water.

Switches off:

- item fields: `regen`, `mana_regen`, `thorns`, `lifesteal`, `sight`, `poison_immune`, `see_invisible`, `water_walk`

### Fire, ice, poison and drain (`elements`)

Weapons, launchers and arrows that burn, freeze, poison or drain, creatures that resist them, spells that burn blood off the ground or freeze water.

Switches off:

- item fields: `element`, `element_chance`, `element_power`, `element_turns`
- creature fields: `resists`
- spell fields: `burns`, `freezes_water`

### Eat, drink and use effects (`item_effects`)

Any item that heals, restores mana, cures poison or makes him grow or shrink when it is used from the bag or picked up (`use`, `pickup`).

Switches off:

- item fields: `use`, `pickup`

### Potions 9 and 10, more key colours (`extra_potions_keys`)

Potions beyond the original's eight, and key colours beyond yellow, red and blue.

Switches off:

- quest.json: `potions`, `keys`

## Creatures

### Thieves and drops (`thieves_and_drops`)

Creatures that steal gold or drain mana, that drop gold or items when hit or killed (with chances), and the rules for what a hit leaves.

Switches off:

- creature fields: `steal_gold`, `drain_mana`, `hit_gold`, `hit_item`, `hit_item_chance`, `death_gold`, `hit_drops`

### New creature behaviour (`creature_behaviour`)

Creatures that only come for the hero within a range, run from him, rise again from blood, turn into another creature when hurt or killed, or burst into others.

Switches off:

- creature fields: `chase_range`, `flees_within`, `regenerates_from_blood`, `rise_limit`, `becomes_on_death`, `bursts_into`, `transforms_into`, `transforms_below`, `transforms_damage`

## Always on

### Everything is data in a pack

Items, creatures, classes, spells, tiles, stories, dialogue, shops and level scripts are plain files in a quest pack, which the editor changes. The original quest is the pack packs/TheQuest.

### Past the original's limits

More than 20 spells (a spell book with pages), new classes in class changes and the questionnaire, and levels beyond the seventh.

### The original's bugs, fixed

The Shield / Ring of Ice swap, the shop that remembers the last shop, the item in a tree and more. settings.ini (fixes) or the Quest tab chooses which.

### Display and sound choices

items drawn over the creatures, smooth scaling, render quality, FPS quality, fog and view distance, sound: settings.ini.

### Custom Maps and switching packs

Packs you make live in Custom Maps; P on the title and load screens switches between The Quest and them, each with its own saves.
