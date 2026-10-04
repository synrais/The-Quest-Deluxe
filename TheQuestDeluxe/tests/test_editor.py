"""The Quest Deluxe Editor's window, driven by simulated mouse clicks on a copy of packs/TheQuest.

Needs tkinter and a display (on Linux without one: xvfb-run python tests/test_editor.py).
Paints walls by dragging, undoes and redoes, sets the start, fills a rectangle with gold,
checks a script and the dialogue, saves, and checks what reached the files.
"""
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    import tkinter as tk
    root = tk.Tk()
except Exception as e:                          # noqa: BLE001
    print(f'skipped: no tkinter or no display ({e})')
    sys.exit(0)

tmp = tempfile.mkdtemp()
os.environ['HOME'] = tmp                        # the editor remembers the last pack here
pack = os.path.join(tmp, 'edpack')
shutil.copytree(os.path.join(ROOT, 'packs', 'TheQuest'), pack)

from editor.app import App  # noqa: E402

app = App(root, pack)


def pump(n=15):
    for _ in range(n):
        root.update()
        time.sleep(0.01)


def click(x, y, drag_to=None):
    c = app.map_tab.canvas
    s = app.map_tab.size
    c.event_generate('<ButtonPress-1>', x=(x - 1) * s + 5, y=(y - 1) * s + 5)
    if drag_to:
        c.event_generate('<B1-Motion>', x=(drag_to[0] - 1) * s + 5, y=(drag_to[1] - 1) * s + 5)
        c.event_generate('<Motion>', x=(drag_to[0] - 1) * s + 5, y=(drag_to[1] - 1) * s + 5)
    end = drag_to or (x, y)
    c.event_generate('<ButtonRelease-1>', x=(end[0] - 1) * s + 5, y=(end[1] - 1) * s + 5)
    pump(3)


pump(30)
m, g = app.map_tab, app.project.grid(1)
m.layer.set('wall')
m.value['wall'] = 5                                   # boulders
click(3, 3, drag_to=(6, 3))                           # a fast drag still paints every square
assert [g.get(x, 3)[1] for x in range(3, 7)] == [5, 5, 5, 5], [g.get(x, 3)[1] for x in range(3, 7)]
m.undo()
assert g.get(4, 3)[1] == 3 and g.get(3, 3)[1] == 0     # back to the pine tree and grass
m.redo()
assert g.get(4, 3)[1] == 5
print('paint, undo, redo: ok')

m.tool.set('start')
click(7, 8)
assert app.project.constant(1, 'START') == (7, 8)
m.tool.set('rect')
m.layer.set('gold')
m.value['gold'] = 1
m.gold.set(25)
click(2, 6, drag_to=(3, 7))
assert all(g.get(x, y)[4] == 25 for x in (2, 3) for y in (6, 7))
print('start and gold rectangle: ok')

app.tabs.select(app.events_tab)
pump()
app.events_tab.show(1)
assert app.events_tab.check()
app.tabs.select(app.text_tab)
pump()
assert app.text_tab.check()
print('script and dialogue checks: ok')

# the Items tab: a new weapon, renamed, made a launcher, with a picture
import pygame  # noqa: E402
from tkinter import messagebox, simpledialog  # noqa: E402
from editor.art import to_ega  # noqa: E402

it = app.items_tab
app.tabs.select(it)
pump()
it.new()
row = it.row
assert row['id'] == 1001 and row['type'] == 'weapon'
name = next(f for f in it.fields() if f.key == 'name')
w, var = it.widgets['name']
var.set('Thunder Hammer')
it._typed(name, var, w)
assert row['bag_name'] == 'Thunder Hammer'                # follows the name while they match
it._set(next(f for f in it.fields() if f.key == 'type'), 'launcher')
assert row['kind'] == 4 and 'fires' in it.widgets or row.get('fires') == []
pic = pygame.Surface((40, 40), pygame.SRCALPHA)
pygame.draw.circle(pic, (200, 30, 30), (20, 20), 12)
it.set_picture('items', to_ega(pic))
assert app.project.picture('bag', 1001) is not None        # a bag picture was made from it
simpledialog.askstring = lambda *a, **k: 'Darts'
messagebox.showinfo = lambda *a, **k: None
it.new_ammo_kind()
darts = [r for r in it.rows if r.get('ammo') == 'darts']
assert len(darts) == 20 and [r['count'] for r in darts] == list(range(1, 21))
asked = []
messagebox.askyesno = lambda title, msg, **k: asked.append(msg) or True
it.select(201)
it.delete()
assert 'level 1 map' in asked[0] and not any(r['id'] == 201 for r in it.rows)
print('items: new weapon, rename, launcher, picture, ammo kind, delete with its uses listed: ok')

