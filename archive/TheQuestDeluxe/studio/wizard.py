"""The level wizard: a level from start to finish in six steps, with a live picture of what you are making."""
from __future__ import annotations

import random
import textwrap
import tkinter as tk
from tkinter import ttk

from editor.art import photo

from . import levels, theme, ui, worldgen
from .gallery import Entry, Picker
from .stepdialog import StepDialog
from .theme import C, px

STEPS = [('place', 'Place', 'map'), ('land', 'Land', 'tree'), ('life', 'Life', 'skull'), ('loot', 'Loot', 'coin'),
         ('story', 'Story', 'book'), ('make', 'Make it', 'sparkle')]
THEME_CARDS = [('country', 'Countryside', 'Open fields, forest and a river, a few houses joined by paths.', 'sun'),
               ('village', 'Village', 'Streets of houses, a well, villagers and a shop.', 'home'),
               ('dungeon', 'Fortress', 'Rooms and corridors with doors, and a great room at the end.', 'door'),
               ('wilderness', 'Wilderness', 'Thick forest and a winding trail, with clearings where trouble waits.', 'tree'),
               ('maze', 'Maze', 'A twisting maze to get lost in, with the way out at the far end.', 'grid'),
               ('cave', 'Caves', 'Winding caverns of rock, with wide chambers to fight in and the way out deep inside.', 'mountain')]
SIZES = [('3', 'Small  3 × 3'), ('5', 'Medium  5 × 5'), ('7', 'Large  7 × 7'), ('10', 'Huge  10 × 10')]
CORNER_NAMES = [('sw', 'Bottom left'), ('nw', 'Top left'), ('ne', 'Top right'), ('se', 'Bottom right')]
LEVELS_OF = {'gentle': 'Gentle: few and weak, for a first level.', 'normal': 'Normal: about as busy as the original levels.',
             'tough': 'Tough: crowded, and the strong ones come sooner.', 'deadly': 'Deadly: the strong ones everywhere. Bring potions.'}

NAMES_A = ['Whispering', 'Broken', 'Silent', 'Sunken', 'Crimson', 'Forgotten', 'Wandering', 'Hollow', 'Iron', 'Misty', 'Burning',
           'Lonely', 'Thorny', 'Drowned', 'Ancient', 'Shattered']
NAMES_B = {'country': ['Meadows', 'Crossing', 'Fields', 'Downs', 'Marches'], 'village': ['Hollow', 'Green', 'Vale', 'Stead', 'Ford'],
           'dungeon': ['Keep', 'Halls', 'Vault', 'Bastion', 'Crypt'], 'wilderness': ['Woods', 'Trail', 'Thicket', 'Wilds', 'Pines'],
           'maze': ['Maze', 'Labyrinth', 'Warren', 'Tangle', 'Gardens'], 'cave': ['Caverns', 'Depths', 'Hollows', 'Grotto', 'Deeps']}
STORY_TEMPLATES = {
    'country': ['The road leaves the village behind and runs out across open country. Rivers cut it, forests crowd it, and '
                'here and there a lonely house stands in the fields.',
                'Somewhere ahead lies the way on. {boss_line}You tighten your grip and walk out into the wild.'],
    'village': ['At last, a village. Smoke rises from the chimneys and there are people in the streets, though they watch '
                'you with worried eyes.',
                'Perhaps someone here knows something. {boss_line}You step onto the main street.'],
    'dungeon': ['Cold stone, torchlight and the echo of your own steps. The old fortress is a tangle of rooms and corridors, '
                'and not all of it is empty.',
                '{boss_line}You push open the first door.'],
    'wilderness': ['The trees close in until the sky is a thin grey line. A narrow trail winds between the trunks, and '
                   'things move in the clearings.',
                   '{boss_line}You follow the trail into the dark.'],
    'cave': ['The daylight shrinks to a coin behind you. Water drips somewhere in the dark, and the tunnels split and split again '
             'between walls of wet rock.',
             '{boss_line}You keep one hand on the stone and go deeper.'],
    'maze': ['Walls rise on every side, too high to see over. Every turn looks like the last, and you are sure you hear '
             'something breathing round the next corner.',
             '{boss_line}You pick a way and walk.'],
}


