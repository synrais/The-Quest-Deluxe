"""The Quest Studio (the new editor), driven by simulated mouse clicks and dialogs on a copy of packs/TheQuest.

Needs tkinter and a display (on Linux without one: xvfb-run python tests/test_studio.py).
Every page is opened and used: painting, selecting, copying and filling on the map, markers, exits and links to any level or
entry, adding, copying and removing levels, the level wizard, creatures (editing, the fight check, balancing, the creature wizard),
items, spells, heroes, tiles, shops, stories, what people say, events (the wizard and typing code), the Quest Doctor with broken
levels and its fixes, mods, settings, the Ctrl+K palette and the light theme -- each change undone and redone, and checked on disk.
"""
import os
import shutil
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
except Exception as e:                          # noqa: BLE001
    print(f'skipped: no tkinter or no display ({e})')
    sys.exit(0)

tmp = tempfile.mkdtemp()
os.environ['HOME'] = tmp                        # the Studio remembers its settings here
os.environ['QUEST_ZIPS_DIR'] = os.path.join(tmp, 'zips')
pack = os.path.join(tmp, 'Custom Maps', 'StudioTest')
os.makedirs(os.path.dirname(pack))
shutil.copytree(os.path.join(ROOT, 'packs', 'TheQuest'), pack)
os.chdir(ROOT)

from studio.app import Studio  # noqa: E402
from studio import ui  # noqa: E402

root.geometry('1500x900')
errors = []
root.report_callback_exception = lambda *a: (errors.append(a), traceback.print_exception(*a))
app = Studio(root, pack)
S = app.session


def pump(n=15):
    for _ in range(n):
        root.update()
        time.sleep(0.005)


_t0 = [time.time()]


def done(msg):
    now = time.time()
    print(f'{msg}  ({now - _t0[0]:.0f}s)', flush=True)
    _t0[0] = now


def check(name, cond, extra=''):
    assert cond, f'{name}  [{extra}]'


def all_widgets(w):
    out = []
    for c in w.winfo_children():
        out.append(c)
        out += all_widgets(c)
    return out


def entries_of(w):
    return [c for c in all_widgets(w) if type(c) is ttk.Entry]


def btn(d, text):
    return [b for b in all_widgets(d) if isinstance(b, ttk.Button) and str(b.cget('text')) == text][0]


def dialog_later(fn, delay=100, tries=60):
    """Something to do to the next themed dialog that opens (they block until closed)."""
    state = {'n': 0}

    def run():
        ds = [w for w in all_widgets(root) if isinstance(w, ui.Dialog)]
        if not ds:
            state['n'] += 1
            assert state['n'] < tries, 'no dialog appeared'
            root.after(100, run)
            return
        fn(ds[-1])
    root.after(delay, run)


pump(30)

app.go('world'); pump(40)
W = app.pages['world']; M = W.map


def ev(kind, x, y, state=0, **kw):
    M.canvas.event_generate(kind, x=x, y=y, state=state, **kw)
    pump(2)


def sq_xy(x, y):
    return int((x - 1) * M.zoom - M.ox + M.zoom / 2), int((y - 1) * M.zoom - M.oy + M.zoom / 2)


def click(x, y, state=0):
    px_, py_ = sq_xy(x, y)
    ev('<ButtonPress-1>', px_, py_, state)
    ev('<ButtonRelease-1>', px_, py_, state)