# the Creatures tab: a trait that defaults to on, loot rules, a new person's number
ct = app.creatures_tab
app.tabs.select(ct)
pump()
ct.select(32)
row = ct.row
bleeds = next(f for f in ct.fields() if f.key == 'bleeds')
ct._set(bleeds, True)
assert 'bleeds' not in row                               # the default (it bleeds) is left out of the file
ct._set(bleeds, False)
assert row['bleeds'] is False
loot = next(f for f in ct.fields() if f.key == 'loot')
w, var = ct.widgets['loot']
var.set('10-60: gold 5+2; 60-70: item 620')
ct._typed(loot, var, w)
assert row['loot'] == [[10, 60, 'gold', 5, 2], [60, 70, 'item', 620]]
simpledialog.askinteger = lambda *a, **k: 2              # a person
ct.new()
assert -99 <= ct.row['id'] <= -1 and ct.row['id'] != -5 and ct.row['att'] == -2
print('creatures: traits, loot, a new person: ok')

# pickers (a creature chosen from a list), the new traits, and links between levels
ct.select(32)
shows = next(f for f in ct.fields() if f.key == 'reveals_as')
assert shows.kind == 'choice' and any(v == 3 for v, _ in shows.choices)
ct._set(shows, 3)
assert ct.row['reveals_as'] == 3
ct._set(shows, None)
assert 'reveals_as' not in ct.row
size = next(f for f in ct.fields() if f.key == 'size')
ct._set(size, 2)
assert ct.row['size'] == 2
ct._set(size, None)
assert 'size' not in ct.row
print('creatures: pickers for what it turns into, and its size: ok')

# painting: Alt picks only with Alt held (Num Lock sets bit 0x8 on Windows), and a picture can start from another
from editor.painter import Painter
class Click:
    x, y, state = 5 * 12 + 2, 5 * 12 + 2, 0x0008          # a click with Num Lock on
cl = app.classes_tab
app.tabs.select(cl)
pump()
cl.select(1)
pd = cl.paint('heroes', False, 'Painted hero')
pump()
assert pd.templates and any('Mage' in name for name, _ in pd.templates)
assert any(c != -1 for col in pd.cells for c in col), 'it opens on the drawn hero'
pd.left = 9
pd._press(Click, 'left')
assert pd.left == 9 and pd.cells[5][5] == 9, 'a plain click paints, whatever the Num Lock'
pd._release(Click, 'left')
pd._press(Click, 'left', alt=True)
assert pd.left == 9 and pd.cells[5][5] == 9                  # Alt picked the colour that is there
pd.template.set(next(name for name, _ in pd.templates if 'Mage' in name))
pd.use_template()
assert pd.undo_stack and any(c != -1 for col in pd.cells for c in col)
pd.save()
assert app.project.picture('heroes', 1) is not None
pd.dirty = False
pd.destroy()
# the painter's tools: eraser, oval, mirror, swap, turn, zoom, background
pd = cl.paint('heroes', False, 'Painted hero')
pump()


class At:
    def __init__(self, x, y):
        self.x, self.y, self.state = x * pd.zoom + 2, y * pd.zoom + 2, 0