class LevelWizard(StepDialog):
    STEPS = STEPS
    HEADING = 'Make a level'
    MAKE_LABEL = 'Make the level'

    def __init__(self, app, on_done=None):
        width = min(px(1120), app.root.winfo_screenwidth() - px(60))
        height = min(px(760), app.root.winfo_screenheight() - px(100))
        super().__init__(app, 'Make a level', width, height)
        self.on_done = on_done
        self.p = worldgen.Params(seed=random.randint(1, 99999))
        self.p.screens = (5, 5)
        self.extra = {'title': '', 'story': '', 'story_on': True, 'target': 'new', 'open': True, 'play': False,
                      'creatures_mode': 'auto', 'boss_on': False}
        self.detected = worldgen.detect(self.s.project)
        self.result = None
        self.step = 0
        self._job = None
        self._photo = None
        self.build_frame()
        self.go(0)
        self.refresh_now()

    def preview_pane(self, right):
        ttk.Label(right, text='What you are making', style='H3.TLabel').pack(anchor='w', padx=px(16), pady=(px(16), px(6)))
        self.canvas = tk.Canvas(right, width=px(408), height=px(408), bg=C['canvas'], highlightthickness=1,
                                highlightbackground=C['line'])
        self.canvas.pack(padx=px(16))
        bar = ttk.Frame(right)
        bar.pack(fill='x', padx=px(16), pady=px(8))
        ui.button(bar, 'Roll again', self.roll, 'dice', 'TButton', 'A different level with the same settings').pack(side='left')
        ttk.Label(bar, text='Seed').pack(side='left', padx=(px(12), px(4)))
        self.seed_var = tk.StringVar(value=str(self.p.seed))
        e = ttk.Entry(bar, textvariable=self.seed_var, width=7)
        e.pack(side='left')
        e.bind('<Return>', lambda ev: self.set_seed())
        e.bind('<FocusOut>', lambda ev: self.set_seed())
        ui.tip(e, 'The same seed and settings make the same level. Type one to get a level back.')
        self.stats = ttk.Label(right, text='', style='Dim.TLabel', wraplength=px(400), justify='left')
        self.stats.pack(anchor='w', padx=px(16))
        self.warn = ttk.Label(right, text='', style='Bad.TLabel', wraplength=px(400), justify='left')
        self.warn.pack(anchor='w', padx=px(16), pady=(px(4), 0))

    def _set(self, key, v):
        if self.guard:
            return
        if key in ('rivers', 'lakes', 'buildings', 'villagers'):
            v = int(round(v))
        setattr(self.p, key, v)
        self.refresh()

    # 1 place
    def _step_place(self):
        self.head('What kind of place is it?', 'Pick one. You can change everything afterwards, and the picture on the right shows what you get.')
        cards = ui.ChoiceCards(self.page, THEME_CARDS, self._theme, self.p.theme, columns=2, width=230)
        cards.pack(fill='x', padx=px(16), pady=(px(4), 0))
        self.h('How big?', 'Each screen is 10 by 10 squares. The hero walks from one screen to the next.')
        seg = ui.Segmented(self.page, SIZES, self._pick_size, str(self.p.screens[0]))
        seg.pack(anchor='w', padx=px(22))
        self.h('Where does the hero start?', 'The way out is in the opposite corner.')
        seg = ui.Segmented(self.page, CORNER_NAMES, self._corner, self.p.start)
        seg.pack(anchor='w', padx=px(22), pady=(0, px(16)))

    def _theme(self, key):
        self.p.theme = key
        for k, v in worldgen.theme_defaults(key).items():
            setattr(self.p, k, v)
        self.p.dark = False
        self.refresh()

    def _pick_size(self, key):
        n = int(key)
        self.p.screens = (n, n)
        self.refresh()

    def _corner(self, key):
        self.p.start = key
        self.refresh()

    # 2 land
    def _step_land(self):
        t = self.p.theme
        self.head('The land', 'How the ground looks and what is on it.')
        if t in ('country', 'wilderness'):
            self.h('Nature')
            self.number('Rivers', 'rivers', 0, 3, 'A river crosses the land. Paths bridge it where they must.')
            self.number('Lakes', 'lakes', 0, 4)
            self.number('Forest (% of the ground)', 'forest', 0, 80, scale=100)
        if t == 'village':
            self.h('The village')
            self.number('How built up', 'buildings', 1, 14, 'More houses along the streets.')
            self.number('Trees round about (%)', 'forest', 0, 60, scale=100)
        if t in ('country', 'wilderness'):
            self.number('Buildings', 'buildings', 0, 12, 'Houses to find in the landscape. Some hold chests and guards.')
        if t != 'maze':
            self.h('Extras')
        if t in ('country', 'wilderness', 'village'):
            self.switch('Paths between things', 'paths', 'Pave the routes between the start, the buildings and the way out.')
        if t in ('dungeon', 'cave'):
            self.switch('Some parts are dark' if t == 'cave' else 'Some rooms are dark', 'dark', 'Dark screens show only the hero and his light.')
        if t not in ('maze', 'cave'):
            self.switch('A locked door and its key', 'puzzle', 'A door that needs a key, with the key hidden elsewhere on the level. '
                        'It guards the last room of a fortress or the farthest house.')
        self._materials()

    def _materials(self):
        sec = ui.Section(self.page, 'What it is made of', 'chosen from this quest\'s own tiles', open_=False)
        sec.pack(fill='x', padx=px(22), pady=(px(18), px(16)))
        d, p, pic = self.detected, self.s.project, self.s.pictures

        def entries(layer, none=None):
            def make():
                return [Entry(r['id'], r.get('name') or f'#{r["id"]}', '', pic.thumb(layer, r['id'], 32))
                        for r in p.entries(layer)]
            return make
        roles = [('Ground', 'floor', 'ground', d.ground, False), ('Path', 'floor', 'path', d.path, True),
                 ('Trees and thickets', 'wall', 'trees', d.trees[0] if d.trees else None, True),
                 ('Water', 'wall', 'water', d.water, True), ('Building walls', 'wall', 'building', d.building[0] if d.building else None, True),
                 ('Indoor floor', 'floor', 'indoor', d.indoor[0] if d.indoor else None, True),
                 ('Doors', 'wall', 'door', d.door, True)]
        for label, layer, key, value, optional in roles:
            row = ttk.Frame(sec.body)
            row.pack(fill='x', pady=2)
            ttk.Label(row, text=label, width=18).pack(side='left')
            cur = self.p.style.get(key, value)
            if isinstance(cur, list):
                cur = cur[0] if cur else None

            def chosen(v, key=key):
                self.p.style[key] = ([v] if key in ('trees', 'building', 'indoor') and v is not None else v)
                if v is None and key in ('trees', 'building', 'indoor'):
                    self.p.style[key] = []
                self.refresh()
            Picker(row, entries(layer), cur, chosen, none_label='(none)' if optional else None, width=24).pack(side='left')

    # 3 life
    def _step_life(self):
        self.head('Who lives here?', 'How dangerous the level is, and which creatures roam it.')
        self.h('How hard?')
        seg = ui.Segmented(self.page, [('gentle', 'Gentle'), ('normal', 'Normal'), ('tough', 'Tough'), ('deadly', 'Deadly')],
                           self._difficulty, self.p.difficulty)
        seg.pack(anchor='w', padx=px(22))
        self.level_text = ttk.Label(self.page, text=LEVELS_OF[self.p.difficulty], style='Dim.TLabel', wraplength=px(470))
        self.level_text.pack(anchor='w', padx=px(22), pady=(px(4), 0))
        self.number('How many creatures (%)', 'monsters', 20, 300, 'Scale the crowd up or down.', scale=100)
        self.switch('A calm start', 'calm_start', 'No hostile creatures on the screen the hero starts on, and people there do not '
                    'fight.')
        self.number('People about', 'villagers', 0, 12, 'Villagers and farmers that stand about and talk.')
        self.h('Who roams here', 'Click to choose the creatures yourself. Left alone, they are picked by how hard it is, the weak '
               'ones near the start and the strong ones near the end.')
        bar = ttk.Frame(self.page)
        bar.pack(fill='x', padx=px(22), pady=(0, px(4)))
        ttk.Button(bar, text='Pick for me', command=self._auto_creatures).pack(side='left')
        ttk.Label(bar, text='  or the crowd of level', style='Dim.TLabel').pack(side='left')
        self.like = ttk.Combobox(bar, state='readonly', width=4, values=[str(n) for n in range(1, self.s.levels + 1)])
        self.like.pack(side='left', padx=px(6))
        self.like.bind('<<ComboboxSelected>>', lambda e: self._like_level(int(self.like.get())))
        holder = ttk.Frame(self.page, height=px(250))
        holder.pack(fill='x', padx=px(18))
        holder.pack_propagate(False)
        from .gallery import Gallery
        pic = self.s.pictures
        hostile = worldgen.hostile(self.s.project)
        self.creature_entries = [Entry(c['id'], c.get('name') or f'#{c["id"]}', f'danger {worldgen.threat(c):.0f}',
                                       pic.thumb('mon', c['id'], 40, 'raised')) for c in hostile]
        self.cgal = Gallery(holder, on_picks=self._creatures, list_mode=True, toggle=True)
        self.cgal.pack(fill='both', expand=True)
        self.cgal.set_items(self.creature_entries)
        self._show_creatures()
        self.h('A boss', 'One big creature waits near the way out.')
        r = ttk.Frame(self.page)
        r.pack(fill='x', padx=px(22), pady=(0, px(16)))
        bosses = [c for c in worldgen.hostile(self.s.project) if (c.get('life') or 0) >= 120 or int(c.get('size') or 1) > 1]
        Picker(r, lambda: [Entry(c['id'], c.get('name') or f'#{c["id"]}', f'danger {worldgen.threat(c):.0f}',
                                 pic.thumb('mon', c['id'], 32)) for c in bosses], self.p.boss, self._boss,
               none_label='No boss', width=26).pack(side='left')

    def _difficulty(self, key):
        self.p.difficulty = key
        self.level_text.configure(text=LEVELS_OF[key])
        self._show_creatures()
        self.refresh()

    def _show_creatures(self):
        if self.p.creatures:
            self.cgal.set_picks(self.p.creatures)
        else:
            pool, _ = worldgen.monster_pool(self.s.project, self.p)
            self.cgal.set_picks([c['id'] for c in pool])

    def _creatures(self, keys):
        if self.guard:
            return
        self.p.creatures = [k for k in keys]
        self.refresh()

    def _auto_creatures(self):
        self.p.creatures = []
        self._show_creatures()
        self.refresh()

    def _like_level(self, n):
        from collections import Counter
        grid = self.s.project.grid(n)
        hostile_ids = {c['id'] for c in worldgen.hostile(self.s.project)}
        count = Counter(grid.sq[x][y][3] for x in range(1, 101) for y in range(1, 101) if grid.sq[x][y][3] in hostile_ids)
        picks = [k for k, v in count.items() if v >= 2]
        if picks:
            self.p.creatures = picks
            self._show_creatures()
            self.refresh()

    def _boss(self, key):
        self.p.boss = key
        self.refresh()

    # 4 loot
    def _step_loot(self):
        t = self.p.theme
        self.head('Treasure and shops', 'What the hero can find, and where he can spend it.')
        self.h('Things to find')
        self.number('Gold (%)', 'gold', 0, 300, 'Heaps of gold, more of it the farther from the start.', scale=100)
        self.number('Potions (%)', 'potions', 0, 300, scale=100)
        self.number('Weapons and armour (%)', 'gear', 0, 300, 'Better ones the farther from the start.', scale=100)
        self.switch('Chests in the buildings', 'chests', 'Closed chests that hold gold.')
        if t not in ('maze', 'dungeon', 'cave'):
            self.h('A shop')
            self.switch('Make one house a shop', 'shop', 'A shopkeeper in a house near the start sells potions and gear that '
                        'suit the level. You can change what he sells on the Shops page.')

    # 5 story
    def _step_story(self):
        self.head('The story', 'A name for the level, and the words the hero reads before it begins.')
        self.h('Name')
        r = ttk.Frame(self.page)
        r.pack(fill='x', padx=px(22))
        self.title_var = tk.StringVar(value=self.extra['title'])
        e = ttk.Entry(r, textvariable=self.title_var)
        e.pack(side='left', fill='x', expand=True)
        self.title_var.trace_add('write', lambda *a: self.extra.__setitem__('title', self.title_var.get().strip()))
        ui.button(r, '', self._suggest_title, 'dice', 'Tool.TButton', 'Suggest a name').pack(side='left', padx=px(6))
        self.h('Before the level', 'It is shown as a story page, in the game\'s own style.')
        self.switch('Show a story before this level', 'story_on', store=self.extra)
        self.story_box = tk.Text(self.page, height=11, width=60, wrap='word', bg=C['input'], fg=C['text'], insertbackground=C['text'],
                                 relief='flat', highlightthickness=1, highlightbackground=C['line'], highlightcolor=C['accent'],
                                 font=(theme.FONT, 10), padx=8, pady=6, undo=True)
        self.story_box.pack(fill='x', padx=px(22), pady=(px(8), 0))
        self.story_box.insert('1.0', self.extra['story'])
        self.story_box.bind('<KeyRelease>', lambda e: self._story_typed())
        bar = ttk.Frame(self.page)
        bar.pack(fill='x', padx=px(22), pady=px(6))
        ttk.Button(bar, text='Write something for me', command=self._suggest_story).pack(side='left')
        self.story_info = ttk.Label(bar, text='', style='Faint.TLabel')
        self.story_info.pack(side='left', padx=px(10))
        self._story_typed()

    def _story_typed(self):
        text = self.story_box.get('1.0', 'end-1c')
        self.extra['story'] = text
        lines = self._wrap(text)
        self.story_info.configure(text=f'{len(lines)} lines of the 15 the page holds', foreground=C['bad'] if len(lines) > 15 else C['faint'])

    @staticmethod
    def _wrap(text):
        out = []
        for para in text.split('\n'):
            out += textwrap.wrap(para, 72) or ['']
        while out and out[-1] == '':
            out.pop()
        return out

    def _suggest_title(self):
        rng = random.Random()
        self.title_var.set(f'{rng.choice(NAMES_A)} {rng.choice(NAMES_B.get(self.p.theme, NAMES_B["country"]))}')

    def _suggest_story(self):
        boss = next((c for c in self.s.project.tables['creatures'] if c['id'] == self.p.boss), None) if self.p.boss else None
        line = f'Word is that {boss["name"]} waits near the end. ' if boss else ''
        text = '\n\n'.join(t.format(boss_line=line) for t in STORY_TEMPLATES.get(self.p.theme, STORY_TEMPLATES['country']))
        self.story_box.delete('1.0', 'end')
        self.story_box.insert('1.0', text)
        self._story_typed()

    # 6 make it
    def _step_make(self):
        self.head('Make it', 'Look over the picture, roll again if you like, then make the level.')
        r = self.result
        s = self.s
        self.h('Where it goes')
        box = ttk.Frame(self.page)
        box.pack(fill='x', padx=px(22))
        self.target = tk.StringVar(value=self.extra['target'])
        ttk.Radiobutton(box, text=f'As a new level, number {s.levels + 1}', value='new', variable=self.target,
                        command=lambda: self.extra.__setitem__('target', 'new')).pack(anchor='w')
        for n in range(1, s.levels + 1):
            ttk.Radiobutton(box, text=f'In place of the map of level {n}  (its events and shops stay)', value=str(n),
                            variable=self.target, command=lambda n=n: self.extra.__setitem__('target', str(n))).pack(anchor='w')
        self.h('What you get')
        st = r.stats if r else {}
        facts = [f'{st.get("creatures", 0)} creatures, {st.get("people", 0)} people',
                 f'{st.get("gold", 0)} heaps of gold, {st.get("items", 0)} items, {st.get("chests", 0)} chests',
                 f'{st.get("buildings", 0)} buildings or rooms']
        if r and r.shop_screens:
            facts.append('a shop with a shopkeeper')
        if r and st.get('puzzle'):
            facts.append(f'a locked {st["puzzle"]} door and its key')
        for f in facts:
            ttk.Label(self.page, text='•  ' + f).pack(anchor='w', padx=px(26))
        self.h('Afterwards')
        self.switch('Open it in the World page', 'open', store=self.extra)
        self.switch('Try it in the game', 'play', 'Start the game on this level straight away.', store=self.extra)

    # ── the picture ─────────────────────────────────────────────────────────
    def roll(self):
        self.p.seed = random.randint(1, 99999)
        self.seed_var.set(str(self.p.seed))
        self.refresh_now()

    def set_seed(self):
        try:
            v = int(self.seed_var.get())
        except ValueError:
            self.seed_var.set(str(self.p.seed))
            return
        if v != self.p.seed:
            self.p.seed = v
            self.refresh()

    def refresh(self):
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(260, self.refresh_now)

    def refresh_now(self):
        self._job = None
        if not self.winfo_exists():
            return
        try:
            self.result = worldgen.generate(self.s.project, self.p)
        except Exception as e:                                       # noqa: BLE001 - show it, do not crash the wizard
            import traceback
            traceback.print_exc()
            self.stats.configure(text='')
            self.warn.configure(text=f'Could not make a level with these settings ({e}). Change something and try again.')
            return
        self._draw()
        if STEPS[self.step][0] == 'make':
            self.go(self.step)

    def _draw(self):
        r = self.result
        w, h = r.area
        size = px(408)
        scale = max(2, size // max(w, h))
        surf = self.s.pictures.level_surface(r.sq, 1, 1, w, h, scale)
        self._photo = photo(surf)
        c = self.canvas
        c.delete('all')
        ox, oy = (size - w * scale) // 2, (size - h * scale) // 2
        c.create_image(ox, oy, image=self._photo, anchor='nw')
        for k in range(0, w // 10 + 1):
            c.create_line(ox + k * 10 * scale, oy, ox + k * 10 * scale, oy + h * scale, fill='#ffffff', stipple='gray50')
        for k in range(0, h // 10 + 1):
            c.create_line(ox, oy + k * 10 * scale, ox + w * scale, oy + k * 10 * scale, fill='#ffffff', stipple='gray50')

        def mark(x, y, colour, text):
            px_, py_ = ox + (x - 0.5) * scale, oy + (y - 0.5) * scale
            c.create_oval(px_ - 7, py_ - 7, px_ + 7, py_ + 7, fill=colour, outline='#000000', width=2)
            c.create_text(px_ + 10, py_, text=text, anchor='w', fill='#ffffff', font=(theme.FONT, 9, 'bold'))
        mark(*r.start, C['accent'], 'Start')
        if r.exit:
            mark(*r.exit, '#e65a4b', 'Exit')
        for (sx, sy), k in r.shop_screens.items():
            mark((sx - 1) * 10 + 5, (sy - 1) * 10 + 5, '#4b7be6', 'Shop')
        st = r.stats
        self.stats.configure(text=f'{st["creatures"]} creatures · {st["gold"]} gold heaps · {st["items"]} items · '
                                  f'{st["chests"]} chests · {st["walkable"]} squares to walk on')
        self.warn.configure(text='\n'.join(r.warnings[:4]))

    # ── making it ───────────────────────────────────────────────────────────
    def close(self, value):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
        super().close(value)

    def create(self):
        r = self.result
        if r is None:
            return
        s, p = self.s, self.s.project
        e = self.extra
        target = e['target']
        n = p.levels + 1 if target == 'new' else int(target)
        title = e['title']
        story_lines = self._wrap(e['story']) if e['story_on'] and e['story'].strip() else []
        if len(story_lines) > 15:
            ui.inform(self, 'Too much story', 'A story page holds 15 lines. Shorten the story a little.')
            self.go(4)
            return
        scopes = ['quest', ('map', n), ('script', n), ('shops', n)]
        if story_lines:
            scopes.append('texts')
        with s.edit('Make a level with the wizard', *dict.fromkeys(scopes)):
            levels.put_generated(s, n, r, title, story_lines, new=target == 'new')
        done = self.on_done
        play = e['play']
        want_open = e['open']
        super().close(n)
        if done and want_open:
            done(n)
        if play:
            s.autosave()
            self.app.play(n)


def open_wizard(app, on_done=None):
    w = LevelWizard(app, on_done)
    return w.run()
