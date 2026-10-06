# Compare to The Quest DOS

A button in the Studio's top bar (also the gear menu and Ctrl+K) that runs **your pack's game and the original DOS game side by side,
fed the same keys**, so every difference between them can be seen, saved and reported.

1. Click **Compare to DOS**. Pick a level (1 to 7 are in the original) and the hero (a new one of any class, or one of your saved
   games). Starting asks which square to start on: click it on a map of the level.
2. Two windows open: ours ("The Quest Deluxe - compare to DOS") on the left, the original in DOSBox on the right. **Type in our window.**
   Every key goes to both, one at a time, when both have finished the last.
3. The line under our picture says whether the key left them the same, or what differed. **F12** saves a recording (below).

## Recording what you find
Everything you do is recorded as you go. When you see a difference, press **F12**: a short form asks a few questions (your name, what
looked wrong, which one looked right, how bad, what you were doing, whether it happens every time) and saves one zip in
`Custom Maps/compare zips`. Closing the window offers to save when the recording has differences in it. **Send my edits** sends the
`compare zips` folder with everything else, so a brother can record and the recording arrives with his edits.

What is in the zip, and why it is small and still exact to the pixel: both games start from one save and the original's dice are put in
ours before every key, so the same start, keys and dice give the same game again. So the zip holds the start (the save the original
loaded, the level and square, the dice it began with), every key with its time, a line of facts per key (the dice each side rolled, how many
pixels differ, a CRC-32 of each picture's exact pixels, where the hero stood, his life, what the game said), and the pictures
themselves (lossless PNG, 16 colours, about 10 KB each) only at the start, the end and wherever the two differed, both sides and the
difference side by side. `report.txt` reads like a letter, `steps.csv` opens in a spreadsheet, `log.txt` is the log.

`python run_compare.py --replay "Custom Maps/compare zips/<zip>"` starts both again from the recording's save and dice, presses the same keys
and says whether every dice roll and every picture on both sides came out the same as recorded (THE SAME, or the first key that did not).
The original's dice state is set from the recording (written into DOSBox's memory), which is what makes the replay exact.

Things the original does not have (a hero's new items, spells past the 20th, a class the original lacks, Deluxe's extra potions and keys) cannot
be in its save. They are left out of what the original is given, and, unless you untick it, out of ours too so the two heroes match; the bottom
line of our window and the report say what was left out.

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