pd.clear()
pd.left, pd.right = 4, 1
pd.tool.set('pencil')
pd.mirror.set(True)
pd._press(At(3, 5), 'left')
pd._release(At(3, 5), 'left')
assert pd.cells[3][5] == 4 and pd.cells[36][5] == 4, 'Mirror paints both sides'
pd.mirror.set(False)
pd.tool.set('eraser')
pd._press(At(3, 5), 'right')
pd._release(At(3, 5), 'right')
assert pd.cells[3][5] == -1 and pd.cells[36][5] == 4, 'the eraser deletes with the right button'
pd._press(At(3, 5), 'left')
pd._release(At(3, 5), 'left')
assert pd.cells[3][5] == pd.original[3][5], 'and undoes with the left'
pd.cells[3][5] = 7
pd.tool.set('pencil')
pd._press(At(3, 5), 'right')
pd._release(At(3, 5), 'right')
assert pd.cells[3][5] == pd.original[3][5], 'the pencil undoes a pixel with the right button'
pd.tool.set('eraser')
pd._press(At(3, 5), 'right')
pd._release(At(3, 5), 'right')
pd.tool.set('oval')
pd.filled.set(False)
pd._press(At(10, 10), 'left')
pd._drag(At(20, 16), 'left')
pd._release(At(20, 16), 'left')
assert pd.cells[15][10] == 4 and pd.cells[15][13] == -1 and pd.cells[10][13] == 4, 'an outline of an oval'
pd.filled.set(True)
pd.tool.set('oval')
pd._press(At(25, 25), 'left')
pd._drag(At(30, 30), 'left')
pd._release(At(30, 30), 'left')
assert pd.cells[27][27] == 4
pd.tool.set('swap')
pd.left = 9
pd._press(At(27, 27), 'left')
pd._release(At(27, 27), 'left')
assert pd.cells[27][27] == 9 and pd.cells[15][10] == 9 and pd.cells[36][5] == 9, 'Swap changes every pixel of that colour'
pd.tool.set('dither')
pd.left, pd.right = 2, 3
pd._press(At(0, 0), 'left')
pd._drag(At(3, 0), 'left')
pd._release(At(3, 0), 'left')
assert [pd.cells[x][0] for x in range(4)] == [2, 3, 2, 3]
before = [c[:] for c in pd.cells]
pd.turn(True)
pd.turn(False)
assert pd.cells == before, 'a turn and a turn back'
# the palette: every kind of picture; dropping one stamps it, double-clicking starts from it; select, copy, paste
assert pd.palette is not None
assert pd.palette.kind.get() == 'Heroes', 'a hero opens on the heroes'
for kind in ('Items on the map', 'Items in the bag', 'Creatures', 'Heroes', 'Floors', 'Walls and doors',
             'Decorations', 'Spell icons'):
    pd.palette.kind.set(kind)
    pd.palette.fill()
    assert pd.palette._shown, f'{kind}: nothing on the shelf'
pd.palette.kind.set('Creatures')
pd.palette.fill()
orc = pd.palette._shown[0][1]
pd.clear()
pd.drop(orc, pd.canvas.winfo_rootx() + 20 * pd.zoom + 2, pd.canvas.winfo_rooty() + 20 * pd.zoom + 2)
assert any(c != -1 for col in pd.cells for c in col), 'a dropped picture is stamped'
pd.undo()
assert all(c == -1 for col in pd.cells for c in col), 'and Undo takes it back'
pd.drop(orc, pd.canvas.winfo_rootx() - 50, pd.canvas.winfo_rooty() - 50)
assert all(c == -1 for col in pd.cells for c in col), 'let go outside it: nothing'
pd.palette.on_start(orc)
assert any(c != -1 for col in pd.cells for c in col)
stamped = [c[:] for c in pd.cells]
pd.tool.set('select')
pd._press(At(5, 5), 'left')
pd._drag(At(12, 12), 'left')
pd._release(At(12, 12), 'left')
assert pd._box() == (5, 5, 12, 12)
pd.copy()
pd.clear()
pd.selection = None
pd.last_cell = (20, 20)
pd.paste()
assert pd.cells[20][20] == stamped[5][5] and pd.cells[27][27] == stamped[12][12]
pd.selection = (0, 0, 3, 3)
pd.cut()
other = cl.paint('heroes', False, 'Painted hero')
pump()
other.clear()
other.last_cell = (1, 1)
other.paste()                                           # what was cut in the first window pastes in another
other.dirty = False
other.destroy()
import editor.painter as painter_mod
assert len(pd.small) == 10 == len(pd.big), 'ten floors, small above and big below'
before = painter_mod.FLOOR_PICKS[:]
floors = sorted(pd._floors())
pd._pick_floor(2, floors[-1])
assert painter_mod.FLOOR_PICKS[2] == floors[-1] and pd.small[2].cget('image'), 'a slot changes to the floor chosen'
painter_mod.FLOOR_PICKS[:] = before
pd.set_zoom(16)
assert pd.canvas.winfo_reqwidth() == 640
pd.background.set('Grass')
pd.redraw()
assert pd.canvas.itemcget(pd.rects[0][1], 'fill') in ('#00a800',) or pd.cells[0][1] != -1
pd.ghost.set(True)
pd.redraw()
pd.grid_mode.set('Every pixel')
pd.redraw()
pd.dirty = False
pd.destroy()
print('painter: eraser, oval, mirror, swap, dither, turn, zoom and the background: ok')
# the four default heroes: Marksmanship is not offered to any but the Rogue (it comes free with that class)
cl.select(1)
assert cl.row['no_skill'] in ('mar', ['mar']) or 'mar' in cl.row['no_skill'], cl.row.get('no_skill')   # Knight
cl.select(2)
assert 'mar' in (cl.row['no_skill'] if isinstance(cl.row['no_skill'], list) else [cl.row['no_skill']])  # Mage
cl.select(3)
rogue = cl.row.get('no_skill') or []
assert 'mar' not in (rogue if isinstance(rogue, list) else [rogue])                                   # Rogue has it free
cl.select(4)
assert 'mar' in (cl.row['no_skill'] if isinstance(cl.row['no_skill'], list) else [cl.row['no_skill']])  # Monk
print('classes: Marksmanship shows as not offered to all but the Rogue: ok')
print('painting: a click paints, Alt picks, a picture starts from another, a hero can be painted: ok')

