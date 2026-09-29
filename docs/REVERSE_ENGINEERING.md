# The Quest: reverse-engineering notes

These notes describe what `TheQuest.exe` (Alex Kutsenok, 2001) does. They were recovered
with the tools in `tools/re/`. Function names are the original ones, from the
exe's own debug symbols. `random(n)` means a number from 0 to n−1.

## Build

- Borland C++ 3.1, 16-bit real-mode DOS, BGI graphics at 640×480 in 16 colours (EGA/VGA).
- Four source files: `RPG.CPP`, `ICONS.CPP`, `FUNCS.CPP` and `FUNCS2.CPP`. They use the
  Lawrenceville Press `vector`/`matrix` classes (a common high-school C++ library).
- Every sprite is drawn in code by its own function, for example `deer()`, `chest()` or
  `lockeddoor()`. The ripped PNGs in `sprites/` replace these.

## Data files

Every byte except space, CR and LF is stored as `char + 0x51`. Maps use the same cipher.

| File | Format |
|---|---|
| `L0000n.dat` | 10,000 lines: `x y floor wall item monster gold deco`. |
| `Talk.dat` | `level npcType msgIdx "text…;`. Continuation lines start with `"`. Level 0 holds shared chatter: messages 1–3 are chosen at random. Messages 10+ are scripted. |
| `story.dat` | A `id lineCount` header, then that many lines of text. |
| `qs.dat` | The personality quiz: question, three answers, and a score for each answer. |
| `MONSTERS.DAT` | `type life power atk def warm marm range att`. |
| `Items.dat` | `id reqStr reqInt atk def warm marm str int power kind dex acc`. Kind 3 is a magic weapon (ignores armor); kind 4 is ranged. |
| `Spells.dat` | `id reqInt mana …` (20 spells). |
| `S0000LN.dat` | The stock of shop N on level L. |
| `prices.dat` | `itemId price`. |

## Structs (from the debug types)

```c
struct square  { int t, s, m, i, g, d; };      // floor, wall, monster, item, gold, deco
struct heroo   { mlife, life, mmana, mana, bstr, bintl, bdex, bacc, dex, acc, intl, str,
                 def, atk, rep, power, warm, marm, level, exper, type, invisible, poisoned; };
struct inve    { bkey, rkey, ykey, coins, rose, red, purple, blue, white, cyan, yellow, black; };
struct skills  { amb, bar, sch, mem, mar, cow, hon, ras; };
struct statuss { mons, ems, killer, armboost, powboost, Shield, fShield, level,
                 mission1, mission2, saveslot, p1, p2, p3; };
struct monsters{ type, x, y, life, mlife, atk, def, power, range, warm, marm, att; };
```

Globals: `map` (100×100 squares), `room` (the current 10×10 screen, with a 0/11 border),
`carta` (the automap), `bag` (a 17×13 inventory grid), `book` (the spellbook), `enemies[100]`,
`X,Y` (absolute position), `ax,ay` (position within the screen), and `st`, `hero`, `inv` and `skill`.

### Tile values

- **wall:** a value ≥ 1 blocks movement (1–14 are graphics such as trees, water or walls).
  −1 is a door, −2/−3/−4 are locked doors (gold, red and blue key), and −5/−6 are fake
  walls that open when you walk into them.
- **monster:** a value > 0 is a monster type. −5 is a shopkeeper, and ≤ −6 is an NPC that
  talks. Values ≤ −100 are summoned allies.
- **item:** 1–8 are potions, 9 an emerald, 10 a level-up, 11 meat, 12/13/14 keys,
  15 a chest (holding `random(40)+80` gold), 16 a ruby, 17 seaweed, 101–680 equipment and ammo,
  999 a teleporter, and 1000 the level exit.
- **deco:** 1 is an open door, 2 an open chest, 3/5/6 bodies, and 4 blood.

### Equipment slots (`bag` cells)

The weapon is in `[12][4]` and the off-hand (shield or second weapon) in `[16][4]`. The
helmet is in `[14][2]`, the armor in `[14][4]` and the amulet in `[14][6]`. The backpack
is columns 12–15 of rows 8–11.

## Core rules

- **Derived stats (`statusupdate`):**
  - `dex = bdex + amulet.dex + helmet.dex` (INT works the same way), `acc = bacc + amulet.acc`,
    and `str = bstr + amulet.str`.
  - Melee: `atk = weapon.atk + dex + amulet.atk + 35`, plus the shield's atk.
  - Ranged: `atk = weapon.atk + 2·acc + amulet.atk + 15`, plus 30 with Marksmanship.
  - Cowardice halves atk when life ≤ 30% of maximum.
  - `def = offhand.def + dex + amulet.def + 10`, plus the weapon's def with Ambidexterity.
  - Weapon armor (warm) and magic armor (marm) add up over all worn items, and the Berserker
    potion doubles them. Power is the weapon's power, adjusted by some amulets and poison arrows.
