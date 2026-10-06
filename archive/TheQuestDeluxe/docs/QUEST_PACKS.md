# Quest packs

The Quest Deluxe plays **quest packs**: folders under `packs/` that hold everything a quest is made of,
as plain JSON, text and PNG files. `packs/TheQuest` is the original The Quest, built from the original
game by `tools/make_pack.py` (it reads the classic edition, `../TheQuestClassic`); Deluxe playing it plays
exactly like the classic port, which the repository's `tests/lockstep.py` and the exe verifiers
(`TheQuestClassic/tools/re`, with `QUEST_ENGINE=deluxe`) check.

The classic port stays frozen as the faithful version. New stories, items, creatures, classes,
spells and mechanics go into packs and into Deluxe.

To play another pack: `QUEST_PACK=<folder or name under packs/> python run_deluxe.py`.

```
packs/<name>/
  quest.json          the quest: title, levels, start
  items.json          every item
  creatures.json      monsters, people and summoned allies
  spells.json         every spell
  classes.json        hero classes
  skills.json         skills and faults
  tiles.json          floors, walls, doors, decorations
  text/talk.txt       what people say
  text/stories.txt    the story screens
  text/questions.txt  the character-creation questionnaire
  levels/common.qs    events on every level
  levels/<n>/map.txt      the level's map
  levels/<n>/script.qs    the level's events (docs/EVENTS.md)
  levels/<n>/shops/<k>.txt  a shop's wares
  sprites/...         pictures
  fonts/*.CHR         Borland stroked fonts
```

The tables (`items.json`, `creatures.json`, ...) keep one entry per line, so they read and compare
well. Fields that are left out take the default given below.

## quest.json

| Field | Meaning |
|---|---|
| `title`, `author`, `year` | Shown in the editor. |
| `levels` | How many levels (`levels/1` .. `levels/<n>`). After the last one come the ending stories and the credits. |
| `first_level` | Where a new game starts. |
| `start_potions` | Potions a new hero carries: `{"potion number": count}`. |
| `potions` | Potions 9 and 10, which the original doesn't have (1-8 are its own): `{"9": {"name": "Elixir", "colour": 10, "life": "full", "mana": 5, "cure_poison": true, "berserk": 5}}`. `life` and `mana` are `"half"`, `"full"` or an amount; `cure_poison` cures (a potion that only cures can only be drunk when poisoned); `berserk` is turns of doubled power and armour, like potion 8; `grow` is turns the hero is a giant (hits half as hard again, smashes `giant_breaks` walls, bigger on the map and a high eye in FPS mode); a shrinking and a growing effect cancel each other. `shrink` is turns the hero is half size (a low eye in FPS mode, everything towering) and can pass `small_only` walls (he cannot be put out of one: the potion holds while he is inside); `foresight` is turns in which invisible creatures show for what they really are (as their `reveals_as` creature) and can be targeted. Keys 9 and 0 drink them, the belt shows ten bottles, and items and shops can hold them (`"potion": 9`). Their counts go in the save's DELUXE block. |
| `keys` | Key colours past the original's yellow, red and blue: `{"green": 10, "purple": 5}`, the name and the EGA colour the key is drawn in. A key item (`"key": "green"`) opens locked walls with the same `key`; like the original's keys, they are lost on a new level. With any extra colour the key panel shows small keys, five to a row, grey until found. They go in the save's DELUXE block. |
| `giant_size` | How many squares across a giant hero (a potion of gigantism, or an item with `makes_giant`) stands: 2 makes him take up 2 x 2 squares, his own and those right and below, so he can only go where all of it fits, and a gigantism potion needs room (it fails with "There is no room to grow here!"). Left out or 1: he is one square, only drawn bigger. |
| `mods` | Additions of The Quest Deluxe to switch off for this pack: `{"links": false}` (docs/MODS.md lists the keys; the editor's Mods tab sets them). Everything is on unless it says `false`. |
| `fixes` | The original's bugs to fix: `true` for all, or a list of: `shield_ice` (Shield and Ring of Ice each use their own power), `quiz_ties` (a questionnaire tie is drawn at random between the tied classes, not given to the Monk), `fault_colours` (Honor and Rashness stay red while Cowardice shows), `shop_memory` (a screen without a shop sells nothing, not the last shop's stock), `dead_scan` (the creature that slides into a dead one's place is checked at once, and a scan started over starts at the first creature), `load_gaps` (Load Game lists every saved game past a gap), `talk` (dialogue entries are found by their lines, one-line messages sit like two-line ones, and a missing line says nothing where the original hangs), `blank_rows` (character creation's lists have no blank row where a skill or fault is hidden from a class: Marksmanship from all but Rogues, the fault a class can't have; what is hidden stays hidden. A pack that wants everyone to be able to choose Marksmanship drops its `only_free`), `map` (the `map_fixes` are made). Absent in `packs/TheQuest`, which keeps every bug; a new pack made in the editor has `true`. The player's `settings.ini` can override it: `fixes = on` fixes everything in every pack, `off` nothing. |
| `map_fixes` | Corrections to the pack's maps, made when a level loads if the `map` fix is on: `[{"level": 6, "x": 24, "y": 82, "item": 0, "why": "..."}]`, setting any of `floor`, `wall`, `mon`, `item`, `gold`, `deco`. `packs/TheQuest` has the original's two slips: the item in a tree and the shield that doesn't exist, both removed. |
| `story_order` | Which skills and faults story 1 mentions, in order (their `story` lines in skills.json). |
| `reclass` | Whether the class follows the stats at each level-up. `true`: Quest I's rule, between classes 1-4 (a hero of a pack's own class keeps it). `"stats"`: among all the classes, the one whose starting strength, intelligence, dexterity and accuracy are in the proportions nearest the hero's (the hero's own class wins a tie). `false` or absent: never. The new class's free skill replaces the old one's, as in the original. |