# the Classes tab: a new class with a starting kit
cl = app.classes_tab
app.tabs.select(cl)
pump()
cl.new()
bag = next(f for f in cl.fields() if f.key == 'bag')
w, var = cl.widgets['bag']
var.set('weapon: 1001; backpack: 230 620')
cl._typed(bag, var, w)
cl._set(next(f for f in cl.fields() if f.key == 'look.colour'), 14)
assert cl.row['bag'] == {'12,4': 1001, '12,8': 230, '13,8': 620} and cl.row['look']['colour'] == 14
print('classes: a new class, its kit and colour: ok')

# Dialogue, Stories, Shops
dt = app.dialogue_tab
app.tabs.select(dt)
pump()
dt.f_level.set('1 ')
dt.fill()
dt.list.selection_set(dt.list.get_children()[0])
pump()
assert dt.entry.key == (1, -6, 10)
dt.lines[0].set('My daughter was taken two days ago. If you see her, please')
dt._typed()
assert 'taken two days ago' in app.project.texts['talk']
dt.new()
assert dt.entry.key == (1, -6, 18)
from engine.events import talk_text  # noqa: E402
assert talk_text(app.project.texts['talk'], 1, -6, 18)[0] == ' "Hello there."'   # as the game reads one-liners
st = app.stories_tab
app.tabs.select(st)
pump()
st.new()
st.text.delete('1.0', 'end')
st.text.insert('1.0', 'A new tale begins.\nThe hero wakes.')
st._typed()
from engine.formats import parse_story  # noqa: E402
assert parse_story(app.project.texts['stories'])[st.story.number] == 'A new tale begins.\nThe hero wakes.'
sh = app.shops_tab
app.tabs.select(sh)
pump()
sh.levels.set('4')
sh._pick_level()
n = len(sh.stock)
sh.items.selection_set('211')
sh._put_on()
assert sh.stock[-1] == 211 and len(sh.stock) == n + 1
print('dialogue, stories and shops: edited, and the game reads them: ok')

# Tiles, and the painter
tt = app.tiles_tab
app.tabs.select(tt)
pump()
tt.pick_kind('walls')
tt.select(-2)
assert tt.row['door'] == 'locked' and tt.row['key'] == 'yellow'
tt._set(next(f for f in tt.fields() if f.key == 'door'), 'plain')
assert 'key' not in tt.row
tt.pick_kind('floors')
from unittest import mock  # noqa: E402
with mock.patch('tkinter.messagebox.askyesno', return_value=False):
    tt.new()
new_floor = tt.row['id']
pt = tt.paint('floors', False, 'Picture')
assert pt.palette.kind.get() == 'Floors', 'a floor opens on the floors'
pump()
assert pt.opaque                                      # floors have no see-through pixels
pt.tool.set('rect')
z = 12
pt._press(mock.Mock(x=2, y=2, state=0), 'left')
pt._release(mock.Mock(x=39 * z + 2, y=19 * z + 2, state=0), 'left')
pt.left = 1
pt.tool.set('fill')
pt._press(mock.Mock(x=2, y=30 * z, state=0), 'left')
pt._release(mock.Mock(x=2, y=30 * z, state=0), 'left')
pt.undo()
pt.redo()
pt.save()
pt.destroy()
img = app.project.picture('floors', new_floor)
assert tuple(img.get_at((0, 0)))[:3] == (252, 252, 252) and tuple(img.get_at((5, 30)))[:3] == (0, 0, 168)
print('tiles: a door, a new floor painted: ok')

