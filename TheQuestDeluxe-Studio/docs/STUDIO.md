# The Quest Studio

The Quest Studio is the editor for The Quest Deluxe, built so that anyone can make levels, creatures and items without
reading a manual.

Start it with **The Quest Studio.bat** (Windows) or `python run_studio.py`. The first time it asks which quest to open;
after that it opens the one you had open last. The first seven levels of The Quest are locked, so make your own quest
(**New quest** on the welcome screen): it starts as a copy of them, in `Custom Maps/`, and everything you change stays in
its folder.

## The ideas

* **Everything is saved as you go.** A moment after any change the quest is written to disk, and again when you leave.
  There is no Save button to forget (Ctrl+S also makes the zip of what you added, for sending to someone).
* **Everything can be undone.** Ctrl+Z and Ctrl+Y undo and redo any change on any page: a brush stroke, a renamed
  creature, a whole level made by the wizard, a deleted story. The top bar says what the next undo would undo.
* **Nothing is thrown away quietly.** Deleting asks first and says where the thing is used, and the Quest Doctor reads
  the whole quest and says, in words, what is missing or broken and takes you to the place to fix it.
* **Ctrl+K finds anything.** Type a level, creature, item, spell, story or command and press Enter.

## The pages

### Home
The quest at a glance: the Quest Doctor's verdict, what to do next, every level as a picture with where its exits lead,
buttons to make something, and your recent changes.

### World
Every level as a card on the left; the map in the middle; Paint, Level and Places on the right.

* **Tools** (also the keys B, E, R, L, G, I, S): brush, eraser, rectangle (hollow if you like), line, fill (Ctrl+click
  replaces every square like it on the level), pick (or right-click: take what is under the pointer), select (drag a box,
  then Ctrl+C, Ctrl+X, Ctrl+V, Delete, or drag it to move it; the arrow keys nudge it). Hold Shift with the eraser to rub out
  every layer. Space or the middle button pans; the wheel scrolls, Ctrl+wheel zooms.
* **Paint**: choose a layer (ground, walls, decoration, items, creatures, gold), then a picture. Ctrl+click more pictures to
  paint with a random mix. The eye hides a layer and the padlock protects it.
* **Level**: the level's name, where the hero starts, the stories shown before it, whether the exit asks first, the teleporter
  jump, a map of its ten by ten screens, the 3D sky and fog, and what happens when the hero dies there.
* **Places**: start, **exits** (each can lead to *any* level: its start, a named entry, or an exact square picked on a map of
  that level), stairs, ladders, ropes, holes and jump pads (with the way back made too if you like), named entries, the wake
  spot, shops and peaceful or dark screens.
* **+** makes a blank level, a copy of the one you are on, or runs the level wizard or the quest wizard. **Play here** starts the game on the square
  you last clicked; **3D view** shows the level as FPS mode does.

### The level wizard
Six steps and a live picture that changes as you choose: the **place** (countryside, village, fortress, wilderness, maze or caves;
how many screens; which corner the hero starts in), the **land** (rivers, lakes, forest, buildings, paths, a locked door and
its key, and exactly which of the quest's own tiles to use), **who lives there** (how hard; which creatures, or "the crowd
of level 3"; a boss; villagers), **loot** (gold, potions, gear, chests, a shop), the **story** (a name and the words shown
before the level) and a last look. **Roll again** makes a different level with the same settings, and the seed gets one
back. The result is whole and fair: the hero starts on open ground, the exit can be reached (with the key, if there is
one), nothing lies inside a wall, and shops have wares. The game's own engine has walked every kind from start to exit.

### The quest wizard
A whole quest in four steps, with a picture of every level before it exists. **Adventure**: a title (for a blank quest), a
journey (the classic road from a village through country, wilds and caves to a fortress; into the depths; the wild lands;
lost in the mazes; or surprise me), how many levels (2 to 12), how big each is, how hard it gets (a gentle climb, steady, or
steep) and whether the last level has a boss. **Levels**: the kind of place, size and name of each one, and a dice to roll
a different level of the same kind. **Story**: an opening, a page before each level and an ending, written from the places
and all editable (a page holds 15 lines; the ending is story 8, the opening story 0). **Make it**: where it goes (a blank
quest gets them as levels 1, 2, 3 ...; any other quest gets them after its last level) and whether to play the first one.
Creatures and wares get tougher and dearer from one level to the next, and a level's exit leads on to the next. It is one
Undo, and everything it makes is ordinary levels, creatures and stories to change. **New quest** offers it as the way to start.

### Merge, Import and Compare
* **Merge** (top bar, gear menu, Ctrl+K) brings things from another quest into the open one, in three steps: pick the quest (one of
  yours, The Quest, or a folder or zip from anywhere), tick what to bring (creatures, items, spells, hero classes, skills, floors, walls,
  decorations, any of its levels one by one, story pages, the everyday chatter, the quest settings), then look it over. Each thing is
  *new* (its number is free), *the same* (nothing to do) or a *clash* (your pack has something different under that number): a clash
  can be brought under a free number (every place it is used in what you bring follows it, in maps, shops, loot, class bags and
  summons), replace yours, or be left behind. The notes say what would be lost or changed, with an example ("Creature 1 \"Imp\" is
  replaced by \"Dragonling\"; it is used in level 1 map: 103 squares"). Levels go after your last one, with their shops, stories,
  what people say there, and exit links renumbered. It is one Undo, and your settings are only changed if you say so.