- **Melee hit (`herohit` / `monhit`):** the attack hits if `random(100)+1 ≤ atk − target.def`.
  Damage is `power + random(2·(power/3)+1) − power/3`, minus the target's weapon armor. Magic
  weapons skip the armor. Monster types 23–25 hit against magic armor instead.
- **Ranged hit:** the attack hits if `(8 − dist)·10 + atk + 5 − def ≥ random(100)+1`, where
  `dist = round(sqrt(dx² + dy²))`.
- **`hurt(dmg, who, kind, attacker)`:** applies the same spread, then subtracts weapon armor
  (kind 0) or magic armor (kind 1). Kinds 2 and 3 ignore armor.
- **Poison:** costs `max(1, mlife/100)` life per turn.
- **Potions:** a half potion restores `max/2`, rounded up.
- **Creation:**

  | Class | Life | Mana | STR / INT / DEX / ACC | Starting equipment |
  |---|---|---|---|---|
  | Knight | 50 | 0 | 20 / 10 / 10 / 10 | club, buckler |
  | Mage | 20 | 30 | 10 / 20 / 10 / 10 | club, spells Heal, Flame and Teleport |
  | Rogue | 35 | 15 | 10 / 10 / 15 / 15 | club, sling, 20 pebbles |
  | Monk | 30 | 20 | 15 / 15 / 10 / 10 | Heal, Stoic Necklace |

  `creation()` offers the four classes or a personality quiz (`qs.dat`) that picks one. It then asks
  the player to **"Choose a skill:"** (Bargaining, Ambidexterity, Memorization, Marksmanship or
  Scholar; some depend on the class) and to **"Choose a fault:"** (Cowardice, Rashness or Honor).
  The class's own skill is always granted too: Knight Ambidexterity, Mage Memorization, Rogue
  Marksmanship, Monk Scholar. Knights can't choose Cowardice, Mages can't choose Rashness and Rogues
  can't choose Honor. `newgame()` also binds F1–F9 to spells 1–9. Everyone starts with one Full
  Restoration potion and needs 100 experience for level 2. Story 1 opens with lines about the new
  character ("You are ambidextrous." and so on).

### Quirks in the original (kept as-is)

- **Quiz ties favour the Monk.** Each answer adds 1000/100/10/1 to a total, and the biggest digit
  wins. A tie that involves the Monk, or any three- or four-way tie, gives a Monk.
  Knight/Mage, Knight/Rogue and Mage/Rogue ties are a coin flip.
- **Marksmanship can never be chosen as the extra skill.** It is only listed for Rogues, who
  already have it. Other classes can still move the cursor onto its empty row.
- **Fault colours on the character sheet:** when Cowardice is active (life ≤ 30%), the colour
  is left at yellow, so the Honor and Rashness lines below it come out yellow instead of red.
- **Invisible wraiths (monster 22) are never drawn**: `clean2()` has no case for them.
- **`Talk.dat` reading:** to skip a non-matching entry, `talk()` counts two `"` or `;`
  characters. Two-line entries have three, so the reader can fall out of step with the file. A
  one-line message is drawn at x = −3 (3 pixels off the left edge), keeping its visible quote marks.
  If no line matches, the original searches forever (the game hangs).
- **Shops:** `peddler()` builds the shop's file name in a buffer it never clears. On a screen
  that isn't in its list, the shop sells the last shop's stock, even from an earlier level. Before
  any shop has been visited it is empty.
- **`deadenemycheck()`** walks the creatures by index and removes the dead in place. So the
  creature that slides into a removed one's slot is skipped until the next check. Its scripted
  scenes (for example the level 1 bandit ambush) only fire while the screen has at least one
  creature.
- **Fatebringer** (level 6): when the Woman dies she becomes Fatebringer. The scan then restarts
  at index 1 (not 0), and later kills in that pass are credited to creature 0 instead of the hero.
