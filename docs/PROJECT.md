# The project: two editions, the decisions behind them, and what's next

## Two editions

**The Quest (classic)** is a preservation copy. Its job is to be the original: the same screens, rules,
random numbers, saves and bugs, proven against the original exe. It reads the original's own files
(`TheQuestClassic/packs/TheQuest`, the game as released), and it is **locked**: it only changes when it is
found to differ from the original.

**The Quest Deluxe** is where the game grows. It began as a copy of the classic engine and was changed
to read everything the original hardcodes from **quest packs**: items, creatures and their special
behaviours (named traits), classes and skills, spells and their effects, tiles, the story and
dialogue, shops and the level scripts. Its `packs/TheQuest` is the original quest, converted by
`TheQuestDeluxe/tools/make_pack.py`, and plays exactly like the classic port: the repository's
lockstep test and the exe verifiers check that. It is **standalone**: a copy of its folder alone plays
(`TheQuestDeluxe/tests/test_standalone.py` proves it on every run).

Why two: the frozen classic port keeps Deluxe honest. While Deluxe still plays Quest I exactly, the
lockstep test shows any change to it that isn't meant to change the game; and whatever Deluxe grows
into, the original survives unchanged.

## Decisions

- **The editor edits The Quest Deluxe only.** The classic edition can't be edited; that's how it stays
  locked. A future option is a "classic" profile for packs that only use what the original could
  express, with an export back to the original's file formats.
- **Everything a quest is made of is plain files** (JSON, text, PNG), so packs can be read, compared and
  kept in git by hand. [QUEST_PACKS.md](../TheQuestDeluxe/docs/QUEST_PACKS.md) documents every field.
- **Level scripts** replace the original's hardcoded checks: a small, safe subset of Python with
  handlers for the moments the original checks (talking, a death, a step, a new screen...).
  [EVENTS.md](../TheQuestDeluxe/docs/EVENTS.md).
- **The EGA look stays**: 640×480, 16 colours, 40×40 squares, Borland's fonts.

## The Quest Deluxe's additions

### The editor

Maps and level settings, items, creatures, classes, spells, tiles, shops, dialogue, stories and events,
a 16-colour painter for every picture, a 3D preview, new packs, and Play (F5) to test from the clicked
square. `TheQuestDeluxe/tests/test_editor.py` drives it with simulated clicks.

### FPS mode (F)

The world through the hero's eyes, as a turn-based, grid-step view in the style of an early-1990s PC
game:

- A raycaster draws the view at 200×200 and doubles it into the map area; walls are textured with the
  pack's own pictures.
- The ground and ceilings are drawn by turning a top-down picture of the nearby squares so the eye
  looks up it, then scaling one row of it per screen row.
- Trees, creatures, items and gold stand up as billboards; water and blood lie flat; carpeted rooms
  get a roof. Tiles and items can say how they look (`view3d`, `roof`), otherwise opaque wall pictures
  become blocks and the rest billboards.
- Distance fades out in a 4×4 ordered dither, in the EGA colours.
- The panel's Map box shows the current screen from above, with an arrow for the way the hero faces
  (M switches it back to the level map); out of FPS mode it is the original's level map.
- The weapon in hand at the bottom right (`engine/hands.py`): its bag picture, cut out, tilted and
  scaled up in whole pixels (nothing when the hand is empty). The original's white attack stroke on
  the target isn't drawn in FPS mode (it is still heard): the weapon shows the blow, and a miss
  carries it too far. A creature's stroke on the hero is drawn as he sees it: from in front it rises
  from the bottom of the view, from his right it comes from the left.
- Arrows, bolts and sling stones fly (`engine/missiles.py`): the original only draws where a shot
  lands; in FPS mode the shot first flies from the bow to the target in an arc, shrinking with
  distance (a miss flies on past it), or from a creature at the hero, growing (a miss whips past). It bobs as the hero steps, and swings, thrusts (spears, pikes, lances) or is drawn and
  let go (bows, slings) as he attacks. Only the picture moves; the rules don't know about it.