# FPS mode: the 3D fields, the level's 3D settings and the 3D preview
tt.pick_kind('floors')
tt.select(1)
tt._set(next(f for f in tt.fields() if f.key == 'roof'), 10)
assert app.project.tiles['floors'][0]['roof'] == 10
tt._set(next(f for f in tt.fields() if f.key == 'roof'), None)
assert 'roof' not in app.project.tiles['floors'][0]
app.tabs.select(app.map_tab)
pump()
mt = app.map_tab
mt.look3d['SKY_3D'].insert(0, '1')
mt._apply_settings()
assert app.project.constant(1, 'SKY_3D') == 1
mt.selected = (5, 5)
mt.open_3d()
pump()
pv = mt.preview3d
assert pv.scene.sky == 1
pv.turn(1)
pv.walk(0)
assert (pv.x, pv.y, pv.facing) == (6, 5, 1), (pv.x, pv.y, pv.facing)
mt._press(mock.Mock(x=(9 - 1) * mt.size + 5, y=(9 - 1) * mt.size + 5))     # a click on the map moves the view
mt._release(mock.Mock(x=(9 - 1) * mt.size + 5, y=(9 - 1) * mt.size + 5))
assert (pv.x, pv.y) == mt.selected
pv.destroy()
mt.look3d['SKY_3D'].delete(0, 'end')
mt._apply_settings()
assert app.project.constant(1, 'SKY_3D') is None
print('FPS mode: roofs, 3D level settings, the 3D preview: ok')

# more key colours: set on the Quest tab, then offered to key items and locked doors
qt = app.quest_tab
qt.load()
qt.keys.set('Green: 10, purple: 5')
qt.apply()
assert app.project.quest['keys'] == {'green': 10, 'purple': 5}, app.project.quest.get('keys')
qt.load()
assert qt.keys.get() == 'green: 10, purple: 5'
key_field = next(f for f in app.items_tab.fields() if f.key == 'key')
assert [k for k, _ in key_field.choices] == ['yellow', 'red', 'blue', 'green', 'purple'], key_field.choices
app.tiles_tab.pick_kind('walls')
door_field = next(f for f in app.tiles_tab.fields() if f.key == 'key')
assert [k for k, _ in door_field.choices] == ['yellow', 'red', 'blue', 'green', 'purple'], door_field.choices
qt.keys.set('')
qt.apply()
assert 'keys' not in app.project.quest
print('more key colours: the Quest tab, and the choices for keys and locked doors: ok')

# class changes: the Quest tab's three rules
qt.load()
assert qt.reclass.get() == qt.RECLASS[True]
qt.reclass.set(qt.RECLASS['stats'])
qt.apply()
assert app.project.quest['reclass'] == 'stats'
qt.load()
assert qt.reclass.get() == qt.RECLASS['stats']
qt.reclass.set(qt.RECLASS[True])
qt.apply()
assert app.project.quest['reclass'] is True
assert any(f.key == 'reclass' for f in app.classes_tab.fields())
print('class changes: the Quest tab rules and the class setting: ok')

# the original's bugs: none fixed in Quest I; ticked on the Quest tab, saved as a list
qt.load()
assert not any(v.get() for v in qt.fixes.values())
qt.fixes['talk'].set(True)
qt.fixes['load_gaps'].set(True)
qt.apply()
assert app.project.quest['fixes'] == ['load_gaps', 'talk'], app.project.quest['fixes']
app.project.quest['fixes'] = True
qt.load()
assert all(v.get() for v in qt.fixes.values())
qt.apply()
assert app.project.quest['fixes'] is True
for v in qt.fixes.values():
    v.set(False)
qt.apply()
assert 'fixes' not in app.project.quest
print("the original's bugs: fixes ticked and saved: ok")

