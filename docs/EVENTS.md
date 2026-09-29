# Level scripts (quests and events)

The original game hardcodes its whole story in C: `talk()`, `deadenemycheck()`, `main2()` and
`newmap()` in TheQuest.exe. The Quest II moves every one of those rules into small per-level script
files:

```
quest2/content/levels/common.qs     rules for every level (from deadenemycheck())
quest2/content/levels/level1.qs     ... level7.qs: the original story, ported
quest2/content/levels/level8.qs     a new level: add L00008.dat and (optionally) this file
```

The original seven were ported line by line from the decompiled code. Then they were checked
against the real exe, which runs in an emulator (`tools/re/verify_events.py` and
`tools/re/verify_deaths.py`). In thousands of random game states, every conversation and every
death gave exactly the same result: the message, the quest counters, reputation, gold, bag, map
and creatures.

## The language

A level script uses a small, safe subset of Python: `def` handlers, `if/elif/else`, `for` loops,
`and/or/not`, comparisons, arithmetic, assignments, and calls to the functions listed below.
Imports, file access and anything the engine doesn't provide are rejected when the level loads.

### Settings (top of the file)

```python
START = (5, 5)                 # where the hero starts
STORIES = [1]                  # story.dat entries shown on arrival (level 6: [6, 10, 11])
SHOPS = {(3, 2): 1}            # screen (column, row, 1-based) -> shop file S0000<level><n>.dat
TELEPORT = (20, 0)             # how far a teleporter pad (item 999) moves the hero
ASK_TO_LEAVE = True            # ask "Want to travel further?" at the exit (item 1000)
```

### Handlers

| Handler | When it runs |
|---|---|
| `talk(npc)` | The hero walks into a talking NPC. `x, y` is the NPC's square. Call `say(n)` to choose the `Talk.dat` message; the default is a random 1-3. It is also called by `talk(n)` from other handlers (for scripted scenes); then `x, y` is the hero's square. |
| `check(w)` | For each creature on the screen (index `w`), several times a turn. This covers scripted scenes, bosses and position triggers. |
| `dies(w)` | Creature `w` has died, before its body falls and its loot drops. |
| `before_pickup()`, `opened_chest()`, `took(item)` | Around the hero's Enter (pick-up) action. |
| `level_start()` | The level has just loaded. |
| `after_action(key)` | After every key press (`key` is `'space'` or `'key'`). |
| `killer_allowed()` | Return False to lock the killer switch. |

`common.qs` runs first, then the level's own handler with the same name.

### Variables

| Name | Meaning |
|---|---|
| `level` | The current level. |
| `m1`, `m2` | The two quest counters (the original's `st.mission1/2`). They reset to 0 on every level. |
| `rep`, `coins`, `killer` | Reputation, gold and the killer switch. |
| `x`, `y` | The event's square (see `talk`). |
| `hx`, `hy` | The hero's map square. |
| `ax`, `ay` | The hero's square on the screen (1-10). |
| `ems`, `mons` | The number of hostile creatures, and of all creatures, on the screen. |
| `attacker` | During `check`/`dies`: -1 if the hero dealt the blow, else a creature index. |

### Functions

| Function | What it does |
|---|---|
| `say(n)`, `said()` | Choose, or read, the message. |
| `talk(npc)` | Run the talk handler for `npc` and show its message. |
| `random(n)` | 0..n-1, using Borland's `rand()` (the same sequence as the original). |
| `has(item)`, `has_any(item)` | Is the item in the backpack / anywhere in the bag (worn items too; the off-hand is not checked, like the original)? |
| `take(item)`, `take_any(item)` | The same, but also removes the item. |
| `give(item)` | Put the item in the first free backpack square. Returns False if the backpack is full. |
| `put(rx, ry, item)` | Drop an item on the screen (at the nearest free square, the original way). |
| `remove(rx, ry)` | The creature at that screen square leaves. |
| `room(rx, ry)`, `map(x, y)` | A square: `.floor .wall .mon .item .gold .deco`, readable and writable. |
| `count(mon, x1, y1, x2, y2)` | How many squares in the map rectangle hold that creature. |
| `visited(sx, sy)` | Has the hero seen that screen? (1-based) |
| `enemies()`, `slot(k)` | The screen's creatures: `.type .x .y .life .mlife .atk .defense .power .range .warm .marm .att .moved` (x, y in screen coordinates). |
| `refresh()` | Rebuild the creature list after changing `room(...).mon`. |
| `change_rep(d)` | Reputation plus or minus, with the original message. |
| `hero_step(dx, dy)`, `poison()`, `hurt_hero(power, kind, w)` | Move the hero, poison them, or hurt them. |
| `autosave(slot)`, `next_level()` | Save the game, or go to the next level. |
| `effect(name, ...)` | One of the original's visual effects (e.g. `'dcast2'`). |
| `range()`, `len()`, `min()`, `max()`, `abs()` | As in Python. |

### Things the original does that scripts keep

- For the screen you're on, `map()` returns the squares as they were when you arrived. The
  original keeps a separate live copy of that screen. Use `room()` for the live squares.
- `talk()` on levels 1-4 is an if/else chain (the first match wins). On levels 5-7 every case is
  checked and the last one wins. The ported scripts keep each form.

## An example: a new quest on level 8

```python
START = (50, 50)
STORIES = []


def talk(npc):
    if x == 52 and y == 50 and npc == -6:          # the farmer next to the start
        if m1 == 0:
            say(10)                                # "Wolves took my sheep..." (Talk.dat: 8 -6 10)
        elif m1 == 1:
            say(11)                                # "Thank you! Take this."
            put(ax, ay, 208)
            change_rep(1)
            m1 = 2


def dies(w):
    if slot(w).type == 2 and m1 == 0:              # killing an orc counts as dealing with the wolves
        m1 = 1
```

The messages go in `Talk.dat` as `8 -6 10 "...;` lines, in the same format as the original levels.