- The hero's bust in the panel, right of the coins and above the right-hand key, with no frame
  (`engine/face.py`, the picture `engine/assets/bust.png`, 11 x 11, drawn 3 times the size; a pack can
  have its own `sprites/bust.png`): the hood in the class colour, the eyes in guy2()'s colours
  (poison, killer, berserk), the necklace in the colour of the amulet worn, only the eyes when
  invisible.
- On a square, gold and items stand in front of the creature on it. The combat log's rising
  numbers (plain pixel text) are off unless settings.ini says `floating_numbers = on`.
- Steps and turns glide over 140 ms; a walking or turning key held down keeps going, one step or turn
  at a time. Turning is free (not a game action); a step is the classic move,
  so the rules don't change: `tests/test_view3d.py` plays the same random games from above and in FPS
  mode and requires identical game state after every key.
- The original's animations draw on the map from above, out of sight; what they change is carried into
  the view, at the creature they hit, or over the whole view when they hit the hero.

Two bugs were found in testing and fixed: facing west, the glide never arrived (the goal was +π, the
glide −π), which hung the game on the next step; and an animation with no level loaded crashed. The
test now walks and turns every way in real time with a watchdog.

### The combat log (D)

"You hit the imp for 4.", "The orc hits you for 3.", misses, parries, the Shield absorbing blows,
spells by name, creatures fighting each other, poison, deaths with the experience gained, pick-ups and
locked doors, over the bottom of the map; in FPS mode the damage can also rise off whoever took it (`floating_numbers`, off as shipped). It
only reports: `tests/test_combat_log.py` plays the same games with it off and on and requires the same
state after every key. It is off in scripted runs, so the lockstep screens still match the classic
port.

## What's next

1. **Lift The Quest Deluxe's limits.** The original's structures fix 20 spells, 8 potions and 3 key
   colours, and job changes and the creation quiz only know the first 4 classes. **Done**: the
   Deluxe save format (the original's save text, with a `DELUXE` block written only when a game goes
   past the original's limits, so Quest I saves stay identical), a spell book with pages for more than
   20 spells, potions 9 and 10 (keys 9 and 0), a pack's own key colours,
   and new classes in job changes (`"reclass": "stats"`) and the questionnaire
   (`TheQuestDeluxe/tests/test_limits.py`).
2. **Fix the original's bugs as a choice.** **Done**: `packs/TheQuest` stays exact, so the lockstep test
   keeps its meaning; quest.json's `fixes` (the editor's Quest tab) switches on seven fixes (the Shield /
   Ring of Ice swap, questionnaire ties, fault colours, the shop memory, the death scan, Load Game's
   gaps and the dialogue reader), so a "Quest I Deluxe" pack and new quests can have them
   (`TheQuestDeluxe/tests/test_fixes.py`), plus no blank rows in character creation's skill and fault lists and a pack's own map
   corrections (Quest I's item in a tree and missing shield). The player decides in
   `TheQuestDeluxe/settings.ini`: shipped with `fixes = on` (every fix, every pack, and "Bug fixes: on"
   on the title screen), or `off`, or `pack` to leave it to each pack. The tests never read it, so
   they still play `packs/TheQuest` exactly as the original. New packs made in the editor start with
   every fix on. [FINDINGS.md](FINDINGS.md) says which bug each fix covers.
3. **FPS mode, in stages.** The hero's eye colours (killer, berserk, poison) and Shield rings can't be
   seen in 3D. A first try, a portrait of the hero top left, was dropped. Stage 1 (**done**): the
   screen from above moved from the view's corner into the panel's Map box. Stage 2 (**done**): the
   weapon in view, bottom right, bobbing as the hero walks and swinging, thrusting or drawing as he
   attacks. Stage 3 (**done**): the hero's bust right of the coins: the hood in the class colour, the
   eyes in the state colours, the necklace in the amulet's colour, only the eyes when invisible.

## Sharing

The engines and the editor are this project's own work. `TheQuestClassic/packs/TheQuest` is the original game
and `TheQuestDeluxe/packs/TheQuest` is its content converted (Alex Kutsenok's maps, story, text and
pictures, and Borland's font files). Sharing either publicly needs the rights holder's permission; a
public release of The Quest Deluxe could instead ship only new quests.