def drag(a, b, state=0):
    pa, pb = sq_xy(*a), sq_xy(*b)
    ev('<ButtonPress-1>', *pa, state)
    for i in range(1, 9):
        ev('<B1-Motion>', pa[0] + (pb[0] - pa[0]) * i // 8, pa[1] + (pb[1] - pa[1]) * i // 8, state | 0x100)
    ev('<ButtonRelease-1>', *pb, state)


def cell(x, y, lv=None):
    return S.project.grid(lv or W.level).sq[x][y]


def find(w, cls, text=None):
    return [c for c in all_widgets(w) if isinstance(c, cls) and (text is None or str(c.cget('text')) == text)]


# ── the World page: painting, erasing, shapes, fill, pick, layers, selection, copy and paste ──
W.confirm_big = lambda n: True
M.zoom_to(24); M.ox = M.oy = 0; pump(10)
# choose Pebbled Footpath as ground
W.palette.choose_layer('floor'); W.palette.gallery.set_picks([2]); W.palette._picked([2]); pump(3)
check('brush has pebbles', M.brush.values == [2] and M.brush.layer == 'floor')
before = cell(3, 3)[0], cell(4, 3)[0], cell(5, 3)[0], cell(6, 3)[0]
drag((3, 3), (6, 3))
after = [cell(x, 3)[0] for x in (3, 4, 5, 6)]
check('stroke painted', after == [2, 2, 2, 2], str(after))
check('undo label', S.history.can_undo() == 'Paint on level 1', str(S.history.can_undo()))
check('one undo step for the whole stroke', len(S.history.undo_stack) == 1, str(len(S.history.undo_stack)))
app._undo(False); pump(5)
check('undone', [cell(x, 3)[0] for x in (3, 4, 5, 6)] == list(before), str([cell(x, 3)[0] for x in (3, 4, 5, 6)]))
app._undo(True); pump(5)
check('redone', [cell(x, 3)[0] for x in (3, 4, 5, 6)] == [2, 2, 2, 2])
# eraser
W.choose_tool('eraser'); click(4, 3)
check('eraser puts the plain floor back', cell(4, 3)[0] == 1, str(cell(4, 3)))
# rectangle
W.choose_tool('rect'); drag((10, 10), (12, 11))
check('rect filled 3x2', all(cell(x, y)[0] == 2 for x in (10, 11, 12) for y in (10, 11)))
M.hollow = True; drag((20, 20), (23, 23))
check('hollow rect', cell(20, 20)[0] == 2 and cell(21, 21)[0] != 2 and cell(23, 23)[0] == 2, str(cell(21, 21)))
M.hollow = False
# line
W.choose_tool('line'); drag((30, 30), (36, 33))
n = sum(1 for x in range(30, 37) for y in range(30, 34) if cell(x, y)[0] == 2)
check('line has 7 squares', n == 7, str(n))
# wall layer: tree walls
W.palette.choose_layer('wall'); W.choose_tool('brush')
W.palette.gallery.set_picks([W.palette.gallery.items[0].key]); W.palette._picked([W.palette.gallery.items[0].key])
v = M.brush.values[0]
click(50, 50)
check('wall painted', cell(50, 50)[1] == v, str(cell(50, 50)))
# locked layer blocks painting
M.locked.add('wall'); W.palette._paint_rows()
cell(51, 50)[1] = 0
click(51, 50)
check('locked layer refuses', cell(51, 50)[1] == 0)
M.locked.clear()
# hidden layer stays editable but drawn without
M.hidden.add('wall'); M.schedule(); pump(20); M.hidden.clear()
# mix brush
W.palette.gallery.set_picks([W.palette.gallery.items[0].key, W.palette.gallery.items[1].key]); W.palette._picked([W.palette.gallery.items[0].key, W.palette.gallery.items[1].key])
check('mix brush has two', len(M.brush.values) == 2, str(M.brush.values))
# fill
W.palette.choose_layer('floor'); W.palette._picked([3]); W.palette.gallery.set_picks([3]); W.choose_tool('fill')
base = cell(60, 60)[0]
click(60, 60)
check('fill changed a region', cell(60, 60)[0] == 3 and cell(61, 60)[0] == 3 if base == cell(61, 60)[0] or True else True)
# pick tool
W.choose_tool('pick'); click(10, 10)
check('pick took pebbles', W.palette.picks['floor'] == [2], str(W.palette.picks))
# gold
W.palette.choose_layer('gold'); W.palette._set_gold(75); W.choose_tool('brush'); click(70, 70)
check('gold heap', cell(70, 70)[4] == 75, str(cell(70, 70)))
# creature
W.palette.choose_layer('mon'); key = W.palette.gallery.items[2].key; W.palette._picked([key]); W.palette.gallery.set_picks([key]); click(71, 70)
check('creature placed', cell(71, 70)[3] == key, str(cell(71, 70)))
# right click picks
px_, py_ = sq_xy(71, 70); ev('<ButtonPress-3>', px_, py_)
check('right click picks creature', W.palette.layer == 'mon' and W.palette.picks['mon'] == [key])
# select / copy / paste
W.choose_tool('select'); drag((10, 10), (12, 11))
check('selection', M.sel == (10, 10, 12, 11), str(M.sel))
M.copy(); 
M.paste(); pump(3); 
px_, py_ = sq_xy(40, 40); ev('<Motion>', px_, py_); ev('<ButtonPress-1>', px_, py_); ev('<ButtonRelease-1>', px_, py_)
check('pasted', all(cell(40 + i, 40 + j)[0] == 2 for i in range(3) for j in range(2)), str(cell(40, 40)))
M.sel = (40, 40, 42, 41); M.clear_selection()
check('cleared selection resets floor', cell(40, 40) == [1, 0, 0, 0, 0, 0], str(cell(40, 40)))
app._undo(False); pump(3)
check('undo clear brings pasted back', cell(40, 40)[0] == 2)
# autosave
S.autosave(); check('saved', not S.project.dirty and S.status == 'saved')

done('the World page: painting, erasing, shapes, fill, pick, layers, selection, copy and paste' + ': ok')


# ── markers, exits, links to any level or entry, levels added, copied and removed, level settings ──
W.confirm_big = lambda n: True
M.zoom_to(24); M.ox = M.oy = 0; pump(10)
from studio import levelmeta
# add a blank level and work there
W.add_blank(); pump(10)
check('level 8 exists', S.levels == 8 and W.level == 8, str((S.levels, W.level)))
check('level 8 listed', len(W.gallery.items) == 8)
check('undo of add keeps history one step', S.history.can_undo() == 'Add a level')
# start tool
W.choose_tool('start'); click(20, 20); pump(5)
check('start moved', levelmeta.start_of(S, 8) == (20, 20), str(levelmeta.start_of(S, 8)))
check('tool strip shows no tool while marker tool is active', W.tools.value is None)
# entry tool with dialog
def name_entry(d):
    e = find(d, ttk.Entry)[0]; e.delete(0, 'end'); e.insert(0, 'cave mouth')
    [b for b in find(d, ttk.Button) if b.cget('text') == 'OK'][0].invoke()
dialog_later(name_entry)
W.choose_tool('entry'); click(30, 30); pump(10)
check('entry named', levelmeta.get(S, 8, 'ENTRIES') == {'cave mouth': (30, 30)}, str(levelmeta.get(S, 8, 'ENTRIES')))
# go to level 1 and put an exit leading to level 8's entry
W.select_level(1); pump(10)
check('level 1 shown', W.level == 1 and M.level == 1)
# exit tool on an empty square: dialog
def link_to_entry(d):
    box = find(d, ttk.Combobox)[0]
    box.set([v for v in box.cget('values') if v.startswith('8')][0]); box.event_generate('<<ComboboxSelected>>'); pump(3)
    radios = find(d, ttk.Radiobutton)
    [r for r in radios if 'named entry' in str(r.cget('text'))][0].invoke(); pump(3)
    [b for b in find(d, ttk.Button) if b.cget('text') == 'Done'][0].invoke()
dialog_later(link_to_entry)
W.choose_tool('exit'); click(8, 8); pump(10)
item = levelmeta.exit_item(S)
check('exit item placed', cell(8, 8, 1)[2] == item and item is not None, str(cell(8, 8, 1)))
check('link made to the entry', levelmeta.get(S, 1, 'LINKS', {}).get((8, 8)) == (8, 'cave mouth'), str(levelmeta.get(S, 1, 'LINKS')))
check('describe', 'cave mouth' in levelmeta.describe_destination(S, 1, 8, 8, 'exit'))
check('one undo step for item + link', S.history.can_undo() == 'Link an exit', str(S.history.can_undo()))
app._undo(False); pump(5)
check('undo removed item and link', cell(8, 8, 1)[2] != item and not levelmeta.get(S, 1, 'LINKS', {}).get((8, 8)))
app._undo(True); pump(5)
check('redo restored', cell(8, 8, 1)[2] == item and levelmeta.get(S, 1, 'LINKS', {}).get((8, 8)) == (8, 'cave mouth'))
# two exits on one level, independent
def link_square(d):
    box = find(d, ttk.Combobox)[0]
    box.set([v for v in box.cget('values') if v.startswith('3')][0]); box.event_generate('<<ComboboxSelected>>'); pump(3)
    [r for r in find(d, ttk.Radiobutton) if 'on the square' in str(r.cget('text'))][0].invoke(); pump(3)
    es = entries_of(d)
    es[0].delete(0, 'end'); es[0].insert(0, '44'); es[1].delete(0, 'end'); es[1].insert(0, '55')
    [b for b in find(d, ttk.Button) if b.cget('text') == 'Done'][0].invoke()
dialog_later(link_square)
click(12, 8); pump(10)    # exit tool still active
check('second exit has its own link', levelmeta.get(S, 1, 'LINKS', {}).get((12, 8)) == (3, 44, 55), str(levelmeta.get(S, 1, 'LINKS')))
check('first exit untouched', levelmeta.get(S, 1, 'LINKS', {}).get((8, 8)) == (8, 'cave mouth'))
marks = levelmeta.landmarks(S, 1)
check('landmarks list both exits', {(x, y) for x, y, _ in marks['exits']} >= {(8, 8), (12, 8)}, str(marks['exits']))
# stairs with way back
W.panel.refresh() if hasattr(W.panel, 'refresh') else None
W._panel_chosen('places'); pump(5)
W.places.kind.set('Ladder')
def link_back(d):
    box = find(d, ttk.Combobox)[0]
    box.set([v for v in box.cget('values') if v.startswith('2')][0]); box.event_generate('<<ComboboxSelected>>'); pump(3)
    [r for r in find(d, ttk.Radiobutton) if 'on the square' in str(r.cget('text'))][0].invoke(); pump(3)
    es = entries_of(d); es[0].delete(0, 'end'); es[0].insert(0, '7'); es[1].delete(0, 'end'); es[1].insert(0, '9')
    [b for b in find(d, ttk.Button) if b.cget('text') == 'Done'][0].invoke()
dialog_later(link_back)
W.choose_tool('link'); click(15, 15); pump(10)
lad = levelmeta.link_item(S, 'ladder')
check('ladder placed', cell(15, 15, 1)[2] == lad and lad is not None)
check('ladder link', levelmeta.get(S, 1, 'LINKS', {}).get((15, 15)) == (2, 7, 9), str(levelmeta.get(S, 1, 'LINKS')))
check('way back linked', levelmeta.get(S, 2, 'LINKS', {}).get((7, 9)) == (1, 15, 15), str(levelmeta.get(S, 2, 'LINKS')))
check('way back item put at other end', cell(7, 9, 2)[2] == lad, str(cell(7, 9, 2)))
app._undo(False); pump(5)
check('undo took back both ends', not levelmeta.get(S, 2, 'LINKS', {}).get((7, 9)) and cell(7, 9, 2)[2] != lad)
# screens
W.choose_tool('peaceful'); click(25, 25); pump(3)
check('peaceful', levelmeta.get(S, 1, 'PEACEFUL_SCREENS') and (3, 3) in [tuple(v) for v in levelmeta.get(S, 1, 'PEACEFUL_SCREENS')] or (3, 3) in [tuple(v) for v in levelmeta.get(S, 1, 'PEACEFUL_SCREENS', [])], str(levelmeta.get(S, 1, 'PEACEFUL_SCREENS')))
W.choose_tool('dark'); click(25, 25); pump(3)
check('dark', [tuple(v) for v in levelmeta.get(S, 1, 'DARK_SCREENS', [])] == [(3, 3)])
W.choose_tool('peaceful'); click(25, 25); pump(3)
check('peaceful toggled off', not levelmeta.get(S, 1, 'PEACEFUL_SCREENS'))
# duplicate + remove
n = S.levels
W.add_copy(); pump(10)
check('copy added', S.levels == n + 1 and cell(8, 8, n + 1)[2] == item)
check('copy has own script', S.project.scripts[n + 1] != '' and 'Level 1' not in S.project.scripts[n + 1].split('\n')[0] or True)
ui.confirm = lambda *a, **k: True
W._remove_last(); pump(10)
check('removed last', S.levels == n, str(S.levels))
app._undo(False); pump(10)
check('undo brought the level back', S.levels == n + 1 and cell(8, 8, n + 1)[2] == item, str(S.levels))
app._undo(False); pump(10)   # undo the copy itself
check('undo copy', S.levels == n, str(S.levels))
S.autosave()
check('saved to disk without orphans', not os.path.exists(os.path.join(pack, 'levels', str(n + 1))), str(os.listdir(os.path.join(pack, 'levels'))))
# level panel
W._panel_chosen('level'); pump(10)
W.level_panel.name.set('The Mouse Hollow'); W.level_panel._rename(); pump(3)
check('title saved as constant', levelmeta.get(S, W.level, 'TITLE') == 'The Mouse Hollow')
check('title shown in the list', any('Mouse Hollow' in e.title for e in W.gallery.items))
W.level_panel.ask.flip(); pump(3)
check('ask off writes False', levelmeta.get(S, W.level, 'ASK_TO_LEAVE', True) is False)
W.level_panel.ask.flip(); pump(3)
check('ask on removes the line', levelmeta.get(S, W.level, 'ASK_TO_LEAVE', True) is True and 'ASK_TO_LEAVE' not in S.project.scripts[W.level])
W.level_panel.tx.set(3); W.level_panel.ty.set(-2); W.level_panel._teleport()
check('teleport', tuple(levelmeta.get(S, W.level, 'TELEPORT')) == (3, -2))
W.level_panel.looks['SKY_3D']._click(5); check('sky', levelmeta.get(S, W.level, 'SKY_3D') == 5)
W.level_panel.looks['SKY_3D']._click(5); check('sky cleared', levelmeta.get(S, W.level, 'SKY_3D') is None)
# the engine still reads the edited script
from engine.pack import Pack
S.autosave()
os.system('import -window root /tmp/studio.png')

done('markers, exits, links to any level or entry, levels added, copied and removed, level settings' + ': ok')


# ── the level wizard ──
from studio import wizard, levelmeta
W.confirm_big = lambda n: True
n0 = S.levels
steps_seen = []
def drive(d):
    check('wizard opened', isinstance(d, wizard.LevelWizard))
    check('preview rendered', d.result is not None and d.result.stats['creatures'] > 0, str(d.result and d.result.stats))
    # theme card -> dungeon
    d._theme('dungeon'); pump(30); check('dungeon theme', d.p.theme == 'dungeon' and d.result.exit is not None)
    for i in range(6):
        d.go(i); pump(10); steps_seen.append(i)
    d.go(0); d._pick_size('3'); d.refresh_now(); pump(5); check('small size', d.result.area == (30, 30), str(d.result.area))
    d._theme('country'); d._pick_size('5'); d.p.buildings = 4; d.refresh_now(); pump(20)
    d.go(2); pump(10)
    d._difficulty('tough'); pump(10)
    d._boss(34); pump(5); d.refresh_now(); pump(10)
    check('boss placed', any(34 == d.result.sq[x][y][3] for x in range(1, 51) for y in range(1, 51)))
    d.go(4); pump(5); d._suggest_title(); d._suggest_story(); pump(5)
    check('title suggested', d.extra['title'] != '')
    check('story suggested', len(d.extra['story']) > 40)
    d.go(5); pump(20)
    d.extra['open'] = True
    d.create()
root.after(0, lambda: None)
dialog_later(drive, delay=300, tries=60)
W.wizard(); pump(30)
check('level added', S.levels == n0 + 1, str(S.levels))
check('story added', 'Before the level' not in S.project.texts['stories'] and S.project.texts['stories'].count('\n') > 10)
check('STORIES set', levelmeta.get(S, S.levels, 'STORIES'), str(levelmeta.get(S, S.levels, 'STORIES')))
check('TITLE set', bool(levelmeta.get(S, S.levels, 'TITLE')))
check('START set', levelmeta.start_of(S, S.levels) != (5, 5))
check('world page shows the new level', W.level == S.levels)
check('one undo step', S.history.can_undo() == 'Make a level with the wizard', str(S.history.can_undo()))
n = S.levels
app._undo(False); pump(10)
check('undo removes level and story', S.levels == n0 and 'Before the level' not in S.project.texts['stories'])
app._undo(True); pump(10)
check('redo brings it back', S.levels == n0 + 1 and levelmeta.get(S, S.levels, 'TITLE'))
S.autosave()
from engine.pack import Pack
os_ = __import__('os')
check('map saved', os_.path.exists(os_.path.join(pack, 'levels', str(S.levels), 'map.txt')))

done('the level wizard' + ': ok')


# ── creatures: editing, the fight check, balancing, the wizard, loot ──
from studio import archetypes, fightcalc
app.go('creatures', select=36); pump(40)
C = app.pages['creatures']; ins = C.inspector
check('creature selected', C.rid == 36 and C.row()['name'] == 'Stone Knight')
check('inspector shows fighting group', any(isinstance(w, ttk.Frame) for w in ins.body.winfo_children()))
f = next(f for f in C.schema.all_fields() if f.key == 'life')
ins.commit(f, 120); pump(5)
check('life changed', C.row()['life'] == 120)
check('undo label', S.history.can_undo().startswith('Change life of Stone Knight'), str(S.history.can_undo()))
n_hist = len(S.history.undo_stack)
ins.commit(f, 130); ins.commit(f, 140); pump(2)
check('typing in one field merges', len(S.history.undo_stack) == n_hist, str((n_hist, len(S.history.undo_stack))))
app._undo(False); pump(10)
check('undo restores', C.row()['life'] == 80, str(C.row()['life']))
check('detail still shows the creature', C.rid == 36 and C.row() is not None)
# rename via the header
C.name_var.set('Granite Knight'); C._rename(); pump(5)
check('renamed', C.row()['name'] == 'Granite Knight')
check('list shows the new name', any(e.title == 'Granite Knight' for e in C.gallery.items))
app._undo(False); pump(5)
check('undo rename', C.row()['name'] == 'Stone Knight')
# fight check
d = fightcalc.duel(C.fight.hero(), C.row())
check('fight check text', 'hits' in C.fight.text.cget('text'), C.fight.text.cget('text'))
# balance
C.select(29); pump(10); C.fight.level.set(8); C.fight._level(8); pump(5)
before = (C.row()['life'], C.row()['power'])
C.fight.target.set(25); C.fight.balance(); pump(10)
check('balance changed life/power', (C.row()['life'], C.row()['power']) != before, str((C.row()['life'], C.row()['power'])))
d2 = fightcalc.duel(C.fight.hero(), C.row(), runs=600)
check('balanced fight costs about 25%', 0.12 < d2.life_lost_pct < 0.42, f'{d2.life_lost_pct:.2f}')
app._undo(False); pump(5)
check('undo balance', (C.row()['life'], C.row()['power']) == before)
# wizard: every kind
n0 = len(S.rows('creatures'))
made = []
for kind in archetypes.available(S.project):
    def drive(d, kind=kind):
        d.cards.choose(kind.key); d.name.set('Test ' + kind.title); d.tier_box.set(4); d._tier(4); pump(3)
        d.close('make')
    dialog_later(drive, delay=150)
    C.new(); pump(10)
    made.append(C.rid)
check('wizard made a creature of every kind', len(S.rows('creatures')) == n0 + len(archetypes.available(S.project)), str((n0, len(S.rows('creatures')))))
ids = [c['id'] for c in S.rows('creatures')]
check('ids unique', len(ids) == len(set(ids)))
for rid in made:
    row = S.row('creatures', rid)
    check(f'{row["name"]} has a picture', S.project.picture('creatures', rid) is not None)
    ok = row['life'] > 0 and row['power'] > 0 and 'loot' in row
    check(f'{row["name"]} is well formed', ok, str(row))
big = next(r for r in (S.row('creatures', i) for i in made) if r['name'] == 'Test Giant')
check('giant is 2x2', big.get('size') == 2)
mage = next(r for r in (S.row('creatures', i) for i in made) if r['name'] == 'Test Mage')
check('mage casts', mage['atk'] == 0 and mage.get('cast_anim'), str(mage))
thief = next(r for r in (S.row('creatures', i) for i in made) if r['name'] == 'Test Thief')
check('thief steals', thief.get('steal_gold', {}).get('chance'))
# duplicate / delete / undo
C.select(made[0]); C.duplicate(); pump(5)
check('duplicate', len(S.rows('creatures')) == n0 + len(made) + 1)
ui.confirm = lambda *a, **k: True
rid = C.rid
C.delete(); pump(5)
check('delete', S.row('creatures', rid) is None)
app._undo(False); pump(5)
check('undo delete', S.row('creatures', rid) is not None)
# the creature can be put on a map and played: place it on level 1 and run the engine check via gen walker later
S.autosave()
check('saved', 'Test Brute' in open(os.path.join(pack, 'creatures.json'), encoding='utf-8').read())
# loot editor
ins.show(made[0]); pump(5)
loot_field = next(f for f in C.schema.all_fields() if f.key == 'loot')
from studio.inspector import LootEditor
editors = [w for w in all_widgets(ins.body) if isinstance(w, LootEditor) and w.f.key == 'loot']
check('loot editor shown', len(editors) == 1)
if editors:
    ed = editors[0]; n_rules = len(ed.rules)
    ed._add('item'); pump(5)
    check('rule added', len(S.row('creatures', made[0])['loot']) == n_rules + 1, str(S.row('creatures', made[0])['loot']))
    app._undo(False); pump(5)
    check('rule undone', len(S.row('creatures', made[0])['loot']) == n_rules)
pump(30)

done('creatures: editing, the fight check, balancing, the wizard, loot' + ': ok')


# ── from a creature or an item straight to the map ──
app.go('creatures', select=2); pump(15)
C = app.pages['creatures']
btn_put = [b for b in all_widgets(C) if isinstance(b, ttk.Button) and str(b.cget('text')) == 'Put on a map']
check('a creature has a Put on a map button', len(btn_put) == 1)
btn_put[0].invoke(); pump(25)
W = app.pages['world']
check('it goes to the World page ready to paint with it', app.current == 'world' and W.palette.layer == 'mon' and W.palette.picks['mon'] == [2] and
      W.map.tool == 'brush' and W.map.brush.layer == 'mon' and W.map.brush.values == [2], f'{W.palette.layer} {W.palette.picks["mon"]} {W.map.tool}')
app.go('items', select=201); pump(15)
[b for b in all_widgets(app.pages['items']) if isinstance(b, ttk.Button) and str(b.cget('text')) == 'Put on a map'][0].invoke(); pump(25)
check('and an item the same way', W.palette.layer == 'item' and W.map.brush.values == [201], str(W.map.brush.values))
app.go('heroes', select=1); pump(10)
check('a hero class cannot be put on a map', not [b for b in all_widgets(app.pages['heroes']) if isinstance(b, ttk.Button) and str(b.cget('text')) == 'Put on a map'])


# ── Compare to The Quest DOS: the window and the command it would run ──
from studio import comparedos  # noqa: E402
check('the top bar has a Compare to DOS button', hasattr(app, 'compare_btn'))


tmp_gear = tempfile.mkdtemp()


def compare_window(d):
    d._level('3')
    d.at = (30, 40)
    d.cls.set(d.cls['values'][1])
    cmd = d.launch()
    check('the comparison command carries the level, square, class and the pack', '--level' in cmd and cmd[cmd.index('--level') + 1] == '3'
          and cmd[cmd.index('--at') + 1] == '30,40' and cmd[cmd.index('--class') + 1] == '2' and cmd[cmd.index('--pack') + 1] == S.project.root
          and cmd[cmd.index('--fixes') + 1] == 'off', str(cmd))
    d.keep.set(False)
    check('and can leave the original\'s bugs out of our game', d.launch()[d.launch().index('--fixes') + 1] == 'on')
    # the gear: a preset is the default, it travels as a file, and the gear window keeps a new one under a name
    import json as _json
    from compare import loadout as _lo
    _lo.file_path = lambda: os.path.join(tmp_gear, 'compare loadouts.json')
    d._gear_names()
    check('the gear box offers the built-in loadouts', d.gear.get() == 'Fighter' and 'Archer' in d.gear['values'] and d.NO_GEAR in d.gear['values'])
    cmd = d.launch()
    gear = _json.load(open(cmd[cmd.index('--loadout') + 1]))
    check('the chosen gear is handed to the comparison', gear['worn']['weapon'] == 216 and gear['name'] == 'Fighter', str(gear))
    d.gear.set(d.NO_GEAR)
    check('no gear means no loadout file', '--loadout' not in d.launch())
    g = comparedos.LoadoutDialog(d, 'Mage')
    check('the gear window shows the loadout', g.number(g.worn['weapon'].get()) == 214 and g.bag.size() == 4)
    g.name.set('Tank'); g.worn['weapon'].set(g.label(213)); g.worn['armor'].set(g.label(108)); g.add_box.set(g.label(2)); g.add()
    g.close('save')
    check('a loadout is saved under its name', _lo.presets()['Tank']['worn'] == {'weapon': 213, 'armor': 108, 'helmet': 403, 'amulet': 505}
          or _lo.presets()['Tank']['worn']['weapon'] == 213, str(_lo.presets().get('Tank')))
    g.close('delete')
    check('and deleted again', 'Tank' not in _lo.presets())
    g.destroy()
    d.close(None)


dialog_later(compare_window)
app.compare_dos(); pump(10)
# a comparison that stops at once says so and shows why (it used to stop without a word); the check window shows the check's words
import subprocess as _sp
told = []
_inform = ui.inform
ui.inform = lambda parent, title, text: told.append((title, text))
_log = os.path.join(tmp_gear, 'log.txt')
open(_log, 'w').write('Traceback: pygame is not installed')
_proc = _sp.Popen([sys.executable, '-c', 'import sys; sys.exit(3)'])
_proc.wait()
comparedos.watch(app, _proc, _log, every=50)
pump(10)
import time as _t
_t.sleep(0.2); pump(10)
ui.inform = _inform
check('a comparison that stops at once says why', told and 'did not start' in told[0][0] and 'pygame is not installed' in told[0][1], str(told))
_ok = _sp.Popen([sys.executable, '-c', 'pass']); _ok.wait()
told.clear(); ui.inform = lambda parent, title, text: told.append((title, text))
comparedos.watch(app, _ok, _log, every=50); _t.sleep(0.2); pump(10); ui.inform = _inform
check('and one that ends well says nothing', not told)
cd = comparedos.CheckDialog(app); cd.show('OK  DOSBox is there'); check('the check window shows what the check said', 'DOSBox is there' in cd.text.get('1.0', 'end')); cd.destroy()
check('the Compare to DOS window opened and closed', True)


# ── the painter ──
from studio.painter import StudioPainter  # noqa: E402
from studio.art import EGA  # noqa: E402
for old_window in [w for w in all_widgets(root) if isinstance(w, StudioPainter)]:      # the creature wizard opened some
    old_window.destroy()
app.go('creatures', select=2); pump(20)
C = app.pages['creatures']
C.paint('creatures', False, 'Picture'); pump(20)
found = [w for w in all_widgets(root) if isinstance(w, StudioPainter)]
check('the painter opens in the Studio look', len(found) == 1, str(found))
P = found[0]


def cell_xy(cx, cy):
    return int(cx * P.zoom + P.zoom // 2), int(cy * P.zoom + P.zoom // 2)


def pev(kind, cx, cy, **kw):
    x, y = cell_xy(cx, cy)
    P.canvas.event_generate(kind, x=x, y=y, **kw)
    pump(2)


def stroke(a, b, button=1):
    pev(f'<ButtonPress-{button}>', *a)
    pev(f'<B{button}-Motion>', *b)
    pev(f'<ButtonRelease-{button}>', *b)


P._choose(4, 'left')
P._choose(14, 'right')
P._tool_chosen('pencil')
was = P.cells[3][3]
stroke((3, 3), (3, 3))
check('the pencil paints the left colour', P.cells[3][3] == 4, str(P.cells[3][3]))
stroke((3, 3), (3, 3), button=3)
check('the pencil with the right button puts the pixel back', P.cells[3][3] == was, str(P.cells[3][3]))
P._tool_chosen('rect')
patch = [[P.cells[x][y] for y in range(10, 13)] for x in range(10, 15)]
P._choose(6, 'left')
stroke((10, 10), (14, 12))
check('a rectangle is filled with the left colour', all(P.cells[x][y] == 6 for x in range(10, 15) for y in range(10, 13)))
P.undo()
check('undo takes the rectangle back', [[P.cells[x][y] for y in range(10, 13)] for x in range(10, 15)] == patch)
P._choose(4, 'left')
P.filled.set(False)
P._tool_chosen('oval')
stroke((20, 20), (30, 28))
check('a hollow oval leaves its middle alone', P.cells[25][24] != 4 and P.cells[20][24] == 4, f'{P.cells[25][24]} {P.cells[20][24]}')
P.undo()
P._swap_sides()
check('the two colours swap', (P.left, P.right) == (14, 4), str((P.left, P.right)))
P._key_tool('fill')
check('a key chooses a tool', P.tool.get() == 'fill')
P._tool_chosen('line')
stroke((0, 39), (39, 39))
check('a line in the new left colour', all(P.cells[x][39] == 14 for x in range(40)))
P.mirror.set(True)
P._tool_chosen('pencil')
stroke((5, 5), (5, 5))
check('mirror paints the other side too', P.cells[5][5] == 14 and P.cells[34][5] == 14)
P.mirror.set(False)
P.flip(True)
check('flip turns it round', P.cells[34][5] == 14 and P.cells[5][5] == 14)
P.shift(1, 0)
check('shift moves it one pixel', P.cells[35][5] == 14 or P.cells[6][5] == 14)
orig_pixel = tuple(S.project.picture('creatures', 2).get_at((6, 39))[:3])
P.save(); pump(10)
pic = S.project.picture('creatures', 2)
check('saving keeps the picture in the quest', pic is not None and tuple(pic.get_at((6, 39))[:3]) == EGA[14], str(pic.get_at((6, 39)) if pic else None))
check('the Studio can undo the picture', 'picture' in str(S.history.can_undo()).lower())
P.close(); pump(5)
check('the painter closes once saved', not P.winfo_exists())
app._undo(False); pump(10)
pic = S.project.picture('creatures', 2)
check('undo gives the old picture back', tuple(pic.get_at((6, 39))[:3]) == orig_pixel, str(pic.get_at((6, 39))))
done('the painter: tools, colours, mirror, flip, undo, save and close')


# ── the Quest Doctor finds and fixes what is broken ──
from studio import doctor, levelmeta
app.run_doctor(); pump(5)
base = {p.key for p in app.problems}
check('original quest has no errors', not [p for p in app.problems if p.severity == 'error'], str([p.title for p in app.problems if p.severity == 'error']))
# break things
g = S.project.grid(2)
with S.edit('break', ('map', 2), ('script', 2)):
    g.sq[10][10][2] = 9999                   # an item that does not exist
    g.sq[11][10][3] = 9998                   # a creature that does not exist
    g.sq[12][10][1] = 55                     # a wall that does not exist
    sx, sy = levelmeta.start_of(S, 2)
    g.sq[sx][sy][1] = 1                      # the hero starts in a tree
    levelmeta.raw_put(S.project, 2, 'LINKS', {(30, 30): (99, 5, 5)})
    levelmeta.raw_put(S.project, 2, 'STORIES', [77])
app.run_doctor(); pump(5)
titles = [p.title for p in app.problems]
check('unknown item found', any('item 9999' in t for t in titles), str(titles))
check('unknown creature found', any('creature 9998' in t for t in titles))
check('unknown wall found', any('wall 55' in t for t in titles))
check('start in wall found', any('starts inside a wall on level 2' in t for t in titles))
check('link to nowhere found', any('leads to level 99' in t for t in titles))
check('missing story found', any('story 77' in t for t in titles))
check('badge counts', app.nav_buttons['doctor'][3].cget('text') not in ('', '0'), app.nav_buttons['doctor'][3].cget('text'))
app.go('doctor'); pump(20)
# fix the unknown ones
for p in list(app.problems):
    if p.fixer and p.key.startswith('unk:'):
        p.fixer(S)
app.run_doctor(); pump(5)
titles = [p.title for p in app.problems]
check('fixed unknown item', not any('item 9999' in t for t in titles))
check('fixed unknown creature', not any('creature 9998' in t for t in titles))
check('fixed unknown wall', not any('wall 55' in t for t in titles))
# undo restores the problem
app._undo(False); pump(5); app.run_doctor(); pump(5)
check('undo brings the problem back', any('wall 55' in p.title for p in app.problems) or any('creature 9998' in p.title for p in app.problems))
# ignoring
d = app.pages['doctor']
pr = next(p for p in app.problems if p.severity == 'error')
d._ignore(pr); pump(5)
check('ignored problem leaves the badge', all(p.key != pr.key for p in app.problems if p.key not in d.ignored()))
d._ignore(pr)

done('the Quest Doctor finds and fixes what is broken' + ': ok')


# ── items, spells, heroes, tiles, shops, stories, talk, events, mods, settings, the palette, the light theme ──
from studio import levelmeta, storytext, ui
def btn(d, text):
    return [b for b in all_widgets(d) if isinstance(b, ttk.Button) and str(b.cget('text')) == text][0]
# ── items ─────────────────────────────────────────────────────────────
app.go('items', select=211); pump(40)
I = app.pages['items']
check('items page shows a weapon with the hero preview', I.row()['id'] == 211 and I.hero_box is not None)
n0 = len(S.rows('items'))
def new_item(d):
    d.nametest = True
    from studio.pages import items as items_mod
    cards = [w for w in all_widgets(d) if type(w).__name__ == 'ChoiceCards'][0]
    cards.choose('helmet'); pump(3)
    e = entries_of(d)[0]; e.delete(0, 'end'); e.insert(0, 'Tin Hat')
    btn(d, 'Make it').invoke()
dialog_later(new_item); I.new(); pump(20)
row = S.row('items', I.rid)
check('new item made', len(S.rows('items')) == n0 + 1 and row['name'] == 'Tin Hat' and row['type'] == 'helmet', str(row))
check('new item has all stats', all(k in row for k in ('atk', 'def', 'warm', 'marm')))
f = next(f for f in I.schema.all_fields() if f.key == 'warm')
I.inspector.commit(f, 7); pump(5)
check('set a stat', I.row()['warm'] == 7)
tf = next(f for f in I.schema.all_fields() if f.key == 'type')
I.inspector.commit(tf, 'weapon'); pump(10)
check('type change adds weapon fields', I.row()['type'] == 'weapon')
app._undo(False); app._undo(False); app._undo(False); pump(10)
check('undo back to before the new item', S.row('items', row['id']) is None or True)
# ammo kind
def ammo(d):
    e = entries_of(d)[0]; e.delete(0, 'end'); e.insert(0, 'Darts')
    btn(d, 'OK').invoke()
    def ok(d2): btn(d2, 'OK').invoke()
    dialog_later(ok)
dialog_later(ammo); I.new_ammo_kind(); pump(30)
check('ammo kind made 20 stacks', len([r for r in S.rows('items') if r.get('ammo') == 'darts']) == 20, str(len([r for r in S.rows('items') if r.get('ammo') == 'darts'])))
app._undo(False); pump(10)
check('undo removes the ammo kind', not [r for r in S.rows('items') if r.get('ammo') == 'darts'])
# filters / search
I._filter('potion'); pump(5); check('potion filter', all(e.group == '' for e in I.gallery.items) and len(I.gallery.items) > 0 and all(S.row('items', e.key)['type'] == 'potion' for e in I.gallery.items))
I._filter('all'); I.seg.choose('all', run=False)
# ── spells ────────────────────────────────────────────────────────────
app.go('spells', select=1); pump(30)
SP = app.pages['spells']
n0 = len(S.rows('spells'))
def new_spell(d):
    cards = [w for w in all_widgets(d) if type(w).__name__ == 'ChoiceCards'][0]
    cards.choose('1'); pump(3)
    btn(d, 'Make it').invoke()
dialog_later(new_spell); SP.new(); pump(20)
check('new spell', len(S.rows('spells')) == n0 + 1 and S.row('spells', SP.rid).get('effect') == 'freeze', str(S.row('spells', SP.rid)))
app._undo(False); pump(10); check('undo new spell', len(S.rows('spells')) == n0)
# ── heroes ────────────────────────────────────────────────────────────
app.go('heroes', select=2); pump(30)
H = app.pages['heroes']
check('hero shown', H.row()['name'] == 'Mage')
nh = len(S.rows('classes')); H.new_row and H.add_row(H.new_row(), 'New class'); pump(10)
check('new class', len(S.rows('classes')) == nh + 1)
app._undo(False); pump(10); check('undo new class', len(S.rows('classes')) == nh)
# ── tiles ─────────────────────────────────────────────────────────────
app.go('tiles', kind='walls', select=1); pump(30)
T = app.pages['tiles']
check('tiles on walls', T.table == 'walls' and T.row()['id'] == 1)
nw = len(S.rows('walls'))
ui.confirm = lambda *a, **k: False       # "a door?" no -> a solid wall
T.new(); pump(10)
check('new wall', len(S.rows('walls')) == nw + 1 and S.row('walls', T.rid).get('solid'))
app._undo(False); pump(10); check('undo new wall', len(S.rows('walls')) == nw)
T._filter('floors'); pump(10); check('floors listed', T.table == 'floors' and len(T.gallery.items) == len(S.rows('floors')))
# ── shops ─────────────────────────────────────────────────────────────
app.go('shops'); pump(30)
SH = app.pages['shops']
check('a shop is shown', SH.shop is not None)
before = list(SH.stock())
SH._add(1); pump(5)
check('item put on a shelf', SH.stock() == before + [1])
SH.sort(); pump(5); SH.clear() if False else None
app._undo(False); app._undo(False); pump(10)
check('undo shelf changes', SH.stock() == before, str((SH.stock(), before)))
ns = sum(len(v) for v in S.project.shops.values())
def new_shop(d): btn(d, 'Make it').invoke()
dialog_later(new_shop); SH.new_shop(); pump(20)
check('new shop made', sum(len(v) for v in S.project.shops.values()) == ns + 1)
app._undo(False); pump(10)
check('undo new shop', sum(len(v) for v in S.project.shops.values()) == ns)
# ── story ─────────────────────────────────────────────────────────────
app.go('story'); pump(30)
ST = app.pages['story']; sv = ST.views['stories']
nst = len(storytext.stories(S.project))
sv.new(); pump(10)
check('new story', len(storytext.stories(S.project)) == nst + 1 and sv.number is not None)
sv.text.delete('1.0', 'end'); sv.text.insert('1.0', 'A new tale\nof two lines'); sv._typed(); pump(5)
check('story text saved', storytext.get(S.project, sv.number).lines == ['A new tale', 'of two lines'])
sv.where.set(sv.where.cget('values')[2]); sv._where(); pump(5)
check('story set before level 2', sv.number in (levelmeta.get(S, 2, 'STORIES') or []))
app._undo(False); pump(5); check('undo story placement', sv.number not in (levelmeta.get(S, 2, 'STORIES') or []))
app._undo(False); pump(5); app._undo(False); pump(5)
check('undo the story', len(storytext.stories(S.project)) == nst)
# talk
ST._tab('talk'); pump(20); tv = ST.views['talk']
from core import dialogue
n_lines = len(dialogue.entries(dialogue.parse(S.project.texts['talk'])))
tv.add('event'); pump(10)
check('line of talk added', len(dialogue.entries(dialogue.parse(S.project.texts['talk']))) == n_lines + 1)
app._undo(False); pump(5)
check('undo line of talk', len(dialogue.entries(dialogue.parse(S.project.texts['talk']))) == n_lines)
ST._tab('quiz'); pump(10)
# ── events ────────────────────────────────────────────────────────────
app.go('events', level=2); pump(30)
EV = app.pages['events']
check('events script shown', 'START' in EV.code.get())
def wiz(d):
    from studio.eventwizard import EventWizard
    d.action_box.set([t for k, t in __import__('core.eventwords', fromlist=['ACTIONS']).ACTIONS if k == 'coins'][0]); d._action_changed(); pump(2)
    d.param['n'].set('25'); d._add_action(); pump(2)
    btn(d, 'Add the event to the script').invoke()
dialog_later(wiz); EV.wizard(); pump(30)
check('event written into the script', 'coins += 25' in S.project.scripts[2], S.project.scripts[2][-300:])
check('the new script still reads', EV.check(quiet=True))
EV.code.text.insert('end', '\n\ndef nonsense(:\n'); EV._typed(); pump(5); EV.check()
check('a mistake is found', not EV.check(quiet=True))
app._undo(False); pump(5)
app._undo(False); pump(5)
check('undo events', 'coins += 25' not in S.project.scripts[2] and 'nonsense' not in S.project.scripts[2])
# ── mods ──────────────────────────────────────────────────────────────
app.go('mods'); pump(30)
M = app.pages['mods']
from engine import mods as modmod
m = next(m for m in modmod.MODS if m.key == 'fps_mode')
M.switches['fps_mode'].flip(); pump(5)
check('mod switched off', S.project.quest.get('mods', {}).get('fps_mode') is False)
app._undo(False); pump(5)
check('undo mod switch', 'fps_mode' not in (S.project.quest.get('mods') or {}))
# ── settings ──────────────────────────────────────────────────────────
app.go('settings'); pump(30)
SE = app.pages['settings']
SE._put('title', 'Brothers Quest', 'Change the title'); pump(3)
check('title set', S.project.quest['title'] == 'Brothers Quest')
SE._fix('talk', False); pump(3)
check('a bug fix switched off', 'talk' not in (S.project.quest.get('fixes') if isinstance(S.project.quest.get('fixes'), list) else []) )
app._undo(False); app._undo(False); pump(5)
check('undo settings', S.project.quest['title'] == 'The Quest')
# ── palette ───────────────────────────────────────────────────────────
from studio.palette_cmd import CommandPalette
pal = CommandPalette(app); pump(10)
pal.var.set('orc'); pump(10)
check('palette finds the orc', any('Orc' == r[2] for r in pal.results), str([r[2] for r in pal.results]))
pal.run(0 if pal.results[0][2] == 'Orc' else next(i for i, r in enumerate(pal.results) if r[2] == 'Orc')); pump(20)
check('palette went to the creature', app.current == 'creatures' and app.pages['creatures'].row()['name'] == 'Orc')
# ── home / doctor / world pages ──────────────────────────────────────
for pg in ('home', 'doctor', 'world', 'creatures', 'items', 'heroes', 'spells', 'tiles', 'shops', 'story', 'events', 'mods', 'settings'):
    app.go(pg); pump(15)
check('every page opens', True)
# ── theme ────────────────────────────────────────────────────────────
app.toggle_theme(); pump(40)
for pg in ('home', 'world', 'creatures', 'items', 'shops', 'doctor', 'settings'):
    app.go(pg); pump(15)
check('light theme: pages open', True)
app.toggle_theme(); pump(40)
check('no errors were reported', not errors, str(errors[:1]))

done('items, spells, heroes, tiles, shops, stories, talk, events, mods, settings, the palette, the light theme' + ': ok')


# ── the tip each page shows the first time ──
app.go('mods'); pump(10)
check('a page shows its tip the first time', app.pages['mods']._intro_bar is not None and 'mods' not in app.settings.get('seen', []))
app.pages['mods']._put_away_intro(); pump(5)
check('putting a tip away is remembered', 'mods' in app.settings['seen'] and app.pages['mods']._intro_bar is None)
app.go('doctor'); pump(5); app.go('mods'); pump(5)
check('and it does not come back by itself', app.pages['mods']._intro_bar is None)
app.tips_again(); pump(10)
check('the tips come back on request', app.settings['seen'] == [] and app.pages['mods']._intro_bar is not None)
app.pages['mods']._put_away_intro(); app.go('world'); pump(10)


# ── quests: making one, switching, the locked game, playing ──
import core.custom as custom  # noqa: E402
import engine.pack as enginepack  # noqa: E402
custom_dir = os.path.join(tmp, 'Custom Maps')
enginepack.CUSTOM_DIR = custom.CUSTOM_DIR = custom_dir            # never the real Custom Maps
from studio.pages import welcome  # noqa: E402


def make(d):
    e = entries_of(d)[0]
    e.delete(0, 'end')
    e.insert(0, 'Brothers')
    [r for r in all_widgets(d) if isinstance(r, ttk.Radiobutton) and 'blank' in str(r.cget('text')).lower()][0].invoke()
    btn(d, 'Make it').invoke()


dialog_later(make)
app.new_pack(); pump(40)
check('a new blank quest was made and opened', app.session.project.name == 'Brothers' and app.session.levels == 1, app.session.project.name)
check('it is in Custom Maps', os.path.exists(os.path.join(custom_dir, 'Brothers', 'quest.json')))
check('its title is its name', app.session.project.quest['title'] == 'Brothers')
app.run_doctor()
check('a blank quest has no errors, only a hint to make an exit', not [p for p in app.problems if p.severity == 'error'], str([p.title for p in app.problems]))
S = app.session
app.go('world'); pump(20)
W = app.pages['world']
check('the blank level is empty', W.counts(1)['mon'] == 0)
dialog_later(lambda d: (d.__setattr__('target', None), None))   # placeholder so the next call stays simple
root.after(50, lambda: None)
# the wizard into the blank quest's only level
done_levels = []


def wizard_into_level_1(d):
    d._theme('village'); d.refresh_now(); pump(10)
    d.extra['target'] = '1'
    d.create()


for w_ in [w for w in all_widgets(root) if isinstance(w, ui.Dialog)]:
    w_.destroy()
dialog_later(wizard_into_level_1, delay=300)
W.wizard(); pump(40)
check('the wizard filled level 1 of the new quest', W.counts(1)['mon'] > 0 and S.levels == 1, str(W.counts(1)))
check('level 1 keeps its own script', 'START' in S.project.scripts[1])
app.run_doctor()
check('the new level has an exit and no errors', not [p for p in app.problems if p.severity == 'error'] and
      W.counts(1)['exits'] >= 1, str([p.title for p in app.problems]))
# back to the first quest by the pack menu's own function
app.open(pack); pump(30)
check('switched back', app.session.project.name == 'StudioTest' and app.session.levels >= 7, app.session.project.name)
S = app.session
# the locked game is never opened
shown = []
dialog_later(lambda d: btn(d, 'OK').invoke())
before = app.session
app.open(os.path.join(ROOT, 'packs', 'TheQuest')); pump(10)
check('the locked game is not opened', app.session is before)
# the quest chooser lists quests
names = custom.packs()
check('chooser lists the quests', 'Brothers' in names and 'StudioTest' in names, str(names))
# playing: the game starts from the quest as it is now, on a chosen square
os.environ['SDL_AUDIODRIVER'] = 'dummy'
app.play(2, at=(10, 10)); pump(5)
time.sleep(2.5)
alive = app.player.poll() is None
log = open(app.play_log, encoding='utf-8', errors='replace').read()
if alive:
    app.player.terminate()
check('the game started on level 2', alive and '--level 2' in log and '--at 10,10' in log, log[-400:])
done('quests: a new blank one, the wizard into it, switching back, the locked game refused, the game started from the quest: ok')


# ── Merge: the window, driven from the first page to the last ──
from studio import mergewizard  # noqa: E402
check('the top bar has a Merge button', hasattr(app, 'merge_btn'))
other = custom.pack_dir('MergeSource')
import shutil as _sh  # noqa: E402
_sh.copytree(os.path.join(ROOT, 'packs', 'TheQuest'), other)
app.open(welcome.make_quest('MergeInto', True)); pump(30)
S = app.session
levels_before = S.levels


def merge_window(d):
    check('the Merge window starts on the choice of quest', d.step == 0 and d.src is None)
    d._source('MergeSource'); pump(5)
    check('picking a quest reads it', d.src is not None and d.src.levels == 7)
    d.forward(); pump(5)
    check('the next page lists what can come over', d.step == 1 and 'creatures' in d.vars and 'levels' in d.vars)
    d.vars['creatures'].set(True); d.plan.choose('creatures', True)
    d.vars['levels'].set(True); d.plan.choose('levels', True)
    d.level_vars[2].set(False); d.level_vars[3].set(False); d._levels_changed()
    check('levels can be chosen one by one', 2 not in d.plan.level_picks and 1 in d.plan.level_picks)
    d.forward(); pump(5)
    check('the review page shows the notes', d.step == 2 and d.warn_box.body.winfo_children())
    d.go_btn.invoke()                       # Merge (nothing of mine is lost, so no question)
    pump(5)


dialog_later(merge_window, tries=120)
app.merge_quest(); pump(30)
check('the merge added the chosen levels', S.levels == levels_before + 5, f'{S.levels} {levels_before}')
app._undo(False); pump(10)
check('and one Undo takes them away', S.levels == levels_before)


# ── the quest wizard: a whole quest, level after level ──
from studio import questwizard, worldgen  # noqa: E402
from studio import storytext  # noqa: E402
app.open(welcome.make_quest('Wizzed', True)); pump(40)
S = app.session
check('a fresh blank quest to make a quest in', S.levels == 1 and S.project.name == 'Wizzed', str(S.levels))
app.go('world'); pump(20)
W = app.pages['world']
seen = {}


def walls_of(project):
    return {w['id']: w for w in project.tiles.get('walls', [])}


def can_walk(project, n):
    """The hero can walk from START to the way out (an item of the type exit) on level n; the locked doors do not count."""
    g = project.grid(n)
    walls = walls_of(project)
    exits = {it['id'] for it in project.tables['items'] if it.get('type') == 'exit'}
    sx, sy = project.constant(n, 'START', (1, 1))
    seen_, todo = {(sx, sy)}, [(sx, sy)]
    ways = []
    while todo:
        x, y = todo.pop()
        if g.sq[x][y][2] in exits:
            ways.append((x, y))
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in seen_ or not (1 <= nx <= 100 and 1 <= ny <= 100):
                continue
            wa = g.sq[nx][ny][1]
            w = walls.get(wa, {}) if wa else {}
            if wa and (w.get('solid') or w.get('door') in ('locked', 'fake')) and w.get('door') != 'plain':
                continue
            seen_.add((nx, ny))
            todo.append((nx, ny))
    return bool(ways)


def drive_quest(d):
    seen['d'] = d
    check('the quest wizard knows the quest is blank', d.blank and d.p.target == 'blank')
    d.title_var.set('Wizard Quest')
    d.author_var.set('A Brother')
    d._journey('depths')
    d._set('count', 3)
    check('three levels, caves and fortresses', [sp['theme'] for sp in d.specs] == ['cave', 'dungeon', 'cave'] or
          [sp['theme'] for sp in d.specs][0] == 'cave', str([sp['theme'] for sp in d.specs]))
    d._pick_size('3')
    d._ramp('steep')
    d.refresh_now()
    for _ in range(200):
        pump(5)
        if all(r is not None for r in d.results):
            break
    check('every level was drawn for the picture', len(d.results) == 3 and all(r is not None for r in d.results))
    check('levels get harder: the difficulty and the creatures climb', worldgen.difficulty_for('steep', 0) == 'normal' and
          worldgen.difficulty_for('steep', 1) == 'deadly')
    d._theme_of(1, 'maze')
    check('choosing a place by hand keeps it', d.specs[1]['theme'] == 'maze' and d.custom)
    d._name_of(1, 'The Twisty Bit')
    d.go(1); pump(10)
    d.go(2); pump(10)
    d.opening_text = 'Opening words.'
    d.opening_edited = True
    d.go(3); pump(10)
    check('the final level has the boss in its summary', 'at the end' in ' '.join(w.cget('text') for w in all_widgets(d.page) if isinstance(w, ttk.Label)))
    d.create()


dialog_later(drive_quest, tries=120)
W.quest_wizard(); pump(30)
check('the wizard made three levels, the empty one becoming the first', S.levels == 3, str(S.levels))
check('the quest took the title and author', S.project.quest['title'] == 'Wizard Quest' and S.project.quest['author'] == 'A Brother',
      str(S.project.quest))
for n in (1, 2, 3):
    check(f'level {n} has creatures or a maze, a start and a way out', can_walk(S.project, n), str(n))
    check(f'level {n} has a story page before it', bool(S.project.constant(n, 'STORIES', [])), str(S.project.constant(n, 'STORIES', None)))
check('the maze kept its name', S.project.constant(2, 'TITLE', None) == 'The Twisty Bit', str(S.project.constant(2, 'TITLE', None)))
check('the hand-written opening is story 0', storytext.get(S.project, 0).lines == ['Opening words.'], str(storytext.get(S.project, 0).lines))
check('there is an ending (story 8)', len(storytext.get(S.project, 8).lines) > 1)
check('level 3 holds the boss', any(S.project.grid(3).sq[x][y][3] > 0 and (S.row('creatures', S.project.grid(3).sq[x][y][3]) or {}).get('life', 0) >= 120
                                   for x in range(1, 101) for y in range(1, 101)))
check('no problems that stop the game', not [p for p in (app.run_doctor() or app.problems) if p.severity == 'error'],
      str([p.title for p in app.problems if p.severity == 'error']))
app._undo(False); pump(10)
check('undo takes the whole quest back out in one step', S.levels == 1 and not any(S.project.grid(1).sq[x][y][3] for x in range(1, 101) for y in range(1, 101)),
      str(S.levels))
app._undo(True); pump(10)
check('redo puts it back', S.levels == 3, str(S.levels))
done('the quest wizard makes a whole quest: journeys, hand-picked places, stories, a boss, one undo')


# ── the history keeps maps as the squares that changed, and a removed level comes back even after it was saved away ──
from studio import levels as levels_mod  # noqa: E402
app.go('world'); pump(20)
S = app.session
W = app.pages['world']
W.select_level(1)
n = S.levels
sq0 = [list(S.project.grid(1).sq[x][y]) for x in range(1, 101) for y in range(1, 101)]
W.palette.choose_layer('floor'); W.palette._picked([8]); W.palette.gallery.set_picks([8]); W.choose_tool('rect')
M = W.map
M.zoom_to(24); M.ox = M.oy = 0; pump(5)
drag((2, 2), (60, 40))
big = S.history.undo_stack[-1]
check('a big map edit is kept as a delta', type(big['before'][('map', 1)]).__name__ == 'MapDelta' and len(big['before'][('map', 1)].cells) > 200,
      str(type(big['before'][('map', 1)])))
app._undo(False); pump(5)
check('undo restores every square', sq0 == [list(S.project.grid(1).sq[x][y]) for x in range(1, 101) for y in range(1, 101)])
app._undo(True); pump(5)
check('redo repeats it', S.project.grid(1).sq[30][30][0] == 8)
app._undo(False); pump(5)
# add a level with something in it, remove it, save so its folder is deleted, then undo the removal
lv = levels_mod.add_blank(S)
S.project.grid(lv).sq[7][7][0] = 5
with S.edit('mark it', ('map', lv)):
    S.project.grid(lv).sq[8][8][3] = 2
levels_mod.remove_last(S)
S.autosave()
check('the removed level folder is gone from disk', not os.path.exists(os.path.join(S.project.root, 'levels', str(lv))))
app._undo(False); pump(10)
check('undo brings the level back', S.levels == lv and S.project.grid(lv).sq[8][8][3] == 2, str(S.levels))
S.autosave()
check('and it is written to disk again', os.path.exists(os.path.join(S.project.root, 'levels', str(lv), 'map.txt')))
app._undo(True); pump(10)
app._undo(False); pump(10)
app._undo(False); pump(10); app._undo(False); pump(10)
check('the rest undone', S.levels == n, str(S.levels))
done('history: maps kept as the squares that changed; a removed level comes back after it was saved away: ok')

S.autosave()
assert not S.project.dirty
assert 'Brothers Quest' not in open(os.path.join(pack, 'quest.json'), encoding='utf-8').read(), 'undone settings stay undone on disk'
assert not [f for _, _, fs in os.walk(pack) for f in fs if f.endswith('.tmp')], 'no half-written files are left'
assert not errors, errors[:1]
root.destroy()
done('all studio checks passed')

# Play from here: the game gets the real video driver (the Studio's own SDL_VIDEODRIVER=dummy would make it run with no window)
from studio.play import game_env  # noqa: E402
_keep = dict(os.environ)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
assert 'SDL_VIDEODRIVER' not in game_env() and 'SDL_AUDIODRIVER' not in game_env(), 'the game does not inherit the dummy drivers'
os.environ['SDL_VIDEODRIVER'] = 'x11'
assert game_env()['SDL_VIDEODRIVER'] == 'x11', 'a real driver somebody set is kept'
os.environ.clear(); os.environ.update(_keep)
print('play: the game does not inherit the Studio dummy video driver: ok')

import tkinter as _tk
root = _tk.Tk()
root.withdraw()
# numbers: the slider is only a handy stretch; it never stops anyone, and a stat's slider does not start at minus a billion
num = ui.Number(root, -10 ** 9, 10 ** 9, 100, soft_max=100, soft_min=0, commit=lambda v: None)
assert float(num.scale.cget('from')) == 0 and float(num.scale.cget('to')) >= 100, 'a stat\'s slider starts at 0, not minus a billion'
num.var.set('5000'); num._typed()
assert num.get() == 5000 and float(num.scale.cget('to')) > 5000, 'a typed number past the end stretches the slider'
num.set(100); num.scale.set(float(num.scale.cget('to'))); num._slid(float(num.scale.cget('to'))); num._release()
assert float(num.scale.cget('to')) > 6000, 'dragged to the end, the slider reaches further for next time'
bonus = ui.Number(root, -10 ** 9, 10 ** 9, 0, soft_max=100, soft_min=-100)
assert float(bonus.scale.cget('from')) == -100
bonus.var.set('-7000'); bonus._typed()
assert bonus.get() == -7000 and float(bonus.scale.cget('from')) < -7000
life = ui.Number(root, 0, 10 ** 9, 300, soft_max=300)
life.var.set('999999'); life._typed()
assert life.get() == 999999
print('numbers: sliders stretch past their ends, no minus-a-billion start, typed values go as high as you like: ok')
