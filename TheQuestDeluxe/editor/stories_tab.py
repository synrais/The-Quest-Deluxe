"""The Stories tab: the story screens. stories.txt holds each as `number lines` followed by that many
lines of text. Story 0 opens a new game, 1 follows character creation, the numbers a level's STORIES
setting names show before it, and 8 and 9 end the game (9 after a good ending). The preview is the
game's own story page."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk, messagebox

import pygame

from .art import photo

HEAD = re.compile(r'^(-?\d+) (\d+)$')
SPECIAL = {0: 'opens a new game', 1: 'after character creation', 8: 'the ending', 9: 'the good ending (after 8)'}


class Story:
    def __init__(self, number, lines, raw=None):
        self.number, self.lines, self.raw = number, lines, raw
        self._as_read = (number, list(lines))

    def text(self) -> str:
        if self.raw is not None and (self.number, self.lines) == self._as_read:
            return self.raw
        return '\n'.join([f'{self.number} {len(self.lines)}'] + self.lines)


def parse(text: str) -> list:
    out, lines, i = [], text.split('\n'), 0
    while i < len(lines):
        m = HEAD.match(lines[i])
        if m and i + int(m.group(2)) < len(lines) + 1:
            n = int(m.group(2))
            body = lines[i + 1:i + 1 + n]
            out.append(Story(int(m.group(1)), body, raw='\n'.join(lines[i:i + 1 + n])))
            i += 1 + n
        else:
            out.append(lines[i])
            i += 1
    return out


def write(items) -> str:
    return '\n'.join(it.text() if isinstance(it, Story) else it for it in items)


class StoriesTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.items, self.story = [], None
        self._renderer = None
        left = ttk.Frame(self, padding=4)
        left.pack(side='left', fill='y')
        self.list = ttk.Treeview(left, show='tree', selectmode='browse', height=22)
        self.list.column('#0', width=420)
        self.list.pack(fill='y', expand=True)
        self.list.bind('<<TreeviewSelect>>', lambda e: self._select())
        b = ttk.Frame(left)
        b.pack(fill='x', pady=4)
        ttk.Button(b, text='New story', command=self.new).pack(side='left')
        ttk.Button(b, text='Delete', command=self.delete).pack(side='left', padx=4)
        right = ttk.Frame(self, padding=4)
        right.pack(side='left', fill='both', expand=True)
        row = ttk.Frame(right)
        row.pack(fill='x')
        ttk.Label(row, text='Number').pack(side='left')
        self.number = tk.StringVar()
        ttk.Spinbox(row, from_=0, to=999, width=5, textvariable=self.number).pack(side='left', padx=4)
        ttk.Button(row, text='Apply', command=self.apply).pack(side='left', padx=8)
        self.info = ttk.Label(row, text='', foreground='#555')
        self.info.pack(side='left', padx=8)
        self.text = tk.Text(right, width=78, height=16, font=('Courier', 10), undo=True, wrap='none')
        self.text.pack(anchor='w', pady=4)
        self.text.bind('<KeyRelease>', lambda e: self._typed())
        ttk.Label(right, text='Up to 15 lines of about 75 letters. Level settings (the Map tab) say which '
                              'stories show before each level.', foreground='#555').pack(anchor='w')
        self.preview = ttk.Label(right)
        self.preview.pack(anchor='w', pady=6)

    def load(self):
        self.items = parse(self.app.project.texts['stories'])
        self.story = None
        self.fill()
        first = next((it for it in self.items if isinstance(it, Story)), None)
        if first:
            self.show(first)

    def used(self):
        """Which story numbers are shown where."""
        p, out = self.app.project, dict(SPECIAL)
        for n in range(1, p.levels + 1):
            for s in p.constant(n, 'STORIES', []) or []:
                out[s] = f'before level {n}'
        return out

    def fill(self):
        t, used = self.list, self.used()
        t.delete(*t.get_children())
        for i, it in enumerate(self.items):
            if isinstance(it, Story):
                first = it.lines[0][:28] if it.lines else ''
                t.insert('', 'end', iid=str(i), text=f'{it.number}  ({used.get(it.number, "not shown")})  {first}')
        if self.story in self.items:
            t.selection_set(str(self.items.index(self.story)))

    def _select(self):
        sel = self.list.selection()
        if sel and self.items[int(sel[0])] is not self.story:
            self.show(self.items[int(sel[0])])

    def show(self, st):
        self.story = st
        self.number.set(str(st.number))
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', '\n'.join(st.lines))
        self._count()
        self._preview()

    def _typed(self):
        """The text applies as it is typed (the number with Apply)."""
        self._count()
        st = self.story
        lines = self.text.get('1.0', 'end-1c').split('\n')
        if st is not None and lines != st.lines:
            st.lines = lines
            self._save()
            self._preview()

    def _count(self):
        lines = self.text.get('1.0', 'end-1c').split('\n')
        longest = max((len(s) for s in lines), default=0)
        bad = len(lines) > 15 or longest > 78
        self.info.config(text=f'{len(lines)} lines, the longest {longest} letters', foreground='#a00' if bad else '#555')

    def apply(self):
        st = self.story
        if st is None:
            return
        try:
            number = int(self.number.get())
        except ValueError:
            messagebox.showerror('Story', 'The number is a number.')
            return
        if any(isinstance(it, Story) and it is not st and it.number == number for it in self.items):
            messagebox.showerror('Story', f'There is already a story {number}.')
            return
        st.number = number
        st.lines = self.text.get('1.0', 'end-1c').split('\n')
        self._save()
        self.fill()
        self._preview()

    def _save(self):
        self.app.project.texts['stories'] = write(self.items)
        self.app.project.touch('stories')
        self.app.changed()

    def new(self):
        taken = {it.number for it in self.items if isinstance(it, Story)}
        n = next(v for v in range(2, 1000) if v not in taken and v not in (8, 9))
        st = Story(n, ['Once upon a time...'])
        if self.items and self.items[-1] != '':
            self.items.append(st)
        else:
            self.items.insert(max(0, len(self.items) - 1), st)
        self._save()
        self.story = st
        self.fill()
        self.show(st)

    def delete(self):
        st = self.story
        if st is None or not messagebox.askyesno('Delete', f'Delete story {st.number}?'):
            return
        self.items.remove(st)
        self.story = None
        self._save()
        self.fill()

    # ── preview: the game's own story page ──────────────────────────────────
    def _preview(self):
        if self.story is None:
            return
        r = self._game_renderer()
        from deluxe.ui import TextScreen
        screen = pygame.Surface((640, 480))
        TextScreen('', '\n'.join(self.story.lines)).draw(r, screen)
        self._img = photo(pygame.transform.smoothscale(screen, (480, 360)))
        self.preview.config(image=self._img)

    def _game_renderer(self):
        root = self.app.project.root
        if self._renderer is None or self._renderer[0] != root:
            from deluxe.pack import Pack, PackSource
            from deluxe.render import Renderer
            if pygame.display.get_surface() is None:
                pygame.display.set_mode((640, 480))       # the dummy video driver: nothing shows
            pack = Pack(root)
            self._renderer = (root, Renderer(pygame.Surface((640, 480)), PackSource(pack), pack))
        return self._renderer[1]