## Numbers

Every item, creature, spell, class and tile has a number (`id`). New content can use any numbers,
with two conventions the engine and saves rely on:

- **Creatures:** above 0 is a monster, -1 to -99 a person (-5 is a shopkeeper), -100 and below a
  summoned ally. People talk when walked into; allies follow the hero and vanish when it leaves the
  screen.
- **Map squares:** 0 means "nothing" for walls, items, creatures, gold and decorations.

## items.json

| Field | Meaning |
|---|---|
| `id`, `name` | `name` is the item's name in the editor and in messages. |
| `bag_name` | The name the inventory prints under the map (Quest I's own spellings). |
| `price` | Shop price in gold. Potions cost 2 x (level - 1) times more after level 1; Bargaining takes 30% off everything else. |
| `type` | `exit`: the way on to the next level, unless the level's `LINKS` (docs/EVENTS.md) has an entry for its square: `(level,)` leads to ANY level's start, `(level, x, y)` to a square of one, so each exit of a level can lead somewhere of its own (the Map tab's Link tool sets it). `ladder`, `rope`, `stairs`, `hole`, `jump_pad`: stepping on one (or Enter on it) takes the hero to the square the level script's `LINKS` names (docs/EVENTS.md): another level, which is kept as he left it (also in saves), so a cellar, a tower or a building with floors can be made. A hole or a pad with no link back is one way. `potion`, `key`, `chest`, `teleporter`, `exit`, `armour`, `weapon` (melee), `launcher` (sling, bow), `shield`, `helmet`, `amulet`, `ammo`, `treasure` (goes in the backpack). |
| `req_str`, `req_int` | Needed to use it. |
| `atk`, `def`, `warm`, `marm`, `str`, `int`, `dex`, `acc` | What it adds while worn (attack, defence, weapon armour, magic armour, stats). |
| `power` | A weapon's damage; for amulets see `power_bonus`. |
| `kind` | Weapons: 0 normal, 1 double strike (1 in 5), 2 parry (1 in 5), 3 magic (ignores armour), 4 ranged, 5 two-handed, 6 two-handed with parry. |
| `potion` | For potions: its number 1-8 (the key that drinks it and its place on the belt). |
| `fps_attack` | Weapons and launchers: how the weapon in view moves in FPS mode when the hero attacks: `swing`, `thrust` or `shoot` (by default spears, pikes and lances, kind 3, thrust; other weapons swing; launchers shoot). |
| `fps_turn` | Weapons and launchers: degrees anticlockwise to stand the bag picture up in the hand (the crossbow: 90). A pack can instead draw the weapon as held: `sprites/hands/<id>.png`, upright, the grip at the bottom. |
| `fps_dx`, `fps_dy` | Weapons, launchers and shields: view pixels to move the item in the hero's hand in FPS mode (across, down; an off-hand weapon is mirrored). Set by dragging it in the Items tab's FPS preview. |
| `key` | For keys: `yellow`, `red` or `blue`, or a colour of quest.json's `keys`. |
| `ammo`, `count` | For ammunition: its kind (`arrows`, ...) and how many the stack holds (up to 20). A stack of each size is its own item. |
| `regen`, `mana_regen` | Worn items: life and mana the hero gains each turn. |
| `thorns`, `lifesteal` | Worn items: damage to a creature that hits the hero in melee; percent of his melee damage he heals. |
| `sight` | Worn items: squares further the eye sees in FPS mode. |
| `poison_immune`, `see_invisible`, `water_walk` | Worn items: poison cannot touch him; invisible creatures show (like foresight); walls with `freezes_to` (water) do not stop him. |
| `stand_on`, `stand_id`, `stand_effect`, `stand_amount` | Worn items: while worn, each turn the hero stands on `stand_on` (`blood`: any pile of blood, footprints or remains; `deco`, `floor`: the decoration or floor numbered `stand_id`; `item`: an item lying there, `stand_id` or any if 0), the item does `stand_effect` (`berserk`: the Berserker potion's doubled power and armour for `stand_amount` turns (at least 2); `heal`, `hurt`, `mana`, `drain_mana`: that much a turn; `poison`, `cure_poison`). |
| `cape`, `hood_colour`, `show_on_hero`, `worn_colour` (older: the amulet clasp; now `clasp_colour`), `worn_dx`, `worn_dy`, `worn_rotate`, `worn_behind`, `worn_from`, `clasp_colour`, `clasp_when`, `clasp_alt`, `clasp_mode` | Worn items, with settings.ini `show_gear = on` (the hero is then drawn from `engine/assets/hero_base.png`, or the pack's own `sprites/hero_base.png`: a hooded figure wearing nothing, his hood in his class's colour; a class's painted hero `sprites/heroes/<class number>.png` is used as his body instead, the shipped four are the bare heroes). `cape` (armour only; true/false, else by name) makes it a cape, and a cape's `hood_colour` (EGA 0-15) turns his hood that colour while he wears it. `worn_from` (`bag` or `ground`) says which picture he wears or holds, `worn_behind` (true/false) which side of his body it is drawn on; unsaid (`cape` not set), armour named cape, cloak, shawl, robe or mantle is worn BEHIND him as its inventory (bag) picture, laid on pixel for pixel, and anything else in front as its picture on the ground; `worn_dx`/`worn_dy` slide it and `worn_rotate` (a multiple of 45 degrees, clockwise) turns it (the Items tab's hero preview sets all of these: choose its picture beside the item's pictures, drag it, use the arrows, Rotate, In front / Behind); wearing nothing shows nothing: no cape until he puts one on. Other armour is laid on pixel for pixel like the rest and can be moved, but only the pixels on the hero's armour area show (his torso from chin to groin, not his arms; the rest is clipped away), as armour pictures rarely fit the sprite. A helmet, a weapon and a shield (placed once, for his LEFT hand, the screen's right, which is what the editor's preview shows: his right arm is left out there; in the weapon slot, his RIGHT hand, the screen's left, the game draws the mirror of it across his middle) are laid on him pixel for pixel as the item's picture on the ground; an amulet only colours the yellow clasp pixel under his chin: `clasp_colour` (else its colour on the hero); `clasp_when` (always, low_life, hurt, poisoned, shielded, invisible, powered) with `clasp_alt` makes it change to that colour while it holds, or flash between the two with `clasp_mode: flash`. `worn_colour` (EGA 0-15, else the commonest colour of the bag picture) colours the amulet's clasp. `show_on_hero: false` leaves an item off. |
| `light` | Any item: on a dark screen (`DARK_SCREENS`) the hero sees this many squares round him while he wears or carries it (the best of what he has; none: only his own square). |
| `makes_small`, `makes_giant` | Worn items: while worn the hero is small, or a giant (both: his own size). |
| `use` | Any item: `{"life": 20, "mana": 5, "cure_poison": true, "message": "..."}`. In the inventory (i), Enter on it in the backpack uses it up (food, a bandage, a mana root): `life` and `mana` are an amount, or `"half"` or `"full"`; the other effects of `pickup` work too (`grow`, `shrink`, `foresight`, `berserk`, `poison`). It cannot be worn. |
| `pickup` | Any item: `{"grow": 40, "life": 10, "message": "..."}`. Picked up with Enter it is used at once and gone (a mushroom): `grow` or `shrink` (turns), `life`, `mana`, `foresight` (turns), `poison` (true), `message`. |
| `element` | Weapons, launchers and ammunition: what a hit adds. `fire` and `poison` go on hurting for `element_turns` turns (3) at `element_power` (3) a turn; `ice` freezes the creature `element_turns` turns; `drain` heals the hero by half the damage. A bow's and its arrows' elements both apply. `element_chance`: percent of hits it takes hold on (100 if left out). Creatures whose `resists` lists the element shrug it off. |
| `fires` | For launchers: the kinds of ammunition it takes. |
| `missile_anim` | For launchers: the animation of a hit (`sthit`, `arhit`, `bolthit`). |
| `power_x2` | Ammunition that doubles a launcher's power ... |
| `no_ammo_bonus` | ... except with this launcher. |
| `power_bonus` | Amulets: `melee` or `ranged` blows get the amulet's power added. |
| `quest` | Can't be sold or dropped. |

Pictures: `sprites/items/<id>.png` on the map (40x40, transparent), `sprites/bag/<id>.png` in the
bag and the shops (a whole 40x40 cell, grey background included).

## creatures.json

| Field | Meaning |
|---|---|
| `id`, `name` | |
| `life`, `power`, `atk`, `def`, `warm`, `marm` | Stats (as the original's MONSTERS.DAT). |
| `range` | 1 = melee; more = it shoots (or casts, with `atk` 0) from that far. |
| `att` | Attitude: 9 hostile (sees 9 squares), 8 hostile and sees the invisible, -1 neutral (turns hostile when hit), -2 peaceful, -3 follows the hero, -4 a caster that never melees. |
| `exp` | Experience for killing it. |
| `loot` | Rules tried with roll = random(100) + 1; the first with lo < roll <= hi applies: `[lo, hi, "gold", n, base]` drops random(n) + base gold, `[lo, hi, "item", id]` drops an item. |
| `drop_on_level` | `{"level": item}`: always drops this item on that level. |

Traits (all optional):

| Trait | Meaning |
|---|---|
| `bleeds` | `false`: no blood when hit. |
| `corpse` | `body` (default), `bones` (the necromancer can raise these) or `none`. |
| `invisible`, `reveals_as`, `hides_as` | Not drawn or targeted; turns into the `reveals_as` creature when it attacks, and back (`hides_as`) when the hero leaves the screen. |
| `magic_attack` | Its blows are stopped by magic armour instead of weapon armour. |
| `poison_melee`, `poison_ranged`, `poison_cast` | Poisons the hero 1 time in n when that attack hits. |
| `missile_anim` | Its missile's animation. |
| `cast_anim` | Its spell's animation: `[name, arguments...]`. |
| `resists` | A list of elements (`fire`, `ice`, `poison`, `drain`) that weapons, arrows and spells with that element don't affect. |
| `size` | How many squares across (and down) the creature stands on: 2 is a giant on 2 x 2 squares. Place it on the map at its top-left square, with the others free and on the same screen; it moves, fights (from its nearest square), dies and is drawn as one creature, from any of its squares. Its picture is stretched to fit, or used as it is if it is `size` x 40 pixels square. |
| `becomes_on_death` | A creature number: it doesn't die, it turns into that creature (at full life, where it stood). The hero still gets the first form's experience and loot. |
| `bursts_into` | `{"12": 3, "13": 1}`: when it dies, that many of each creature spring up on free squares near its body. |
| `transforms_into`, `transforms_below`, `transforms_damage` | When it is hurt enough it becomes the creature `transforms_into`, at that creature's full life: `transforms_below` is the percent of its life at or under which, `transforms_damage` the damage taken in all (either). A second form can transform again. |
| `steal_gold`, `drain_mana` | `{"chance": 30, "min": 1, "max": 4}`: when its blow or shot hurts the hero, a `chance` percent (1-100) that it takes `min` to `max` gold (never more than he has; it carries it and drops it where it dies) or mana. The Gold and thieves section of the Creatures tab. |
| `hit_gold`, `hit_item`, `hit_item_chance` | Each time the hero hurts it in melee: `hit_gold` (same form as above) lets that much gold fall on its square; `hit_item` (an item number) falls with `hit_item_chance` percent (every time if left out). |
| `death_gold` | Same form: a `chance` percent that it leaves `min` to `max` gold when it dies, as well as its `loot`. |
| `hit_drops` | Rules like `loot` (`[lo, hi, "gold", n, base]` or `[lo, hi, "item", id]`), rolled each time it is hurt (not by burning or poison): it drops gold or an item on its square. |
| `rise_limit` | With `regenerates_from_blood`: how many times it can rise (1, 2 ...). Left out: for ever, while there is blood. |
| `chase_range` | A hostile creature only comes for the hero when he is within this many squares; further away it stays where it is. Left out: as far as it sees. |
| `flees_within` | A hostile creature runs from the hero when he is within this many squares, and fights only when cornered (archers and casters still shoot). |
| `regenerates_from_blood` | After it dies, the nearest pile of blood on the screen (blood, footprints, remains; not its own body) slides a square a turn towards the body, and when it lands the creature rises again at full life, if nobody stands there. `blood_range` limits how far from its body the blood counts (the whole screen if left out). It rises again every time it dies while there is blood in reach, the blood it spills when hit included. Fire spells with `burns` clear the blood and so starve it; with none in reach it stays dead. |
| `heals_allies` | Heals a wounded creature on its side instead of attacking. |
| `raises_dead` | Turns bones on the screen into this creature. |
| `explodes` | Blasts the hero this many times, then dies. |
| `drains_life` | Heals itself by the damage its spell does. |
| `deceiver` | Turns summoned allies into the creature `becomes`, with the stats given. |
| `rests_after_moving` | Doesn't attack in a turn it moved. |
| `animal` | Doesn't fight people; killing it earns no reputation. |
| `silences_witnesses` | Nobody reports a killing while it is on the screen. |
| `log_name` | How Deluxe's combat log names it ("The knight hits you for 7."); left out, its name in lower case. |

Pictures: `sprites/creatures/<id>.png`.

A hero class can be painted: `sprites/heroes/<class id>.png` (40 x 40, see-through where the floor shows) takes the place of the drawn hero (the original's guy2(), in the class colour). The editor's Classes tab paints it, starting from the drawn hero or from another class.

## spells.json

| Field | Meaning |
|---|---|
| `id`, `name` | The spell book holds 20 spells a page; a pack with more (ids past 20) gets more pages, and Left/Right in the book go on from page to page. F1-F9 can be bound to any spell. Spells past 20 are saved in the save file's DELUXE block. |
| `req_int`, `mana`, `range`, `power`, `duration` | `range` 0 = cast on the hero. |
| `effect` | `heal`, `bolt` (damage at a target), `teleport`, `shield`, `fire_shield`, `freeze`, `heal_target` (cast at any creature, ally, person or enemy: it gains `power` life, up to its full life), `resurrect` (cast at the body of a creature or person that died on this level: it rises and fights beside the hero, as a summoned ally does, until he leaves the screen, or with `follows: true` until it dies, going with him from screen to screen; `power` is the percent of its life it comes back with, 0 for all of it; a creature with `corpse: none` leaves no body and can't be raised), `disguise` (the hero becomes a random creature, from `creatures` or any monster that shows, for `duration` turns: monsters take him for one of their own and leave him alone, and he can still fight and cast; each friendly person near rolls `npc_anger` percent, 50 if left out, to turn on him, and people on screens he walks into roll too; it wears off when the turns are up), `shadow_clones` (an ally, `creature`, on each free square of the 8 around the hero; `clones_hero`: each has that percent of the hero's life, power, attack, defence and armour, and with a `duration` they fade after that many turns), `ward` (the 8 squares around the hero), `dark_hour` (the same, repeated, mana to 0), `invisibility`, `summon`, `drain`, `earthquake`. |
| `anim` | `[animation, arguments...]` from `engine/anim.py`. |
| `repeat` | How many times the animation (or the ward) repeats. |
| `creature` | What a `summon` brings. |
| `fizzle` | % chance the spell fails (Invisibility also fails under a shield). |
| `empties_mana` | Casting it leaves no mana. |
| `needs_target` | Only castable at a creature. |
| `burns` | A radius in squares (0 = the square hit): the spell burns the blood off the ground there (blood, footprints and remains; bones stay). Bolts, `ward` and `dark_hour` use it; a bigger spell gets a bigger radius. |
| `freezes_water` | A radius (0 = the square hit): water within it (a wall with `freezes_to`) turns to ice for the spell's `duration` turns (10 if it has none), then melts. Bolts and `freeze` use it; the water itself is a valid target. |
| `absorb_power_of`, `freeze_power_of` | Quest I's Shield and Ring of Ice read each other's power (a bug in the original; both are 10). |

Icons: `sprites/spells/<id>.png`.

## classes.json and skills.json

A class: `id`, `name`, starting `life`, `mana`, `str`, `int`, `dex`, `acc`; `growth` = [life, mana]
gained per level; `skill` = the skill it gets free; `no_skill` / `no_fault` = the skills / faults creation
doesn't offer it (a name, or a list: the Knight has `"no_fault": "cow"`); `look` =
how the hero is drawn (`colour`, `shield_and_sword`); `bag` = starting items by bag cell
`"column,row"` (12,4 weapon, 16,4 off hand, 14,2 helmet, 14,4 armour, 14,6 amulet, 12-15 x 8-11 the
backpack); `spells` = known from the start, in spell-book order; `reclass`: `false` = a hero of this class
keeps it and no hero becomes it at a level-up. Creation lists every class (more than ten sit closer
together).

skills.json lists the skills (`kind` `skill`) and faults (`kind` `fault`) in the order creation
offers them, with the `story` line story 1 prints. `only_free`: only comes free with a class.
What each skill does is part of the engine (Bargaining, Ambidexterity, Memorization, Marksmanship,
Scholar; Cowardice, Rashness, Honor).

## tiles.json

`floors`, `walls` and `decos`, each with `id`, `name` and:

| Field | Meaning |
|---|---|
| `solid` | Walls: blocks the way. |
| `door` | Walls: `plain` (opens when walked into; monsters open these too), `fake` (a secret wall that opens the same way), `locked` (needs the `key` of that colour). An opened door closes again as a plain door when the hero leaves the screen. |
| `map_colour` | `[EGA colour, priority]` on the automap; the floor's or the wall's, whichever has the higher priority (plain grass green otherwise). `map_colour_on_level` overrides it on one level. |
| `needs_item`, `becomes`, `becomes_deco`, `consumes`, `message`, `blocked_message` | Walls: walked into with the item `needs_item` in the bag (worn or carried), the wall becomes the wall `becomes` (0 or left out: nothing, so a boulder is moved), perhaps leaving the decoration `becomes_deco`, and the item is used up if `consumes`. `message` says so in the combat log; `blocked_message` is what walking into it says without the item. Give the wall `solid` so that nothing else passes. |
| `water` | Walls (with `solid`): it is water, and a hero wearing an item with `water_walk` walks across it (so does a wall that has `freezes_to`). |
| `giant_breaks` | Walls (with `solid`): a giant walks into it and it is smashed: it becomes `becomes` (nothing if left out), with `message`. For a thin wall or a barricade. |
| `small_only` | Walls (with `solid`): a hero under a potion of shrinking (`shrink`) walks through it; everyone else is stopped. For a crack in a rock or a mouse hole; the `billboard` look suits it in FPS mode. |
| `freezes_to` | Walls: the wall a freezing spell (`freezes_water`) turns this one into, e.g. water into a wall called Ice that isn't `solid`. The ice melts back when its turns are up (later if somebody stands on it). |
| `hurts`, `heals` | Floors and decorations: life the hero loses or gains each turn he stands on it (lava, a healing spring). |
| `role` | Decorations the engine puts down: `open_door`, `open_chest`, `remains`, `remains2`, `blood`, `bones`. |

Pictures: `sprites/floors/<id>.png`, `sprites/walls/<id>.png`, `sprites/decos/<id>.png`.

**FPS mode (the 3D view).** Deluxe draws the same grid through the hero's eyes (F in the game; the
panel's Map box shows the screen from above, M switches it to the level map; the hero's bust by the
coins is `sprites/bust.png` if the pack has one, else the engine's: red, EGA 4, is drawn in the class
colour, white, 15, in the eye colour, and yellow, 14, in the colour of the amulet worn). These fields say how things look there; all
are optional, so packs without them still work:

| Field | Meaning |
|---|---|
| `view3d` | Walls: `block` (a solid cube with the picture on each side), `billboard` (the picture standing in the middle of the square, like a tree) or `flat` (lying on the ground, like water). Left out, an opaque picture is a block and one with see-through pixels a billboard. Decorations: `billboard` (the default) or `flat` (blood, bones). |
| `roof` | Floors: the wall picture drawn overhead (indoors). Left out, the sky shows. A building's walls carry the roof of the room beside them. |

Items have a `view3d` too (items.json): `small` (half size, standing; the default), `billboard` (full
size; the default for chests) or `flat` (the default for stairs and teleporter pads). Creatures and
gold always stand up; invisible creatures don't show. A level's script can set `SKY_3D` and `FOG_3D`
(EGA colours; the fog is what the distance fades into, the sky's colour if left out) and `RANGE_3D`
(how many squares the eye sees, 10 if left out); quest.json can give defaults for all levels as
`"view3d": {"sky": 9, "fog": 9, "range": 10}`.

## levels

`levels/<n>/map.txt`: one line per square, `x y floor wall item creature gold deco` (x and y 1-100;
the map is 10 x 10 screens of 10 x 10 squares). Lines starting with `#` are comments.

`levels/<n>/script.qs` and `levels/common.qs`: the level's events and its settings (`START`,
`STORIES`, `SHOPS`, `TELEPORT`, `ASK_TO_LEAVE`, `LEAVE_JINGLE`, `PEACEFUL_SCREENS`, ...), in the
small script language described in docs/EVENTS.md.

`levels/<n>/shops/<k>.txt`: the wares of shop k, item numbers filling the shop's 4 x 10 cells in
order. `SHOPS` in the script says which screen has which shop.

## text

`talk.txt`: `level person index "first line` optionally followed by `"second line`, ending with `;`.
Level 0 lines are shared by every level; indices 1-3 are picked at random when someone chats, 10 and
up are said from scripts (`say(n)`).

`stories.txt`: `id lines` followed by that many lines of text. Story 0 opens a new game, 1 follows
character creation, the level's `STORIES` show before it, 8 and 9 end the game.

`questions.txt`: the questionnaire, 8 questions of 9 lines each (question, answers, and the score
lines). A score is the original's number (1000 Knight, 100 Mage, 10 Rogue, 1 Monk; the largest digit
of the total picks the class, with the original's tie rules) or, for a pack's own classes,
`class: points, ...` (`5: 2` or `1: 1, 5: 1`). Once any answer given is scored that way, the class
with the most points wins, the original's scores counting one point per digit, and a tie is drawn at
random.
