"""The Story & talk page: the story screens before levels, what people say, and the questionnaire."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pygame

from editor import dialogue
from editor.art import photo
from engine.events import talk_text

from .. import levelmeta, storytext, theme, ui
from ..gallery import Entry, Gallery
from ..theme import C, px
from .base import Page

TABS = [('stories', 'Stories'), ('talk', 'What people say'), ('quiz', 'The questionnaire')]


def make_text(parent, height=10, width=60):
    t = tk.Text(parent, height=height, width=width, wrap='none', bg=C['input'], fg=C['text'], insertbackground=C['text'], relief='flat',
                highlightthickness=1, highlightbackground=C['line'], highlightcolor=C['accent'], font=('Courier', 11), padx=10, pady=8,
                undo=False, selectbackground=C['accent'], selectforeground=C['accent_text'])
    return t


class StoryPage(Page):
    key = 'story'
    title = 'Story & talk'
    icon = 'book'

    def build(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=px(20), pady=(px(14), px(6)))
        ttk.Label(top, text='Story & talk', style='H1.TLabel').pack(side='left')
        self.seg = ui.Segmented(top, TABS, self._tab, 'stories')
        self.seg.pack(side='left', padx=px(24), pady=(px(8), 0))
        self.holder = ttk.Frame(self)
        self.holder.pack(fill='both', expand=True)
        self.views = {'stories': StoriesView(self.holder, self), 'talk': TalkView(self.holder, self), 'quiz': QuizView(self.holder, self)}
        self.current = None
        self._tab('stories')

    def _tab(self, key, **where):
        if self.current is not None:
            self.views[self.current].pack_forget()
        self.current = key
        self.seg.choose(key, run=False)
        self.views[key].pack(fill='both', expand=True)
        self.views[key].show(**where)

    def on_show(self, tab=None, **where):
        self._tab(tab or self.current or 'stories', **where)

    def reload(self):
        for v in self.views.values():
            v.show()

    def search(self, q):
        out = []
        for st in storytext.stories(self.s.project):
            first = (st.lines[0] if st.lines else '')
            if q in first.lower() or q == str(st.number) or q == f'story {st.number}':
                out.append((f'Story {st.number}', first[:60], 'book', lambda n=st.number: self.app.go('story', tab='stories', select=n)))
        return out


# ── stories ──────────────────────────────────────────────────────────────────
class StoriesView(ttk.Frame):
    def __init__(self, master, page):
        super().__init__(master)
        self.page, self.s = page, page.s
        self.number = None
        self._loading = False
        self._job = None
        left = ttk.Frame(self, width=px(300))
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        ui.vsep(self).pack(side='left', fill='y')
        head = ttk.Frame(left)
        head.pack(fill='x', padx=px(14), pady=(px(6), px(6)))
        ttk.Label(head, text='Story screens', style='H3.TLabel').pack(side='left')
        ui.button(head, 'New', self.new, 'plus', 'Accent.TButton', 'Write a new story').pack(side='right')
        self.list = Gallery(left, on_select=self._pick, list_mode=True)
        self.list.pack(fill='both', expand=True)
        right = ttk.Frame(self)
        right.pack(side='left', fill='both', expand=True, padx=px(20))
        self.title = ttk.Label(right, text='', style='H2.TLabel')
        self.title.pack(anchor='w', pady=(px(8), 0))
        self.role = ttk.Label(right, text='', style='Dim.TLabel')
        self.role.pack(anchor='w')
        row = ttk.Frame(right)
        row.pack(fill='x', pady=(px(8), px(4)))
        ttk.Label(row, text='Shown before').pack(side='left')
        self.where = ttk.Combobox(row, state='readonly', width=24)
        self.where.pack(side='left', padx=px(8))
        self.where.bind('<<ComboboxSelected>>', lambda e: self._where())
        ui.button(row, 'Fit to the page', self.fit, 'list', 'TButton', 'Wrap the words to the width of the story page').pack(side='left', padx=px(10))
        ui.button(row, '', self.delete, 'trash', 'Tool.TButton', 'Delete this story').pack(side='left')
        cols = ttk.Frame(right)
        cols.pack(fill='both', expand=True)
        self.text = make_text(cols, height=16, width=80)
        self.text.pack(side='left', anchor='n')
        self.text.bind('<KeyRelease>', lambda e: self._typed())
        side = ttk.Frame(cols)
        side.pack(side='left', anchor='n', padx=px(16))
        self.preview = ttk.Label(side)
        self.preview.pack(anchor='nw')
        self.info = ttk.Label(side, text='', style='Dim.TLabel')
        self.info.pack(anchor='w', pady=(px(6), 0))
        self._renderer = None
        self.empty = ui.EmptyState(self, 'book', 'No stories yet.', 'Write a story', self.new)

    # list ----------------------------------------------------------------------
    def show(self, select=None, **where):
        self.fill()
        if select is not None and storytext.get(self.s.project, select):
            self.number = select
        elif self.number is None or storytext.get(self.s.project, self.number) is None:
            first = storytext.stories(self.s.project)
            self.number = first[0].number if first else None
        self.list.select(self.number, scroll=True)
        self.load()

    def fill(self):
        used = storytext.used_by(self.s.project)
        entries = []
        for st in storytext.stories(self.s.project):
            first = (st.lines[0] if st.lines else '').strip()
            entries.append(Entry(st.number, f'Story {st.number}', f'{used.get(st.number, "not shown anywhere")}  ·  {first[:34]}'))
        self.list.set_items(entries)
        self.list.select(self.number, scroll=False)

    def _pick(self, number):
        self.number = number
        self.load()

    def load(self):
        st = storytext.get(self.s.project, self.number) if self.number is not None else None
        if st is None:
            self.text.pack_forget()
            return
        self._loading = True
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', '\n'.join(st.lines))
        self._loading = False
        self.title.configure(text=f'Story {st.number}')
        used = storytext.used_by(self.s.project)
        self.role.configure(text=storytext.RESERVED.get(st.number, 'Shown before a level you choose below.'))
        n = self.s.levels
        opts = ['nowhere'] + [f'before level {k}  ({levelmeta.title(self.s, k)})' for k in range(1, n + 1)]
        self.where.configure(values=opts, state='disabled' if st.number in storytext.RESERVED else 'readonly')
        cur = next((k for k in range(1, n + 1) if st.number in (levelmeta.get(self.s, k, 'STORIES', []) or [])), None)
        self.where.set(opts[cur] if cur else opts[0])
        self._counts()
        self._draw()

    def _lines(self):
        return self.text.get('1.0', 'end-1c').split('\n')

    def _counts(self):
        lines = self._lines()
        widest = max((len(s) for s in lines), default=0)
        bad = len(lines) > storytext.PAGE_LINES or widest > storytext.PAGE_WIDTH
        self.info.configure(text=f'{len(lines)} of {storytext.PAGE_LINES} lines · widest {widest} of {storytext.PAGE_WIDTH} letters',
                            foreground=C['bad'] if bad else C['dim'])

    def _typed(self):
        if self._loading or self.number is None:
            return
        lines = self._lines()
        st = storytext.get(self.s.project, self.number)
        if st is None or lines == st.lines:
            return
        with self.s.edit(f'Edit story {self.number}', 'texts', merge=f'story:{self.number}', source=self):
            storytext.set_lines(self.s.project, self.number, lines)
        self._counts()
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(250, self._redraw)

    def _redraw(self):
        self._job = None
        self._draw()
        self.fill()

    def fit(self):
        lines = storytext.wrap('\n'.join(self._lines()), 72)
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', '\n'.join(lines))
        self._typed()

    def _where(self):
        st = storytext.get(self.s.project, self.number)
        if st is None:
            return
        choice = self.where.current()
        scopes = [('script', k) for k in range(1, self.s.levels + 1)]
        with self.s.edit(f'Show story {st.number} before a level', *scopes, source=self):
            for k in range(1, self.s.levels + 1):
                have = list(levelmeta.get(self.s, k, 'STORIES', []) or [])
                if st.number in have:
                    have.remove(st.number)
                    levelmeta.raw_put(self.s.project, k, 'STORIES', have)
            if choice > 0:
                have = list(levelmeta.get(self.s, choice, 'STORIES', []) or [])
                have.append(st.number)
                levelmeta.raw_put(self.s.project, choice, 'STORIES', have)
        self.fill()
        self.role.configure(text='Shown before a level you choose below.')

    def new(self):
        lines = ['Once upon a time...']
        with self.s.edit('Write a new story', 'texts', source=self):
            n = storytext.add_story(self.s.project, lines)
        self.number = n
        self.fill()
        self.list.select(n)
        self.load()
        self.text.focus_set()
        self.text.tag_add('sel', '1.0', 'end')

    def delete(self):
        st = storytext.get(self.s.project, self.number)
        if st is None:
            return
        if st.number in storytext.RESERVED:
            ui.inform(self, 'Story', f'Story {st.number} is part of the game ({storytext.RESERVED[st.number]}), so it stays. You can change its words.')
            return
        if not ui.confirm(self, 'Delete a story', f'Delete story {st.number}?\n\nYou can bring it back with Undo (Ctrl+Z).', 'Delete', danger=True):
            return
        scopes = ['texts'] + [('script', k) for k in range(1, self.s.levels + 1)]
        with self.s.edit(f'Delete story {st.number}', *scopes, source=self):
            storytext.delete(self.s.project, st.number)
            for k in range(1, self.s.levels + 1):
                have = list(levelmeta.get(self.s, k, 'STORIES', []) or [])
                if st.number in have:
                    have.remove(st.number)
                    levelmeta.raw_put(self.s.project, k, 'STORIES', have)
        self.number = None
        self.show()

    # the game's own story page ------------------------------------------------------
    def _draw(self):
        if self.number is None:
            return
        try:
            r = self._game_renderer()
            from engine.ui import TextScreen
            screen = pygame.Surface((640, 480))
            TextScreen('', '\n'.join(self._lines())).draw(r, screen)
            self._img = photo(pygame.transform.smoothscale(screen, (px(400), px(300))))
            self.preview.configure(image=self._img)
        except Exception as e:                                        # noqa: BLE001
            self.preview.configure(image='', text=f'(no preview: {e})')

    def _game_renderer(self):
        root = self.s.project.root
        if self._renderer is None or self._renderer[0] != root:
            from engine.pack import Pack, PackSource
            from engine.render import Renderer
            pack = Pack(root)
            self._renderer = (root, Renderer(pygame.Surface((640, 480)), PackSource(pack), pack))
        return self._renderer[1]


# ── what people say ──────────────────────────────────────────────────────────
class TalkView(ttk.Frame):
    def __init__(self, master, page):
        super().__init__(master)
        self.page, self.s = page, page.s
        self.person = None
        self.level = 0
        left = ttk.Frame(self, width=px(300))
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        ui.vsep(self).pack(side='left', fill='y')
        ttk.Label(left, text='People', style='H3.TLabel').pack(anchor='w', padx=px(14), pady=(px(6), px(4)))
        self.list = Gallery(left, on_select=self._pick, list_mode=True)
        self.list.pack(fill='both', expand=True)
        right = ttk.Frame(self)
        right.pack(side='left', fill='both', expand=True, padx=px(20))
        self.title = ttk.Label(right, text='', style='H2.TLabel')
        self.title.pack(anchor='w', pady=(px(8), 0))
        bar = ttk.Frame(right)
        bar.pack(fill='x', pady=px(6))
        ttk.Label(bar, text='On level').pack(side='left')
        self.levels = ttk.Combobox(bar, state='readonly', width=22)
        self.levels.pack(side='left', padx=px(8))
        self.levels.bind('<<ComboboxSelected>>', lambda e: self._level())
        ui.button(bar, 'Add chit-chat', lambda: self.add('chat'), 'plus', 'TButton', 'Something they say at random when the hero walks into them').pack(side='left', padx=px(8))
        ui.button(bar, 'Add a line for an event', lambda: self.add('event'), 'bolt', 'TButton', 'Said when an event calls say(n)').pack(side='left')
        self.scroll = ui.Scrolled(right)
        self.scroll.pack(fill='both', expand=True)
        self.preview = ttk.Label(right)
        self.preview.pack(anchor='w', pady=px(6))
        self.note = ttk.Label(right, text='Chit-chat (numbers 1 to 3) is picked at random when the hero walks into someone. Lines from 10 up are said '
                              'when an event calls say(number). "Every level" lines are heard on any level. About 70 letters fit the strip.',
                              style='Faint.TLabel', wraplength=px(760), justify='left')
        self.note.pack(anchor='w', pady=(0, px(8)))
        self._src = None

    def items(self):
        return dialogue.parse(self.s.project.texts['talk'])

    def people(self):
        """People that talk or could: every non-monster creature, and anyone with a line."""
        names = {c['id']: c.get('name', '') for c in self.s.rows('creatures')}
        have = {e.person for e in dialogue.entries(self.items())}
        return [(v, names.get(v, '')) for v in sorted(set(v for v in names if -100 < v < 0 and v != -5) | have, key=lambda v: (v > 0, -v if v < 0 else v))]

    def show(self, person=None, **where):
        entries = []
        count = {}
        for e in dialogue.entries(self.items()):
            count[e.person] = count.get(e.person, 0) + 1
        pic = self.s.pictures
        for v, name in self.people():
            entries.append(Entry(v, name or f'#{v}', f'{count.get(v, 0)} lines', pic.thumb('mon', v, 36, 'raised')))
        self.list.set_items(entries)
        if person is not None:
            self.person = person
        if self.person is None and entries:
            self.person = entries[0].key
        self.list.select(self.person, scroll=True)
        n = self.s.levels
        self.levels.configure(values=['every level'] + [f'level {k}  ({levelmeta.title(self.s, k)})' for k in range(1, n + 1)])
        self.levels.set('every level' if self.level == 0 else f'level {self.level}  ({levelmeta.title(self.s, self.level)})')
        self.draw()

    def _pick(self, person):
        self.person = person
        self.draw()

    def _level(self):
        self.level = self.levels.current()
        self.draw()

    def draw(self):
        for w in self.scroll.body.winfo_children():
            w.destroy()
        if self.person is None:
            return
        name = {v: n for v, n in self.people()}.get(self.person, '')
        self.title.configure(text=f'{name or "#" + str(self.person)} on {"every level" if self.level == 0 else "level " + str(self.level)}')
        mine = [e for e in dialogue.entries(self.items()) if e.person == self.person and e.level == self.level]
        if not mine:
            ttk.Label(self.scroll.body, text='Nothing said here yet. Add some chit-chat or a line for an event.', style='Dim.TLabel',
                      padding=px(14)).pack(anchor='w')
        for e in sorted(mine, key=lambda e: e.number):
            self._card(e)
        self._strip(mine[0] if mine else None)

    def _card(self, e):
        card = ui.Card(self.scroll.body, pad=10)
        card.pack(fill='x', pady=px(4), padx=(0, px(6)))
        f = card.inner
        head = ttk.Frame(f, style='Raised.TFrame')
        head.pack(fill='x')
        kind = 'chit-chat' if e.number <= 3 else f'said by say({e.number})'
        ttk.Label(head, text=f'Line {e.number}', style='H3.TLabel', background=C['raised']).pack(side='left')
        ttk.Label(head, text=kind, style='Raised.Dim.TLabel').pack(side='left', padx=px(10))
        ui.button(head, '', lambda e=e: self.delete(e), 'trash', 'Tool.TButton', 'Delete this line').pack(side='right')
        ui.button(head, '', lambda e=e: self._strip(e), 'eye', 'Tool.TButton', 'See it as the game shows it').pack(side='right')
        vars_ = []
        for i, text in enumerate((e.line1, e.line2 or '')):
            r = ttk.Frame(f, style='Raised.TFrame')
            r.pack(fill='x', pady=2)
            ttk.Label(r, text='First line' if i == 0 else 'Second line', style='Raised.TLabel', width=11).pack(side='left')
            v = tk.StringVar(value=text)
            ent = ttk.Entry(r, textvariable=v, width=74)
            ent.pack(side='left', fill='x', expand=True)
            count = ttk.Label(r, text='', style='Raised.Dim.TLabel', width=11)
            count.pack(side='left', padx=px(6))
            v.trace_add('write', lambda *a, v=v, c=count: c.configure(text=f'{len(v.get())} letters', foreground=C['bad'] if len(v.get()) > 70 else C['dim']))
            for ev in ('<Return>', '<FocusOut>'):
                ent.bind(ev, lambda e_, e=e, vs=vars_: self._edit(e, vs))
            ent.bind('<FocusIn>', lambda e_, e=e: self._strip(e))
            vars_.append(v)
            count.configure(text=f'{len(text)} letters')

    def _edit(self, e, vars_):
        l1, l2 = vars_[0].get(), vars_[1].get() or None
        if (l1, l2) == (e.line1, e.line2):
            return
        if any(c in l1 + (l2 or '') for c in '";'):
            self.page.app.say('A line may not contain " or ; because they end lines in the file.', 'warn')
            return
        self._write(lambda items: self._find(items, e, lambda x: setattr(x, 'line1', l1) or setattr(x, 'line2', l2)), 'Change what someone says', merge=f'talk:{e.key}')
        e.line1, e.line2 = l1, l2
        self._strip(e)

    @staticmethod
    def _find(items, e, fn):
        for it in items:
            if isinstance(it, dialogue.Entry) and it.key == e.key:
                fn(it)
                return True
        return False

    def _write(self, fn, label, merge=None):
        items = self.items()
        fn(items)
        with self.s.edit(label, 'texts', merge=merge, source=self):
            self.s.project.texts['talk'] = dialogue.write(items)
            self.s.project.touch('talk')

    def add(self, kind):
        if self.person is None:
            return
        items = self.items()
        taken = {e.number for e in dialogue.entries(items) if e.level == self.level and e.person == self.person}
        if kind == 'chat':
            free = [n for n in (1, 2, 3) if n not in taken]
            if not free:
                self.page.app.say('A person has three chit-chat lines at most (1 to 3).', 'warn')
                return
            number = free[0]
        else:
            number = next(n for n in range(10, 1000) if n not in taken)
        e = dialogue.Entry(self.level, self.person, number, 'Hello there.')
        at = max((i for i, it in enumerate(items) if isinstance(it, dialogue.Entry) and it.level == self.level and it.person == self.person),
                 default=len(items) - 1)
        items.insert(at + 1, e)
        with self.s.edit('Add a line of talk', 'texts', source=self):
            self.s.project.texts['talk'] = dialogue.write(items)
            self.s.project.touch('talk')
        self.show()
        self._strip(e)

    def delete(self, e):
        if not ui.confirm(self, 'Delete a line', f'Delete "{e.line1}"?\n\nYou can bring it back with Undo (Ctrl+Z).', 'Delete', danger=True):
            return
        self._write(lambda items: [items.remove(it) for it in list(items) if isinstance(it, dialogue.Entry) and it.key == e.key], 'Delete a line of talk')
        self.show()

    def _strip(self, e):
        s = pygame.Surface((640, 70))
        s.fill((0, 0, 0))
        got = talk_text(self.s.project.texts['talk'], e.level or 1, e.person, e.number) if e else None
        if got is None:
            font = pygame.font.Font(None, 20)
            s.blit(font.render('(the game would not find this line)' if e else '', True, (255, 80, 80)), (8, 8))
        else:
            from engine.bgi import BGI
            from engine.pack import Pack, PackSource
            if self._src is None or self._src[0] != self.s.project.root:
                self._src = (self.s.project.root, PackSource(Pack(self.s.project.root)))
            g = BGI(s, self._src[1])
            g.settextstyle(6, 0, 1)
            g.setcolor(15)
            line1, line2, x = got
            g.outtextxy(x, 3, line1)
            g.outtextxy(x + 1, 33, line2)
        self._img = photo(pygame.transform.scale(s, (px(800), px(88))))
        self.preview.configure(image=self._img)


# ── the questionnaire ────────────────────────────────────────────────────────
class QuizView(ttk.Frame):
    def __init__(self, master, page):
        super().__init__(master)
        self.page, self.s = page, page.s
        self._loading = False
        ttk.Label(self, text='The questions a new hero answers to find his class: 8 questions of 9 lines. A score is 1000 (Knight), 100, 10 or 1 '
                  '(Monk), or "class: points" (5: 2) for a pack\'s own class.', style='Dim.TLabel', wraplength=px(900), justify='left').pack(
            anchor='w', padx=px(20), pady=(px(8), px(4)))
        self.text = make_text(self, height=24, width=100)
        self.text.configure(font=('Courier', 10), wrap='none')
        self.text.pack(fill='both', expand=True, padx=px(20), pady=px(6))
        self.text.bind('<KeyRelease>', lambda e: self._typed())
        self.info = ttk.Label(self, text='', style='Dim.TLabel')
        self.info.pack(anchor='w', padx=px(20), pady=(0, px(8)))

    def show(self, **where):
        self._loading = True
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', self.s.project.texts['questions'])
        self._loading = False
        self._check()

    def _typed(self):
        if self._loading:
            return
        text = self.text.get('1.0', 'end-1c')
        if text == self.s.project.texts['questions']:
            return
        with self.s.edit('Edit the questionnaire', 'texts', merge='quiz', source=self):
            self.s.project.texts['questions'] = text
            self.s.project.touch('questions')
        self._check()

    def _check(self):
        n = len(self.text.get('1.0', 'end-1c').splitlines())
        ok = n >= 72
        self.info.configure(text=f'{n} lines' + ('' if ok else f' (the questionnaire needs 72: 8 x 9)'), foreground=C['ok'] if ok else C['bad'])
