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
from deluxe.events import talk_text  # noqa: E402
assert talk_text(app.project.texts['talk'], 1, -6, 18)[0] == ' "Hello there."'   # as the game reads one-liners
st = app.stories_tab
app.tabs.select(st)
pump()
st.new()
st.text.delete('1.0', 'end')
st.text.insert('1.0', 'A new tale begins.\nThe hero wakes.')
st._typed()
from deluxe.formats import parse_story  # noqa: E402
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

assert app.dirty
app.save()
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
root.destroy()
print('all editor checks passed')