# a class's hidden skills and faults: one stays a plain name (as Quest I has it), more make a list
ct = app.classes_tab
ct._show(next(r for r in ct.rows if r['id'] == 1))                   # the Knight: no_fault "cow"
f = next(f for f in ct.fields() if f.key == 'no_fault')
ct._toggle(f, 'ras', True)
assert ct.row['no_fault'] == ['cow', 'ras'], ct.row['no_fault']
ct._toggle(f, 'ras', False)
assert ct.row['no_fault'] == 'cow'
f = next(f for f in ct.fields() if f.key == 'no_skill')
ct._toggle(f, 'bar', True)
assert ct.row['no_skill'] == ['bar', 'mar'], ct.row['no_skill']        # Marksmanship is never offered to a Knight
ct._toggle(f, 'bar', False)
assert ct.row['no_skill'] == 'mar'
print("classes: skills and faults hidden from a class: ok")

assert app.dirty
from editor import side_save
kept = []
real_save_zip = side_save.save_zip
side_save.save_zip = lambda *a, **k: kept.append(1) or (None, '')
app.save()
side_save.save_zip = real_save_zip
assert kept, 'Save keeps a zip of the additions'
print('save: also keeps the zip of the additions off to the side: ok')
assert os.path.exists(os.path.join(pack, 'sprites', 'items', '1001.png'))
assert os.path.exists(os.path.join(pack, 'sprites', 'bag', '1001.png'))
assert not os.path.exists(os.path.join(pack, 'sprites', 'items', '201.png'))
assert os.path.exists(os.path.join(pack, 'sprites', 'floors', f'{new_floor}.png'))
assert not app.dirty
with open(os.path.join(pack, 'levels', '1', 'map.txt')) as fh:
    lines = set(fh.read().splitlines())
assert '3 3 1 5 0 0 0 0' in lines and '2 6 1 0 0 0 25 0' in lines
with open(os.path.join(pack, 'levels', '1', 'script.qs')) as fh:
    assert 'START = (7, 8)                      # where newmap() puts the hero' in fh.read()
print('saved: map and script as expected')

import editor.map_tab as mt
mtab = app.map_tab
app.tabs.select(mtab)
pump()
mtab.level = 1
mtab.grid.sq[6][6][2] = 5                                 # an item that is no ladder: refused
shown = []
mt.messagebox.showinfo = lambda *a, **k: shown.append(a)
mtab._link_tool(6, 6)
assert shown, 'a square without a ladder asks for one first'
app.project.tables['items'].append({'id': 990, 'name': 'Stairs', 'type': 'stairs'})
mtab.grid.sq[6][6][2] = 990
class FakeLink:
    result = (2, 10, 12, 'Down you go.', True)
mt.LinkDialog = lambda *a, **k: FakeLink()
mtab._link_tool(6, 6)
assert app.project.constant(1, 'LINKS') == {(6, 6): (2, 10, 12, 'Down you go.')}
assert app.project.constant(2, 'LINKS') == {(10, 12): (1, 6, 6)}
assert app.project.grid(2).get(10, 12)[2] == 990        # the same stairs at the other end
class Gone:
    result = 'remove'
mt.LinkDialog = lambda *a, **k: Gone()
mtab._link_tool(6, 6)
assert app.project.constant(1, 'LINKS') is None
print('links: the Link tool makes both ends and removes one: ok')

# the wheel, zoom and grid on the map
from editor.uikit import _route
class Wheel:
    x_root = y_root = 0
    state = 0
before = (mtab.ox, mtab.oy)
mtab._wheel(3, False, False)
assert mtab.oy == before[1] + 6 and mtab.ox == before[0]
mtab._wheel(1, False, True)
assert mtab.ox == before[0] + 2
size = mtab.size
mtab._wheel(-1, True, False)                                  # Ctrl + wheel up: zoom in
assert mtab.size > size
mtab._wheel(1, True, False)
assert mtab.size == size
mtab.square_lines.set(False)
mtab.redraw()
mtab.square_lines.set(True)
mtab.redraw()
app.tabs.select(app.items_tab)
pump()
form = app.items_tab.pics.master                                # the form's side of the tab scrolls with the wheel
assert getattr(form, '_wheel_handler', None) is not None
form._wheel_handler(2, False, False)                            # (the handler runs without error)
assert getattr(app.quest_tab, '_wheel_handler', None) is not None
# the wheel over a drop-down's own list: Tk's popdown is unknown to tkinter and must not raise
class Over:
    x_root = y_root = 5
    state = 0
    delta = -120