* **Import a quest from a folder or zip** (gear menu) copies it into Custom Maps (the original is never touched), mends it and opens it.
  Opening any old pack mends it first: files it lacks (skills, tiles, texts, fonts, level maps and scripts) are put in from The Quest and
  its level count is made to agree with its folders; what was done is said.
* **Compare to DOS** runs your game beside the original: [COMPARE.md](COMPARE.md).

### Creatures, Items, Spells, Heroes, Tiles
A gallery of pictures on the left, the chosen one on the right: its picture (Paint, Import), its name, **Put on a map**
(the World page with this one ready to paint with) and every field in groups that open and close. Sliders are for numbers worth dragging. **New** asks what kind it is:

* Creatures start from a kind that is already in the quest (brute, archer, mage, armoured, swarmer, thief, healer, undead,
  giant, boss, wild animal, villager), with numbers fitted to how tough you want it.
* The **Fight check** works out how the creature fares against any hero class at any level, with the game's own rules, and shows
  every level from 1 to 20 in colour. **Balance** sets the life and power so that hero loses about as much of his life as you
  say.
* Loot is edited as rules over the 100 numbers of the roll, with a strip showing what falls how often.
* Items show how they sit on the hero (drag them into place) and in the hand in FPS mode. New ammunition makes all twenty stacks.
* Tiles are floors, walls and doors, and decorations; walls can be water, doors, locked doors (with their key colour),
  boulders an item moves, and so on.

### Shops
Each shop's shelves as the game lays them out. Click things to put them on, click a shelf to take it off, drag to move it.
**Suggest wares** fills a shop with potions and gear that suit its level.

### Story & talk
**Stories** are the screens shown before a level (pick which level, and see the game's own page as you type; **Fit to the page**
wraps the words). **What people say** is each person's chit-chat and the lines events make them say, one card per line with a
preview of the strip as the game draws it. **The questionnaire** is the class quiz.

### Events
Each level's script, with line numbers, an outline of its handlers and a Check that reads it the way the game will. **Add an
event** builds a rule from menus (when, only if, then) and writes both the code and what people say. **Insert** puts an item,
creature, story or message number where the cursor is.

### Quest Doctor
Reads every level (the start, a way out, whether the exit can be reached, links and entries, shops, stories, the script),
every creature, item, spell, tile and hero, and lists problems as **must fix**, **probably a mistake** and **good to know**.
**Show me** goes there; **Fix it** repairs what it safely can; **Ignore** hides one for this quest. The number beside it in the
sidebar counts what needs you.

### Mods and Settings
**Mods** switches what The Quest Deluxe adds to the original on or off for this quest. **Settings** holds the title, author,
first level, how classes change, the potions a hero starts with, potions 9 and 10, key colours, which of the original's bugs are
fixed, and the Studio's own look (dark or light).

### The painter
**Paint** opens the painter: icon tools (pencil, eraser, line, rectangle, oval, fill, dither, swap a colour, select, pick), the
16 colours plus see-through (left click is the left button's colour, right click the right button's, X swaps them), mirror,
move, flip and turn, copy, cut and paste, undo and redo, and the picture standing on the quest's own floors beside it as you
paint. The pictures of the quest sit on the right: drag one onto yours to stamp it, double-click to start from it. Keys: B E L R O
G D W S I choose the tools.

## Keys

| Key | Does |
|---|---|
| Ctrl+K | Find anything, run a command |
| Ctrl+Z, Ctrl+Y | Undo, redo |
| Ctrl+S | Save now and make the zip |
| F5 | Play from the clicked square (or the level's start) |
| B E R L G I S | Map tools: brush, eraser, rectangle, line, fill, pick, select |
| Ctrl+C, Ctrl+X, Ctrl+V, Ctrl+A | Copy, cut, paste, select all (on the map) |
| + and - | Zoom the map |

## For the curious

* Every field of items, creatures, spells, classes and tiles is described once, in `core/fields/` (no windows there); the
  Studio builds its forms from those descriptions (`studio/schema.py`). Everything it writes is the same pack format
  ([QUEST_PACKS.md](QUEST_PACKS.md)); a level's name is a `TITLE` line in its script, which the game ignores.
* `studio/merge.py` (merging) and `studio/upgrade.py` (mending old packs) have no windows and are tested by `tests/test_merge.py`; `studio/worldgen.py` is the level generator (and plans a whole quest: `quest_params`), `studio/questwizard.py` and
  `studio/wizard.py` are its two wizards (both built on `studio/stepdialog.py`), `studio/doctor.py` the Quest Doctor and `studio/fightcalc.py` the fight
  check; none of them touches a window, and they are tested on their own.
* Tests: `xvfb-run python tests/test_studio.py` drives every page; `python tests/test_worldgen.py` generates levels and has
  the real game walk them, and play a whole generated quest from the first start to the credits.
