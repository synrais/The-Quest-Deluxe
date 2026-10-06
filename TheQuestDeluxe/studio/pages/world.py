"""The World page: every level as a card, the map with its tools, and the panels for painting, level settings and places."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from editor.project import SIZE

from .. import icons, levels, levelmeta, theme, ui
from ..gallery import Entry, Gallery
from ..mapview import MARKER_TOOLS, ZOOMS, MapView
from ..theme import C, px
from .base import Page
from .world_level import LevelPanel
from .world_paint import PalettePanel
from .world_places import PlacesPanel, edit_link

TOOLS = [('brush', 'brush', 'Brush (B): click or drag to paint'),
         ('eraser', 'eraser', 'Eraser (E): rub out the chosen layer. Hold Shift to rub out everything'),
         ('rect', 'rect', 'Rectangle (R)'),
         ('line', 'line', 'Line (L)'),
         ('fill', 'bucket', 'Fill (G): fill the area. Hold Ctrl to replace every square like it on the level'),
         ('pick', 'picker', 'Pick (I, or right-click): take what is under the pointer as the brush'),
         ('select', 'select', 'Select (S): drag a box, then copy, cut, move or clear it')]
PANELS = [('paint', 'Paint'), ('level', 'Level'), ('places', 'Places')]


class WorldPage(Page):
    key = 'world'
    title = 'World'
    icon = 'map'

    # ── build ───────────────────────────────────────────────────────────────
    def build(self):
        self.level = int(self.app.settings.get('world_level', 1))
        self.level = max(1, min(self.level, self.s.levels))
        self.page = self                                      # dialogs hang on this
        self._thumbs: dict = {}
        self._counts: dict = {}
        self._thumb_job = None
        self.last_sq = None
        self.hover_sq = None
        left = ttk.Frame(self, width=px(224))
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        ui.vsep(self).pack(side='left', fill='y')
        right = ttk.Frame(self, width=px(330))
        right.pack(side='right', fill='y')
        right.pack_propagate(False)
        ui.vsep(self).pack(side='right', fill='y')
        mid = ttk.Frame(self, style='Bg.TFrame')
        mid.pack(side='left', fill='both', expand=True)
        self._build_list(left)
        self._build_middle(mid)
        self._build_right(right)
        for t in ('quest', 'texts'):
            self.s.on(t, self._structure_changed)
        self.s.on('map', self._map_changed)
        self.s.on('script', self._script_changed)
        self.s.on('items', lambda sc, src: self.palette.refresh())
        self.s.on('creatures', lambda sc, src: self.palette.refresh())
        self.s.on('tiles', lambda sc, src: self.palette.refresh())
        self.s.on('pictures', lambda sc, src: self.palette.refresh())
        self.map.set_level(self.level)
        self.palette._apply()

    # left: the levels
    def _build_list(self, left):
        head = ttk.Frame(left)
        head.pack(fill='x', padx=px(12), pady=(px(14), px(6)))
        ttk.Label(head, text='Levels', style='H2.TLabel').pack(side='left')
        ui.button(head, '', self._add_menu, 'plus', 'Tool.TButton', 'Add a level').pack(side='right')
        self.gallery = Gallery(left, on_select=self.select_level, list_mode=True)
        self.gallery.pack(fill='both', expand=True)
        foot = ttk.Frame(left)
        foot.pack(fill='x', padx=px(10), pady=px(8))
        self.remove_btn = ui.button(foot, 'Remove last level', self._remove_last, 'trash', 'Flat.TButton')
        self.remove_btn.pack(side='left')

    def _fill_list(self):
        entries = []
        for n in range(1, self.s.levels + 1):
            c = self.counts(n)
            entries.append(Entry(n, f'{n}  {levelmeta.title(self.s, n)}' if levelmeta.title(self.s, n) != f'Level {n}' else f'Level {n}',
                                 f'{c["mon"]} creatures · {c["exits"]} exit{"s" if c["exits"] != 1 else ""}',
                                 self.thumb(n)))
        self.gallery.set_items(entries)
        self.gallery.select(self.level, scroll=True)
        self.remove_btn.state(['!disabled'] if self.s.levels > 1 else ['disabled'])

    def thumb(self, n):
        if n not in self._thumbs:
            self._thumbs[n] = self.s.pictures.level_thumb(self.s.project.grid(n), px(56))
        return self._thumbs[n]

    def counts(self, n):
        if n not in self._counts:
            g = self.s.project.grid(n)
            types = {r['id']: r.get('type', '') for r in self.s.project.tables['items']}
            c = {'mon': 0, 'item': 0, 'gold': 0, 'exits': 0}
            for x in range(1, SIZE + 1):
                col = g.sq[x]
                for y in range(1, SIZE + 1):
                    fl, wa, it, mo, go, de = col[y]
                    if mo > 0:
                        c['mon'] += 1
                    if it:
                        c['item'] += 1
                        if types.get(it) == 'exit':
                            c['exits'] += 1
                    if go > 0:
                        c['gold'] += 1
            self._counts[n] = c
        return self._counts[n]

    # middle: toolbar, map, status
    def _build_middle(self, mid):
        bar = ttk.Frame(mid, padding=(px(10), px(6)))
        bar.pack(fill='x')
        self.tools = ui.ToolStrip(bar, TOOLS, self._tool_chosen, 'brush')
        self.tools.pack(side='left')
        ui.vsep(bar).pack(side='left', fill='y', padx=px(10), pady=px(2))
        ui.button(bar, '', lambda: self.map.zoom_by(-1), 'minus', 'Tool.TButton', 'Zoom out (-)').pack(side='left')
        self.zoom_label = ttk.Label(bar, text='', width=6, anchor='center')
        self.zoom_label.pack(side='left')
        ui.button(bar, '', lambda: self.map.zoom_by(1), 'plus', 'Tool.TButton', 'Zoom in (+)').pack(side='left')
        ui.button(bar, '', self._fit, 'fit', 'Tool.TButton', 'See the whole level').pack(side='left', padx=(px(4), 0))
        ui.vsep(bar).pack(side='left', fill='y', padx=px(10), pady=px(2))
        self.grid_btn = ui.button(bar, '', self._toggle_grid, 'grid', 'Tool.TButton', 'Show or hide the grid lines')
        self.grid_btn.pack(side='left')
        self.marker_btn = ui.button(bar, '', self._toggle_markers, 'flag', 'Tool.TButton',
                                    'Show or hide the markers (start, exits, shops, screens)')
        self.marker_btn.pack(side='left', padx=px(4))
        right = ttk.Frame(bar)
        right.pack(side='right')
        ui.button(right, '', self.open_3d, 'cube', 'Tool.TButton', 'See this level as FPS mode shows it (3D view)').pack(side='left', padx=px(4))
        ui.button(right, 'Play here', self.play_here, 'play', 'TButton',
                  'Start the game on this level at the square you last clicked (or the start)').pack(side='left')
        self.map = MapView(mid, self.s, self)
        self.map.pack(fill='both', expand=True)
        strip = ttk.Frame(mid, style='Bg.TFrame', padding=(px(10), px(5)))
        strip.pack(fill='x')
        self.info = ttk.Label(strip, text='', style='Bg.TLabel', foreground=C['dim'])
        self.info.pack(side='left')
        self.sel_bar = ttk.Frame(strip, style='Bg.TFrame')
        self.sel_bar.pack(side='right')
        self.sel_label = ttk.Label(self.sel_bar, text='', style='Bg.TLabel', foreground=C['accent'])
        self.sel_label.pack(side='left', padx=px(8))
        for text, fn in (('Copy', lambda: self.map.copy()), ('Cut', lambda: self.map.copy(cut=True)),
                         ('Paste', lambda: self.map.paste()), ('Clear', lambda: self.map.clear_selection()),
                         ('Fill with brush', self._fill_selection), ('Done', self._deselect)):
            ttk.Button(self.sel_bar, text=text, style='Flat.TButton', command=fn).pack(side='left')
        self.sel_bar.pack_forget()

    # right: panels
    def _build_right(self, right):
        top = ttk.Frame(right, padding=(px(10), px(10), px(10), px(6)))
        top.pack(fill='x')
        self.seg = ui.Segmented(top, PANELS, self._panel_chosen, 'paint')
        self.seg.pack(fill='x')
        self.holder = ttk.Frame(right)
        self.holder.pack(fill='both', expand=True)
        self.palette = PalettePanel(self.holder, self)
        self.level_panel = LevelPanel(self.holder, self)
        self.places = PlacesPanel(self.holder, self)
        self.panels = {'paint': self.palette, 'level': self.level_panel, 'places': self.places}
        self.panel = None
        self._panel_chosen('paint')

    def _panel_chosen(self, key):
        if self.panel is not None:
            self.panel.pack_forget()
        self.panel = self.panels[key]
        self.panel.pack(fill='both', expand=True)
        if key in ('level', 'places'):
            self.panel.refresh()
        self.seg.choose(key, run=False)

    # ── the host contract of the MapView ────────────────────────────────────
    def on_hover(self, x, y, inside):
        if not inside:
            self.hover_sq = None
            self.info.configure(text='')
            return
        self.hover_sq = (x, y)
        p = self.s.project
        cell = self.map.grid.sq[x][y]
        parts = [f'({x}, {y})   screen ({(x - 1) // 10 + 1}, {(y - 1) // 10 + 1})']
        for layer, label in (('floor', 'Ground'), ('wall', 'Wall'), ('deco', 'Decor'), ('item', 'Item'), ('mon', 'Creature'),
                             ('gold', 'Gold')):
            v = cell[{'floor': 0, 'wall': 1, 'item': 2, 'mon': 3, 'gold': 4, 'deco': 5}[layer]]
            if v and not (layer == 'gold' and v <= 0):
                parts.append(f'{label}: {p.name_of(layer, v)}')
        self.info.configure(text='    '.join(parts))

    def on_pick(self, layer, value):
        self.palette.pick(layer, value)
        self._panel_chosen('paint')
        self.choose_tool('brush')

    def on_click(self, x, y):
        self.last_sq = (x, y)
        view = getattr(self, 'preview3d', None)
        if view is not None and view.winfo_exists():
            view.goto(x, y)

    def on_marker(self, tool, x, y):
        self.on_click(x, y)
        self.places.handle(tool, x, y)

    def on_double(self, x, y):
        kind = self.s.project.item_type(self.map.grid.sq[x][y][2])
        if kind == 'exit' or kind in levelmeta.LINK_TYPES:
            edit_link(self, x, y, kind, None)

    def on_selection(self, rect):
        if rect:
            x0, y0, x1, y1 = rect
            self.sel_label.configure(text=f'{x1 - x0 + 1} × {y1 - y0 + 1} squares')
            self.sel_bar.pack(side='right')
        else:
            self.sel_bar.pack_forget()

    def on_view_changed(self):
        self.zoom_label.configure(text=f'{self.map.zoom * 100 // 24}%')
        if self.built and hasattr(self, 'level_panel'):
            self.level_panel.view_moved()

    def choose_tool(self, tool):
        self.map.set_tool(tool)
        if tool in MARKER_TOOLS:
            self.tools.choose(None, run=False)
            self._panel_chosen('places')
            self.say(None)
        else:
            self.tools.choose(tool, run=False)
        self.places.paint_tools()

    def _tool_chosen(self, tool):
        self.map.set_tool(tool)
        self.places.paint_tools()

    def say(self, text, kind='info'):
        if text:
            self.app.say(text, kind)

    def say_locked(self, layer):
        names = {'floor': 'Ground', 'wall': 'Walls', 'deco': 'Decoration', 'item': 'Items', 'mon': 'Creatures', 'gold': 'Gold'}
        self.app.say(f'The {names[layer]} layer is locked. Click its padlock in the Paint panel to unlock it.', 'warn')

    def confirm_big(self, n):
        return ui.confirm(self, 'Fill a large area', f'This fills {n} squares. Go on?', 'Fill')

    def map_edited(self):
        self._counts.pop(self.level, None)
        self._thumbs.pop(self.level, None)
        self._schedule_thumbs()
        self.places.schedule()
        self.app.changed_world()

    def changed_places(self, map_too=False):
        self._counts.pop(self.level, None)
        self.map.refresh()
        self.places.schedule()
        if self.panel is self.level_panel:
            self.level_panel.refresh()
        self.app.changed_world()
        self._schedule_thumbs()

    def titles_changed(self):
        self._fill_list()

    # ── actions ─────────────────────────────────────────────────────────────
    def select_level(self, n):
        if n is None or n == self.level:
            return
        self.level = n
        self.app.settings['world_level'] = n
        self.map.set_level(n)
        if self.panel is self.places:
            self.places.refresh()
        if self.panel is self.level_panel:
            self.level_panel.refresh()
        self.gallery.select(n, scroll=True)
        self.last_sq = None

    def show_square(self, x, y):
        self.map.center_on(x, y)
        self.map.hover = None
        self.map.schedule()
        self.map.flash(x, y)
        self.on_view_changed()

    def show_screen(self, sx, sy):
        self.map.scroll_to_screen(sx, sy)
        self.on_view_changed()

    def _fit(self):
        self.map.zoom_fit()

    def _toggle_grid(self):
        self.map.show_grid = not self.map.show_grid
        self.map.schedule()

    def _toggle_markers(self):
        self.map.show_markers = not self.map.show_markers
        self.map.schedule()

    def _fill_selection(self):
        m = self.map
        if not m.sel:
            return
        x0, y0, x1, y1 = m.sel
        m._apply('Fill the selection', [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)])

    def _deselect(self):
        self.map.sel = None
        self.map._refresh_cursor()
        self.map._fire_selection()

    def _add_menu(self):
        m = tk.Menu(self, tearoff=False)
        m.add_command(label='A blank level', command=self.add_blank)
        m.add_command(label=f'A copy of level {self.level}', command=self.add_copy)
        m.add_command(label='Make a level with the wizard…', command=self.wizard)
        w = self.winfo_toplevel()
        m.tk_popup(w.winfo_pointerx(), w.winfo_pointery())

    def add_blank(self):
        n = levels.add_blank(self.s)
        self.app.say(f'Level {n} added. It is empty: paint it, or use the wizard.', 'ok')
        self._after_structure(n)

    def add_copy(self):
        n = levels.duplicate(self.s, self.level)
        self.app.say(f'Level {n} is a copy of level {self.level}.', 'ok')
        self._after_structure(n)

    def wizard(self):
        try:
            from ..wizard import open_wizard
        except ImportError:
            ui.inform(self, 'Level wizard', 'The level wizard is not ready yet.')
            return
        open_wizard(self.app, on_done=self._after_structure)

    def _remove_last(self):
        n = self.s.levels
        if n <= 1:
            return
        if not ui.confirm(self, 'Remove a level', f'Remove level {n}, with its map, events and shops?\n\n'
                          'You can bring it back with Undo (Ctrl+Z).', 'Remove', danger=True):
            return
        levels.remove_last(self.s)
        self._after_structure(min(self.level, self.s.levels))

    def _after_structure(self, n):
        self._thumbs.clear()
        self._counts.clear()
        self.level = n
        self.map.set_level(n)
        self._fill_list()
        for p in (self.places, self.level_panel):
            p.refresh()
        self.app.changed_world()

    def open_3d(self):
        from editor.preview3d import Preview3D
        old = getattr(self, 'preview3d', None)
        if old is not None and old.winfo_exists():
            old.destroy()
        self.preview3d = Preview3D(self, self.last_sq or self.hover_sq)
        self.preview3d.title('3D view')

    def play_here(self):
        at = self.last_sq or self.hover_sq or levelmeta.start_of(self.s, self.level)
        self.app.play(self.level, at)

    # ── notifications ───────────────────────────────────────────────────────
    def _structure_changed(self, scope, source):
        if self.s.levels != len(self.gallery.items):
            self.level = max(1, min(self.level, self.s.levels))
            self._thumbs.clear()
            self._counts.clear()
            self.map.set_level(self.level)
            self._fill_list()

    def _map_changed(self, scope, source):
        n = scope[1]
        self._thumbs.pop(n, None)
        self._counts.pop(n, None)
        if source is not self.map and self.visible:
            self._schedule_thumbs()
        elif not self.visible:
            self._dirty_list = True

    def _script_changed(self, scope, source):
        n = scope[1]
        self._counts.pop(n, None)
        if self.panel is self.level_panel and n == self.level:
            self.level_panel.refresh()
        elif self.panel is self.places and n == self.level:
            self.places.schedule()
        if source is None:
            self._schedule_thumbs()

    def _schedule_thumbs(self):
        if self._thumb_job is None:
            self._thumb_job = self.after(700, self._rethumb)

    def _rethumb(self):
        self._thumb_job = None
        if self.winfo_exists():
            self._fill_list()

    # ── life cycle ──────────────────────────────────────────────────────────
    def on_show(self, level=None, at=None, tool=None, panel=None, wizard=False, new_level=False, **where):
        if getattr(self, '_dirty_list', True) or level:
            self._dirty_list = False
            self._fill_list()
        if level:
            self.select_level(int(level))
        if at:
            self.show_square(*at)
        if panel in self.panels:
            self._panel_chosen(panel)
        if tool:
            self.choose_tool(tool)
        self.on_view_changed()
        self.map.schedule()
        self.map.canvas.focus_set()
        if wizard:
            self.after(150, self.wizard)
        if new_level:
            self.after(150, self.add_blank)

    def reload(self):
        self._thumbs.clear()
        self._counts.clear()
        self.level = max(1, min(self.level, self.s.levels))
        self.map.set_level(self.level)
        self.palette.refresh()
        self._fill_list()

    def search(self, q):
        out = []
        for n in range(1, self.s.levels + 1):
            t = levelmeta.title(self.s, n)
            if q in t.lower() or q in f'level {n}':
                out.append((t, f'level {n}', 'map', lambda n=n: self.app.go('world', level=n)))
        return out