orig = root.winfo_containing
def boom(x, y):
    raise KeyError('popdown')
root.winfo_containing = boom
assert _route(root, Over, 1) is None
root.winfo_containing = orig
print('the wheel: the map scrolls, zooms and has a square grid; the forms scroll: ok')

# the event wizard writes a rule into the script and the words into the Dialogue
from editor.event_wizard import EventWizard
app.tabs.select(app.events_tab)
pump()
et = app.events_tab
et.docs.selection_clear(0, 'end')
et.show(8) if 8 in et._keys else None
level = 1
wiz = EventWizard(et, level)
wiz.when.current(0)
wiz._when_changed()
wiz.subject.current([v for v, _ in wiz.people].index(-6)) if -6 in [v for v, _ in wiz.people] else None
wiz._add_condition()
wiz.conds[0]['kind'].current(0)
wiz.conds[0]['var'].set('0')
wiz.action.set_pairs(__import__('editor.event_wizard', fromlist=['ACTIONS']).ACTIONS)
wiz.action.current(0)
wiz._action_changed()
wiz.param['text'].insert(0, 'Wolves took my sheep.')
wiz._add_action()
wiz.action.current(2)
wiz._action_changed()
wiz.param['item'].current(0)
wiz._add_action()
code = wiz.preview.get('1.0', 'end')
assert 'def talk(npc):' in code and 'say(' in code and 'give(' in code and 'm1 == 0' in code, code
wiz._finish()
script = app.project.scripts[1]
assert 'npc == -6 and m1 == 0' in script and 'give(' in script
assert 'Wolves took my sheep.' in app.project.texts['talk']
from engine.script import Script
Script(script, 'level 1')                                     # the game reads what the wizard wrote
from editor.tips import field_tip
missing = []
for tab in (app.items_tab, app.creatures_tab, app.spells_tab, app.classes_tab, app.tiles_tab):
    app.tabs.select(tab)
    pump()
    for kind in (getattr(tab, 'KINDS', None) and ['floors', 'walls', 'decos'] or [None]):
        if kind:
            tab.kind = kind
        tab.load()
        for f in tab.fields():
            if f.kind != 'readonly' and not field_tip(f):
                missing.append((type(tab).__name__, f.key))
assert not missing, f'fields without a tooltip: {missing}'
assert getattr(app.map_tab.canvas, '_tip', None) is not None
app.tabs.select(app.creatures_tab)
pump()
assert getattr(app.creatures_tab.form.winfo_children()[0], '_tip', None) is not None
print('tooltips: every field and the map explain themselves: ok')
# an item that walks on water, with no tile marked as water yet: the editor says so and offers to mark the water
import editor.items_tab as itab
it = app.items_tab
app.tabs.select(it)
pump()
walls = app.project.tiles['walls']
for w_ in walls:
    w_.pop('water', None)
    w_.pop('freezes_to', None)
it.select(501)                                  # an amulet
asked = []
itab.messagebox.askyesno = lambda *a, **k: asked.append(a) or True
walk = next(f for f in it.fields() if f.key == 'water_walk')
it._set(walk, True)
assert asked and next(w_ for w_ in walls if w_['id'] == 2).get('water') is True, (asked, it.row, [(w_['id'], w_.get('name'), w_.get('water')) for w_ in walls][:5])
print('items: ticking Walks on water offers to mark the water tile: ok')
# the Wishes window: a wish is kept with the pack, and the zip tool carries it on
from editor.wishes import WishesWindow
app.wishes()
win = app._wishes
win.line.set('A spell that makes it rain, so the grass grows.')
win.add()
win.text.insert('end', 'I also wish creatures could carry keys.\n')
win.close()
wished = open(os.path.join(pack, 'WISHES.txt'), encoding='utf-8').read()
assert 'A spell that makes it rain' in wished and 'carry keys' in wished and wished.startswith('# Things I wish')
from editor import pack_edits as pz
assert 'A spell that makes it rain' in pz.read_wishes(pack) and '#' not in pz.read_wishes(pack)
print('wishes: written in the editor, kept with the pack, read by the zip tool: ok')
print('events: the wizard makes a rule, its words and the script, and the game reads it: ok')
root.destroy()
print('all editor checks passed')
