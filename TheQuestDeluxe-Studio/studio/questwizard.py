"""The quest wizard: a whole quest, level after level, from a few choices, with a picture of every level before it exists.

It makes each level with the same generator as the level wizard, one kind of place after another, the creatures and the wares
getting tougher and dearer as the quest goes on, a story page before each level, an opening and an ending, and a boss at the end.
Everything it makes is ordinary levels, creatures and stories: change any of it afterwards.
"""
from __future__ import annotations

import random
import textwrap
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from studio.art import photo

from . import levels, storytext, theme, ui, worldgen
from .gallery import Entry, Picker
from .stepdialog import StepDialog, wizard_size
from .theme import C, px
from .wizard import NAMES_A, NAMES_B, STORY_TEMPLATES, THEME_CARDS

STEPS = [('adventure', 'Adventure', 'map'), ('levels', 'Levels', 'grid'), ('story', 'Story', 'book'), ('make', 'Make it', 'sparkle')]
THEME_NAMES = {k: title for k, title, *_ in THEME_CARDS}
JOURNEYS = [('classic', 'The classic road', 'From a village out into the country, through the wilds and the caves, to a fortress.', 'map'),
            ('depths', 'Into the depths', 'Caves and fortresses, each one deeper than the last.', 'mountain'),
            ('wild', 'The wild lands', 'Open country and thick forest, with a village on the way.', 'tree'),
            ('maze', 'Lost in the mazes', 'Maze after maze, each harder to get out of.', 'grid'),
            ('mix', 'Surprise me', 'Any kinds of place, in any order.', 'dice')]
RAMPS = [('easy', 'A gentle climb'), ('steady', 'Steady'), ('steep', 'A steep climb')]
RAMP_TEXT = {'easy': 'Gentle at first, and only normal by the end. Good for young players.',
             'steady': 'Gentle, then normal, then tough, about as the original quest goes.',
             'steep': 'Normal from the start, tough in the middle and deadly at the end.'}
SIZES = [('3', 'Small  3 × 3'), ('5', 'Medium  5 × 5'), ('7', 'Large  7 × 7')]
OPENING = ('{title}\n\nThe land is in trouble, and nobody else is going to do anything about it. You pick up what you own, tell no '
           'one where you are going, and set out along the road.')
ENDING = ('It is over. The last of the guards lies still, the way out stands open, and for the first time in a long while the '
          'air is quiet.\n\nYou walk out into the light. Whatever comes next, {title} is a story they will tell.')
CARRY_ON = ['{prev} lies behind you now.', 'You have left {prev} far behind.', 'After {prev}, the next road is a relief.']


def make_name(theme_key: str, rng: random.Random, used: set) -> str:
    for _ in range(40):
        name = f'{rng.choice(NAMES_A)} {rng.choice(NAMES_B.get(theme_key, NAMES_B["country"]))}'
        if name not in used:
            return name
    return name


def wrap_story(text: str) -> list:
    out = []
    for para in text.split('\n'):
        out += textwrap.wrap(para, 72) or ['']
    while out and out[-1] == '':
        out.pop()
    return out


