# Compare to The Quest DOS

A button in the Studio's top bar (also the gear menu and Ctrl+K) that runs **your pack's game and the original DOS game side by side,
fed the same keys**, so every difference between them can be seen, saved and reported.

1. Click **Compare to DOS**. Pick a level (1 to 7 are in the original), the square to start on (click it on a map of the level)
   and the hero: a new one of any class, or one of your saved games.
2. Two windows open: ours ("The Quest Deluxe - compare to DOS") on the left, the original in DOSBox on the right. **Type in our window.**
   Every key goes to both, one at a time, when both have finished the last.
3. The line under our picture says whether the key left them the same, or what differed. **F12** saves a bug report in the
   `compare reports` folder: both pictures and the differences side by side (pink), and every key pressed so far.

## How they are made to agree
* **One save.** The hero and the place come from a save file made on the original's own level. The original loads it through its Load
  Game screen (no intro, story or fade); ours starts from the same state. If you chose a saved game as the hero, his stats, bag and
  spells are carried over to level and square you picked. Your pack's game puts him on your pack's version of that level, so what you
  see differ is what your pack changed.
* **The dice.** The original keeps rand()'s 32-bit state in memory (Borland C's generator, the same as `engine/rules.py`). Before each
  key the Studio reads it out of DOSBox and puts it in our game; after the key it counts the dice each side rolled. A different number
  is reported ("The original rolled the dice 3 times for this key, ours 1"): it is a real difference in what happens.
* **Pictures.** Our drawing is exact to the original's. The two windows' pixels are compared (DOSBox writes the VGA colours as 80/248,
  ours as 84/252: the top five bits are compared).
* **Keys the original does not know** (F for the 3D view, D for the combat log and so on) are not sent to either.
* **The original's files are never touched.** `dos/TheQuest` is a read-only copy (checked against `dos/MANIFEST.sha256` before and after
  every run); each run is in a scratch copy that is deleted.

## What it has found
* The character sheet (C) closed only on Esc, C, Space or Enter in our game, but on **any key** in the original. Fixed here.
  (`TheQuestClassic/` has the same code and was left alone.)
* Small ones it reports and that are not fixed: the strip under the sheet (the skills line) is drawn one pixel wider by the original, and
  the original leaves a piece of the map frame on the right of the sheet. They show up as a few hundred pink pixels on those screens.

## Needs
* **DOSBox 0.74.** On Windows it is bundled in `dos/dosbox` (the official 0.74-3 files, GPL). On Linux/macOS install it
  (`apt install dosbox`). Linux also needs `xdotool` and ImageMagick (`apt install xdotool imagemagick`) to send keys and take
  pictures of DOSBox.
* The Windows side (finding DOSBox's window, posting keys to it, reading its memory) is written from Windows' documentation and has
  **not been tried on a Windows machine**. If keys do not arrive, set `DOS_INPUT=focus` (the key goes through the keyboard, and DOSBox
  is brought forward for it). The dice need DOSBox's memory; if it cannot be read the window says so and the comparison runs without
  matching dice.

## Test
`xvfb-run python tests/test_compare.py` runs the pieces, then (with DOSBox, xdotool, ImageMagick and a display) the real thing: a walk
and a fight on level 1 and a walk on level 2, where every key must roll the same dice and draw the same picture on both sides.
