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
| `potions` | Potions 9 and 10, which the original doesn't have (1-8 are its own): `{"9": {"name": "Elixir", "colour": 10, "life": "full", "mana": 5, "cure_poison": true, "berserk": 5}}`. `life` and `mana` are `"half"`, `"full"` or an amount; `cure_poison` cures (a potion that only cures can only be drunk when poisoned); `berserk` is turns of doubled power and armour, like potion 8. Keys 9 and 0 drink them, the belt shows ten bottles, and items and shops can hold them (`"potion": 9`). Their counts go in the save's DELUXE block. |
| `keys` | Key colours past the original's yellow, red and blue: `{"green": 10, "purple": 5}`, the name and the EGA colour the key is drawn in. A key item (`"key": "green"`) opens locked walls with the same `key`; like the original's keys, they are lost on a new level. With any extra colour the key panel shows small keys, five to a row, grey until found. They go in the save's DELUXE block. |
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
| `type` | `potion`, `key`, `chest`, `teleporter`, `exit`, `armour`, `weapon` (melee), `launcher` (sling, bow), `shield`, `helmet`, `amulet`, `ammo`, `treasure` (goes in the backpack). |
| `req_str`, `req_int` | Needed to use it. |
| `atk`, `def`, `warm`, `marm`, `str`, `int`, `dex`, `acc` | What it adds while worn (attack, defence, weapon armour, magic armour, stats). |
| `power` | A weapon's damage; for amulets see `power_bonus`. |
| `kind` | Weapons: 0 normal, 1 double strike (1 in 5), 2 parry (1 in 5), 3 magic (ignores armour), 4 ranged, 5 two-handed, 6 two-handed with parry. |
| `potion` | For potions: its number 1-8 (the key that drinks it and its place on the belt). |
| `key` | For keys: `yellow`, `red` or `blue`, or a colour of quest.json's `keys`. |
| `ammo`, `count` | For ammunition: its kind (`arrows`, ...) and how many the stack holds (up to 20). A stack of each size is its own item. |
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

## spells.json

| Field | Meaning |
|---|---|
| `id`, `name` | The spell book holds 20 spells a page; a pack with more (ids past 20) gets more pages, and Left/Right in the book go on from page to page. F1-F9 can be bound to any spell. Spells past 20 are saved in the save file's DELUXE block. |
| `req_int`, `mana`, `range`, `power`, `duration` | `range` 0 = cast on the hero. |
| `effect` | `heal`, `bolt` (damage at a target), `teleport`, `shield`, `fire_shield`, `freeze`, `ward` (the 8 squares around the hero), `dark_hour` (the same, repeated, mana to 0), `invisibility`, `summon`, `drain`, `earthquake`. |
| `anim` | `[animation, arguments...]` from `engine/anim.py`. |
| `repeat` | How many times the animation (or the ward) repeats. |
| `creature` | What a `summon` brings. |
| `fizzle` | % chance the spell fails (Invisibility also fails under a shield). |
| `empties_mana` | Casting it leaves no mana. |
| `needs_target` | Only castable at a creature. |
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
| `role` | Decorations the engine puts down: `open_door`, `open_chest`, `remains`, `remains2`, `blood`, `bones`. |

Pictures: `sprites/floors/<id>.png`, `sprites/walls/<id>.png`, `sprites/decos/<id>.png`.

**FPS mode (the 3D view).** Deluxe draws the same grid through the hero's eyes (F in the game; M
shows or hides the screen from above in the corner). These fields say how things look there; all
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