- **The current screen's `map[]` is stale:** the original copies the screen into `room[]` on
  arrival and writes it back when you leave. Quest checks that read `map[]` (for example "is the
  -14 NPC still there?") see the screen as it was when you arrived.
- **`mastermind()` is the main menu loop** (title → New Game / Load Game / Credits / Quit), not a
  minigame. The ending plays the credits and returns to it.
- **The hero is moved by some conversations** (the level 1 farmer, the level 6 father). The move
  ignores walls.

## Screen drawing

Everything is drawn with BGI calls. `quest2/bgi.py` emulates the ones the game uses: Bresenham lines
(the pixels match the original), Borland's fill patterns, flood fill, and text in the shipped `.CHR`
stroke fonts and the 8×8 ROM font. `quest2/hud.py` ports `stats()`, `dlife2()`, `dmana2()`,
`dcoins()`, `dmoney()`, `dkeys2()`, `dmap()` and `dpotions2()` call for call. The fonts the game uses:
Gothic (4) for page titles, Complex (8) for the stat sheet, Simplex (6) for story and talk,
Triplex (1) for the spellbook, Triplex Script (7) for the message strip, and Sans (3) for gold.

### Animations and sound

The original has **no combat text**. Hits, misses, blocks, spells and deaths show only as short
animations drawn over the map, with PC-speaker tones. They block the game while they play, like
everything in the original. `quest2/anim.py` ports all of them call for call as generators that yield
each `delay()`, and `tools/re/verify_anims.py` checks each one against the exe: the same BGI calls,
tones and delays, in the same order, with the same `rand()` draws.

- **Hero melee (`main2`):** `ahit(square, side, 1)` (white stroke, high tone) on a hit and
  `bhit(square, side)` (grey disc) on a miss. The side is where the blow comes from: 1 right,
  2 below, 3 left, 4 above. There's a 100 ms pause around the Ambidexterity weapon swap and before a
  double strike. A ranged weapon in melee beeps (150 Hz). A magic weapon rings when it deals damage
  (`herohit`).
- **Enemy melee:** `ahit(hero, side, 2)` (low tone) on a hit, `bhit2(hero, side)` for a parry, and
  two falling tones when the Shield spell absorbs the blow (`monhit`, `hurt`). Before the enemies act,
  `main2` waits 100 ms (50 ms with no hostiles on screen).
- **Missiles:** `sthit` (sling), `arhit` (bows) and `bolthit` (crossbow). The hero's miss is
  `bhit(6)` plus a 150 Hz beep; a monster's miss shows nothing.
- **Spells (`cast`):** `dcast()` (the caster's eyes flicker) for every cast, then the spell's own
  animation. A fizzle is `dcast()` plus a 50 Hz beep. A spell that does no damage shows `bhit(5)`.
  Monsters' spells hurt first and animate after.
- **Deaths:** every death beeps (200 then 500 Hz, `deadenemycheck`). The hero's are `dying2()`
  ("You are bleeding!") and `death2()`. `death()` then asks "Want to load?". On No, a black box
  grows from the middle of the screen and the title menu returns.
- **Other beeps:** doors (400 Hz), picking things up (300/400), a full backpack (150), potions
  (740), conversations (a 500/600/500 chime), and the `reput2`, `honor`, `cantsave` and `noarrows2`
  warnings. The jingles are `song_key()` for a key, `song_jazz()` for a level-up, and
  `song_bevcop()` for a new level, except when leaving levels 5 and 7.
- **The hero (`guy2`)** is drawn in code, not from a sprite. While invisible **only the eyes are
  drawn**. The eyes are green when poisoned, red with the killer switch, and light red under a
  Berserker potion. The Shield spell adds a yellow triple ring, Shield of Fire a red one.
- **Sound on/off:** `asound()` reads `sound.txt` on every call and beeps only if it holds 1 (the
  manual: "1=sound, 0=no sound"). Quest II reads `sound.txt` from the game folder, then `data/`, then
  `TheQuest.zip` (which ships 1).
- **Kills (`monsdeath2`):** the hero's remaining exp-to-level goes down by the monster's
  experience value, and the loot table is rolled. Both are now in `quest2/content/monsters.json`.
- **Reputation:** killing an NPC while at least one other NPC is on the screen costs 3 reputation
  (the victim counts as a witness, so the check is `witness > 1`), and every NPC on the screen
  turns hostile. Killing a monster in front of NPCs while at reputation ≤ −4 wins back 1. At
  reputation ≤ −4, NPCs attack on sight, and each new level resets it to −3.
  Stealing (level 1 gold at (5,95); the level 4 chests and the items at (64,95) and (3,37)) and quest
  rewards in `talk()` change it too. Those are level scripts, so they're ported in Phase 4.
- **Honour (fault):** attacking or casting at an enemy sets `hon` 1→2. While `hon == 2` and hostiles
  remain, you can't leave the screen ("It is not honorable to flee from your enemy!"). A kill or a
  new screen resets it to 1.
- **Teleporter (item 999):** `teleporter1()` plays on the pad (after a 500 ms pause), then on level 5
  the hero moves 20 tiles east, and `teleporter2()` plays where they land. On other levels only the
  rings play.

## How levels and events work

`newmap()` increments `st.level` and writes `'0' + level` into `data\l00000.dat`. So **only
levels 1–9 are possible**, and **level 8 is hardcoded as "the ending"** (story 8, or 8 and 9
if `mission1 == 2`). Start positions for each level are hardcoded.

The story is **code, not data**. `talk()`, `deadenemycheck()`, `main2()` and `monsdeath2()`
contain long lists of checks like this one:

```c
if (st.level == 1 && st.mission2 == 0 && X > 80 && X < 91 && Y > 90) talk(3);   // bandit ambush
if (enemy.type == -7 && st.level == 6 && enemy.life < 1) { ...becomes Fatebringer (35)... }
if (enemy.type == 35 && st.level == 6) { talk(36); map[55][20].item = 1000; }  // exit appears
```

Quest state is just the two counters `st.mission1` and `st.mission2`, which reset on every level.
The Quest II replaces these checks with **data-driven event rules**: a trigger, conditions and
actions. The original 7 levels' events are ported into that format.