class QuestWizard(StepDialog):
    STEPS = STEPS
    HEADING = 'Make a quest'
    MAKE_LABEL = 'Make the quest'
    PREVIEW_WIDTH = 470

    def __init__(self, app, on_done=None):
        width, height = wizard_size(app.root)
        super().__init__(app, 'Make a whole quest', width, height)
        self.on_done = on_done
        s = self.s
        self.rng = random.Random()
        blank = self.is_blank()
        self.blank = blank
        q = s.project.quest
        title = q.get('title') or ('My Quest' if blank else s.project.name) or 'My Quest'
        self.p = SimpleNamespace(title=title, author=q.get('author') or '', count=5, journey='classic', ramp='steady', size=5,
                                 boss_mode='last', boss=None, puzzles=True, stories=True, opening=True, ending=True,
                                 target='blank' if blank else 'after', play=False, open=True)
        self.opening_edited = self.ending_edited = False
        self.opening_text = ''
        self.ending_text = ''
        self.specs = []
        self.results = []
        self.photos = []
        self._job = None
        self._gen = None
        self.custom = False
        self.rebuild_specs()
        self.write_stories()
        self.build_frame()
        self.go(0)
        self.refresh_now()

    # ── what is there already ───────────────────────────────────────────────
    def is_blank(self):
        p = self.s.project
        if p.levels != 1:
            return False
        g = p.grid(1)
        return not any(g.sq[x][y][1] or g.sq[x][y][2] or g.sq[x][y][3] or g.sq[x][y][4] for x in range(1, 101) for y in range(1, 101))

    # ── the levels it will make ─────────────────────────────────────────────
    def rebuild_specs(self):
        """One entry per level. The themes follow the journey, unless some were chosen by hand (or the journey is "surprise me",
        which keeps what it picked); names, sizes and seeds are kept, and a level that changes its kind of place gets a new name."""
        p = self.p
        keep = self.specs
        fresh = worldgen.journey_themes(p.journey, p.count, self.rng)
        hold = self.custom or p.journey == 'mix'
        used = {sp['name'] for sp in keep}
        specs = []
        for i in range(p.count):
            theme_key = keep[i]['theme'] if hold and i < len(keep) else fresh[i]
            sp = keep[i] if i < len(keep) else {'name': '', 'seed': self.rng.randint(1, 99999), 'story': '', 'story_edited': False,
                                                 'size': p.size, 'size_edited': False, 'name_edited': False, 'named_for': None}
            sp['theme'] = theme_key
            if not sp['size_edited']:
                sp['size'] = p.size
            if not sp['name_edited'] and sp['named_for'] != theme_key:
                sp['name'] = make_name(theme_key, self.rng, used)
                sp['named_for'] = theme_key
                used.add(sp['name'])
            specs.append(sp)
        self.specs = specs

    def write_stories(self, only_unedited=True):
        """The opening, the ending and a page before each level, written from the themes (the ones typed by hand are kept)."""
        p = self.p
        title = p.title.strip() or 'the quest'
        if not (only_unedited and getattr(self, 'opening_edited', False)):
            self.opening_text = OPENING.format(title=title)
        if not (only_unedited and getattr(self, 'ending_edited', False)):
            self.ending_text = ENDING.format(title=title)
        for i, sp in enumerate(self.specs):
            if only_unedited and sp.get('story_edited'):
                continue
            paras = list(STORY_TEMPLATES.get(sp['theme'], STORY_TEMPLATES['country']))
            boss = self.boss_for(i)
            line = f'Word is that {boss["name"]} waits near the end. ' if boss else ''
            text = '\n\n'.join(t.format(boss_line=line) for t in paras)
            if i > 0:
                text = self.rng.choice(CARRY_ON).format(prev=self.specs[i - 1]['name']) + ' ' + text
            sp['story'] = text

    # ── params ──────────────────────────────────────────────────────────────
    def boss_candidates(self):
        project = self.s.project
        made = worldgen._produced(project)
        return [c for c in worldgen.hostile(project) if ((c.get('life') or 0) >= 120 or int(c.get('size') or 1) > 1) and c['id'] not in made]

    def boss_for(self, i):
        if self.p.boss_mode == 'none' or i != self.p.count - 1:
            return None
        cands = self.boss_candidates()
        if self.p.boss is not None:
            return next((c for c in self.s.project.tables['creatures'] if c['id'] == self.p.boss), None)
        return cands[round(0.5 * (len(cands) - 1))] if cands else None

    def params_for(self, i):
        sp, p = self.specs[i], self.p
        boss = self.boss_for(i)
        q = worldgen.quest_params(i, len(self.specs), sp['theme'], sp['seed'], int(sp['size']), p.ramp, boss['id'] if boss else None, p.puzzles)
        return q

    # ── the picture on the right ────────────────────────────────────────────
    def preview_pane(self, right):
        ttk.Label(right, text='The levels it will make', style='H3.TLabel').pack(anchor='w', padx=px(16), pady=(px(16), px(2)))
        self.preview_note = ttk.Label(right, text='', style='Dim.TLabel', wraplength=px(430), justify='left')
        self.preview_note.pack(anchor='w', padx=px(16), pady=(0, px(6)))
        self.gal = ui.Scrolled(right)
        self.gal.pack(fill='both', expand=True, padx=(px(10), 0))
        self.warn = ttk.Label(right, text='', style='Bad.TLabel', wraplength=px(430), justify='left')
        self.warn.pack(anchor='w', padx=px(16), pady=px(6))

    def refresh(self):
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(280, self.refresh_now)

    def refresh_now(self):
        self._job = None
        if not self.winfo_exists():
            return
        if self._gen is not None:
            try:
                self.after_cancel(self._gen)
            except tk.TclError:
                pass
        self.results = [None] * len(self.specs)
        self._cards()
        self._gen = self.after(10, lambda: self._make_one(0))

    def _make_one(self, i):
        """One level a moment, so the window stays alive while a big quest is drawn."""
        self._gen = None
        if not self.winfo_exists() or i >= len(self.specs):
            self._summary()
            return
        try:
            self.results[i] = worldgen.generate(self.s.project, self.params_for(i))
        except Exception as e:                                           # noqa: BLE001 - say so, do not crash the wizard
            import traceback
            traceback.print_exc()
            self.warn.configure(text=f'Level {i + 1} could not be made with these settings ({e}).')
        self._card_image(i)
        self._gen = self.after(8, lambda: self._make_one(i + 1))

    def _cards(self):
        body = self.gal.body
        for w in body.winfo_children():
            w.destroy()
        self.photos = [None] * len(self.specs)
        self.card_labels = []
        for c in range(2):
            body.columnconfigure(c, weight=1, uniform='c')
        for i, sp in enumerate(self.specs):
            card = tk.Frame(body, bg=C['raised'], highlightthickness=1, highlightbackground=C['line'])
            card.grid(row=i // 2, column=i % 2, padx=px(5), pady=px(5), sticky='nsew')
            img = tk.Label(card, bg=C['canvas'], width=px(200) // 7, height=px(200) // 15, text='…', fg=C['faint'])
            img.pack(padx=px(6), pady=(px(6), 0))
            tk.Label(card, text=f'{i + 1}  {sp["name"]}', bg=C['raised'], fg=C['text'], font=(theme.FONT, 10, 'bold'),
                     anchor='w').pack(fill='x', padx=px(8), pady=(px(4), 0))
            info = tk.Label(card, text=THEME_NAMES.get(sp['theme'], sp['theme']), bg=C['raised'], fg=C['dim'], anchor='w',
                            font=(theme.FONT, 9))
            info.pack(fill='x', padx=px(8), pady=(0, px(6)))
            for w in (card, img, info):
                w.bind('<Button-1>', lambda e, i=i: self.go(1))
            self.card_labels.append((img, info))

    def _card_image(self, i):
        r = self.results[i]
        if r is None or i >= len(self.card_labels):
            return
        img, info = self.card_labels[i]
        w, h = r.area
        scale = max(1, px(200) // max(w, h))
        surf = self.s.pictures.level_surface(r.sq, 1, 1, w, h, scale)
        self.photos[i] = photo(surf)
        try:
            img.configure(image=self.photos[i], width=surf.get_width(), height=surf.get_height(), text='')
            st = r.stats
            sp = self.specs[i]
            info.configure(text=f'{THEME_NAMES.get(sp["theme"], sp["theme"])} · {st["creatures"]} creatures')
        except tk.TclError:
            pass

    def _summary(self):
        warns = []
        for i, r in enumerate(self.results):
            if r is not None:
                warns += [f'Level {i + 1}: {w}' for w in r.warnings[:1]]
        self.warn.configure(text='\n'.join(warns[:4]))
        n = len(self.specs)
        total = sum(r.stats['creatures'] for r in self.results if r)
        self.preview_note.configure(text=f'{n} levels, {total} creatures in all. Click one to change it.')

    # ── step 1 ──────────────────────────────────────────────────────────────
    def _step_adventure(self):
        p = self.p
        self.head('What kind of adventure?', 'A few choices make a whole quest. Everything it makes you can change afterwards.')
        if self.blank:
            self.h('The quest')
            r = ttk.Frame(self.page)
            r.pack(fill='x', padx=px(22))
            ttk.Label(r, text='Title', width=8).pack(side='left')
            self.title_var = tk.StringVar(value=p.title)
            e = ttk.Entry(r, textvariable=self.title_var)
            e.pack(side='left', fill='x', expand=True)
            self.title_var.trace_add('write', lambda *a: self._text('title', self.title_var.get()))
            r = ttk.Frame(self.page)
            r.pack(fill='x', padx=px(22), pady=(px(6), 0))
            ttk.Label(r, text='Author', width=8).pack(side='left')
            self.author_var = tk.StringVar(value=p.author)
            e = ttk.Entry(r, textvariable=self.author_var)
            e.pack(side='left', fill='x', expand=True)
            self.author_var.trace_add('write', lambda *a: self._text('author', self.author_var.get()))
        self.h('The journey', 'Which kinds of place the hero passes through, in order. You can change any of them on the next page.')
        cards = ui.ChoiceCards(self.page, JOURNEYS, self._journey, p.journey, columns=2, width=230)
        cards.pack(fill='x', padx=px(16))
        self.h('How many levels?', 'Each one is a whole level, with its own map, creatures and treasure.')
        r = self.line('Levels')
        num = ui.Number(r, 2, 500, p.count, live=lambda v: self._set('count', v), commit=lambda v: self._set('count', v), width=3, soft_max=20)
        num.pack(side='right')
        self.h('How big is each level?')
        ui.Segmented(self.page, SIZES, self._pick_size, str(p.size)).pack(anchor='w', padx=px(22))
        self.h('How hard does it get?')
        seg = ui.Segmented(self.page, RAMPS, self._ramp, p.ramp)
        seg.pack(anchor='w', padx=px(22))
        self.ramp_text = ttk.Label(self.page, text=RAMP_TEXT[p.ramp], style='Dim.TLabel', wraplength=px(470), justify='left')
        self.ramp_text.pack(anchor='w', padx=px(22), pady=(px(4), 0))
        self.h('The last level', 'A big creature waits near the way out of it.')
        self.boss_seg = ui.Segmented(self.page, [('last', 'A boss'), ('none', 'No boss')], self._boss_mode, p.boss_mode)
        self.boss_seg.pack(anchor='w', padx=px(22))
        pic = self.s.pictures
        bosses = self.boss_candidates()
        self.boss_row = ttk.Frame(self.page)
        ttk.Label(self.boss_row, text='Which one').pack(side='left', padx=(0, px(8)))
        Picker(self.boss_row, lambda: [Entry(c['id'], c.get('name') or f'#{c["id"]}', f'danger {worldgen.threat(c):.0f}',
                                             pic.thumb('mon', c['id'], 32)) for c in bosses], p.boss, self._boss, none_label='One that fits',
               width=26).pack(side='left')
        if p.boss_mode != 'none':
            self.boss_row.pack(fill='x', padx=px(22), pady=(px(8), px(16)))

    def _text(self, key, value):
        setattr(self.p, key, value)
        if key == 'title':
            self.write_stories()

    def _journey(self, key):
        self.p.journey = key
        self.custom = False
        self.rebuild_specs()
        self.write_stories()
        self.refresh()

    def _pick_size(self, key):
        self.p.size = int(key)
        for sp in self.specs:
            sp['size_edited'] = False
            sp['size'] = self.p.size
        self.refresh()

    def _ramp(self, key):
        self.p.ramp = key
        self.ramp_text.configure(text=RAMP_TEXT[key])
        self.refresh()

    def _boss_mode(self, key):
        self.p.boss_mode = key
        if key == 'none':
            self.boss_row.pack_forget()
        else:
            self.boss_row.pack(fill='x', padx=px(22), pady=(px(8), px(16)))
        self.write_stories()
        self.refresh()

    def _boss(self, key):
        self.p.boss = key
        self.write_stories()
        self.refresh()

    def _set(self, key, v):
        if self.guard:
            return
        if key == 'count':
            self.p.count = int(v)
            self.rebuild_specs()
            self.write_stories()
            self.refresh()

    # ── step 2 ──────────────────────────────────────────────────────────────
    def _step_levels(self):
        self.head('The levels', 'What kind of place each level is, how big, and what it is called. The dice make a different one.')
        names = [(k, t) for k, t, *_ in THEME_CARDS]
        for i, sp in enumerate(self.specs):
            box = tk.Frame(self.page, bg=C['raised'], highlightthickness=1, highlightbackground=C['line'])
            box.pack(fill='x', padx=px(22), pady=px(4))
            inner = ttk.Frame(box, style='Raised.TFrame', padding=px(8))
            inner.pack(fill='x')
            ttk.Label(inner, text=f'Level {i + 1}', style='Raised.TLabel', font=(theme.FONT, 10, 'bold')).grid(row=0, column=0, sticky='w')
            tv = tk.StringVar(value=THEME_NAMES.get(sp['theme'], sp['theme']))
            cb = ttk.Combobox(inner, state='readonly', width=13, values=[t for _, t in names], textvariable=tv)
            cb.grid(row=0, column=1, padx=px(8))
            cb.bind('<<ComboboxSelected>>', lambda e, i=i, tv=tv: self._theme_of(i, next(k for k, t in names if t == tv.get())))
            sv = tk.StringVar(value=next(t for k, t in SIZES if k == str(sp['size'])))
            cs = ttk.Combobox(inner, state='readonly', width=13, values=[t for _, t in SIZES], textvariable=sv)
            cs.grid(row=0, column=2)
            cs.bind('<<ComboboxSelected>>', lambda e, i=i, sv=sv: self._size_of(i, next(k for k, t in SIZES if t == sv.get())))
            nv = tk.StringVar(value=sp['name'])
            ne = ttk.Entry(inner, textvariable=nv)
            ne.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(px(6), 0))
            nv.trace_add('write', lambda *a, i=i, nv=nv: self._name_of(i, nv.get()))
            ui.button(inner, '', lambda i=i: self._reroll(i), 'dice', 'Tool.TButton', 'A different level of this kind').grid(
                row=0, column=3, padx=(px(8), 0))
            inner.columnconfigure(2, weight=1)
        ttk.Frame(self.page, height=px(12)).pack()

    def _theme_of(self, i, key):
        self.specs[i]['theme'] = key
        self.specs[i]['name_edited'] = False
        self.custom = True
        self.rebuild_specs()
        self.write_stories()
        self.refresh()

    def _size_of(self, i, key):
        self.specs[i]['size'] = int(key)
        self.specs[i]['size_edited'] = True
        self.refresh()

    def _name_of(self, i, text):
        self.specs[i]['name'] = text.strip()
        self.specs[i]['name_edited'] = True

    def _reroll(self, i):
        self.specs[i]['seed'] = self.rng.randint(1, 99999)
        self.refresh()

    # ── step 3 ──────────────────────────────────────────────────────────────
    def _step_story(self):
        p = self.p
        self.head('The story', 'Pages of words shown before each level, as in the original. Written for you from the places; change any of them.')
        self.switch('An opening story', 'opening', 'Shown when a new game begins.', refresh=False)
        self.switch('A story page before each level', 'stories', 'The hero reads a page before every level.', refresh=False)
        self.switch('An ending', 'ending', 'Shown after the last level, before the credits.', refresh=False)
        self.h('Opening')
        self.open_box = self._box(self.opening_text, 5, self._typed_opening)
        self.h('Before a level')
        r = ttk.Frame(self.page)
        r.pack(fill='x', padx=px(22))
        self.which = ttk.Combobox(r, state='readonly', width=34, values=[f'Level {i + 1}   {sp["name"]}' for i, sp in enumerate(self.specs)])
        self.which.current(0)
        self.which.pack(side='left')
        self.which.bind('<<ComboboxSelected>>', lambda e: self._load_level_story())
        self.level_box = self._box('', 8, self._typed_level)
        self.level_info = ttk.Label(self.page, text='', style='Faint.TLabel')
        self.level_info.pack(anchor='w', padx=px(22))
        self.h('Ending')
        self.end_box = self._box(self.ending_text, 5, self._typed_ending)
        bar = ttk.Frame(self.page)
        bar.pack(fill='x', padx=px(22), pady=px(10))
        ttk.Button(bar, text='Write them all again', command=self._rewrite).pack(side='left')
        self._load_level_story()

    def _box(self, text, height, typed):
        t = tk.Text(self.page, height=height, width=60, wrap='word', bg=C['input'], fg=C['text'], insertbackground=C['text'],
                    relief='flat', highlightthickness=1, highlightbackground=C['line'], highlightcolor=C['accent'],
                    font=(theme.FONT, 10), padx=8, pady=6, undo=True)
        t.pack(fill='x', padx=px(22), pady=(px(6), 0))
        t.insert('1.0', text)
        t.bind('<KeyRelease>', lambda e: typed())
        return t

    def _typed_opening(self):
        self.opening_text = self.open_box.get('1.0', 'end-1c')
        self.opening_edited = True

    def _typed_ending(self):
        self.ending_text = self.end_box.get('1.0', 'end-1c')
        self.ending_edited = True

    def _level_index(self):
        return max(0, self.which.current())

    def _load_level_story(self):
        i = self._level_index()
        self.level_box.delete('1.0', 'end')
        self.level_box.insert('1.0', self.specs[i]['story'])
        self._typed_level(mark=False)

    def _typed_level(self, mark=True):
        i = self._level_index()
        text = self.level_box.get('1.0', 'end-1c')
        self.specs[i]['story'] = text
        if mark:
            self.specs[i]['story_edited'] = True
        lines = wrap_story(text)
        self.level_info.configure(text=f'{len(lines)} lines of the 15 a page holds', foreground=C['bad'] if len(lines) > 15 else C['faint'])

    def _rewrite(self):
        self.opening_edited = self.ending_edited = False
        for sp in self.specs:
            sp['story_edited'] = False
        self.write_stories(only_unedited=False)
        self.go(self.step)

    # ── step 4 ──────────────────────────────────────────────────────────────
    def _step_make(self):
        p = self.p
        s = self.s
        self.head('Make it', 'Look over the pictures on the right, roll any level again if you like, then make the quest.')
        self.h('Where it goes')
        box = ttk.Frame(self.page)
        box.pack(fill='x', padx=px(22))
        self.target = tk.StringVar(value=p.target)
        if self.blank:
            ttk.Radiobutton(box, text='Start the quest with these levels (the empty level 1 becomes the first)', value='blank',
                            variable=self.target, command=lambda: setattr(p, 'target', 'blank')).pack(anchor='w')
        ttk.Radiobutton(box, text=f'After the {s.levels} level{"s" if s.levels != 1 else ""} already in the quest', value='after',
                        variable=self.target, command=lambda: setattr(p, 'target', 'after')).pack(anchor='w')
        self.h('What you get')
        for i, sp in enumerate(self.specs):
            st = self.results[i].stats if i < len(self.results) and self.results[i] else {}
            diff = worldgen.difficulty_for(p.ramp, i / (len(self.specs) - 1) if len(self.specs) > 1 else 0)
            boss = self.boss_for(i)
            text = (f'{sp["name"]}: {THEME_NAMES.get(sp["theme"], sp["theme"]).lower()}, {diff}, {st.get("creatures", "?")} creatures'
                    + (f', and {boss["name"]} at the end' if boss else ''))
            ttk.Label(self.page, text=f'{i + 1}.  {text}', wraplength=px(480), justify='left').pack(anchor='w', padx=px(22), pady=1)
        self.h('Afterwards')
        self.switch('Show me the new levels on the World page', 'open', store=p, refresh=False)
        self.switch('Play the first one', 'play', 'The game starts on the first new level.', store=p, refresh=False)

    # ── making it ───────────────────────────────────────────────────────────
    def close(self, value):
        for j in (self._job, self._gen):
            if j is not None:
                try:
                    self.after_cancel(j)
                except tk.TclError:
                    pass
        super().close(value)

    def create(self):
        s, p = self.s, self.s.project
        q = self.p
        for i, sp in enumerate(self.specs):
            if q.stories and len(wrap_story(sp['story'])) > 15:
                ui.inform(self, 'Too much story', f'The story before level {i + 1} is longer than a page (15 lines). Shorten it a little.')
                self.go(2)
                return
        for text, what in ((self.opening_text, 'opening'), (self.ending_text, 'ending')):
            if len(wrap_story(text)) > 15:
                ui.inform(self, 'Too much story', f'The {what} is longer than a page (15 lines). Shorten it a little.')
                self.go(2)
                return
        # make every level again from the settings now (what the pictures showed), so nothing is stale
        try:
            made = [worldgen.generate(p, self.params_for(i)) for i in range(len(self.specs))]
        except Exception as e:                                       # noqa: BLE001
            ui.inform(self, 'Could not make the quest', f'{e}\n\nChange something, or roll a level again.')
            return
        reuse = q.target == 'blank' and self.blank
        first = 1 if reuse else p.levels + 1
        numbers = [first + i for i in range(len(made))]
        scopes = ['quest', 'texts']
        for n in numbers:
            scopes += [('map', n), ('script', n), ('shops', n)]
        with s.edit('Make a whole quest', *dict.fromkeys(scopes)):
            for i, (n, r) in enumerate(zip(numbers, made)):
                lines = wrap_story(self.specs[i]['story']) if q.stories and self.specs[i]['story'].strip() else []
                levels.put_generated(s, n, r, self.specs[i]['name'], lines, new=not (reuse and i == 0))
            if reuse:
                if q.title.strip():
                    p.quest['title'] = q.title.strip()
                if q.author.strip():
                    p.quest['author'] = q.author.strip()
                p.quest['first_level'] = 1
            for number, text, on in ((0, self.opening_text, q.opening), (8, self.ending_text, q.ending)):
                if on and text.strip():
                    if not storytext.set_lines(p, number, wrap_story(text)):
                        storytext.add_story(p, wrap_story(text), number=number)
        done, want_open, play = self.on_done, q.open, q.play
        super().close(numbers[0])
        if done and want_open:
            done(numbers[0])
        if play:
            s.autosave()
            self.app.play(numbers[0])


def open_quest_wizard(app, on_done=None):
    return QuestWizard(app, on_done).run()
