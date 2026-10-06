# The Quest Studio

The Quest Studio is the editor for The Quest Deluxe: a new, friendlier home for everything the old editor did, built so
that anyone can make levels, creatures and items without reading a manual. (The old editor, `run_editor.py`, is still
here and still works on the same quests.)

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
* **+** makes a blank level, a copy of the one you are on, or runs the wizard. **Play here** starts the game on the square
  you last clicked; **3D view** shows the level as FPS mode does.

### The level wizard
Six steps and a live picture that changes as you choose: the **place** (countryside, village, fortress, wilderness or maze;
how many screens; which corner the hero starts in), the **land** (rivers, lakes, forest, buildings, paths, a locked door and
its key, and exactly which of the quest's own tiles to use), **who lives there** (how hard; which creatures, or "the crowd
of level 3"; a boss; villagers), **loot** (gold, potions, gear, chests, a shop), the **story** (a name and the words shown
before the level) and a last look. **Roll again** makes a different level with the same settings, and the seed gets one
back. The result is whole and fair: the hero starts on open ground, the exit can be reached (with the key, if there is
one), nothing lies inside a wall, and shops have wares. The game's own engine has walked every kind from start to exit.

### Creatures, Items, Spells, Heroes, Tiles
A gallery of pictures on the left, the chosen one on the right: its picture (Paint, Import), its name, and every
field in groups that open and close. Sliders are for numbers worth dragging. **New** asks what kind it is:

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

* The Studio reads every field of items, creatures, spells and classes from the old editor's descriptions
  (`editor/*_tab.py`), so the two can never disagree about what a field is. Everything it writes is the same pack format
  ([QUEST_PACKS.md](QUEST_PACKS.md)); a level's name is a `TITLE` line in its script, which the game ignores.
* `studio/worldgen.py` is the level generator, `studio/doctor.py` the Quest Doctor and `studio/fightcalc.py` the fight
  check; none of them touches a window, and they are tested on their own.
* Tests: `xvfb-run python tests/test_studio.py` drives every page; `python tests/test_worldgen.py` generates levels and has
  the real game walk them.
