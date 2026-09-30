"""The Dialogue tab: what people say. Each line belongs to a level (0 = every level), a person (their
creature number) and a number: 1-3 are chit-chat picked at random when the hero walks into them,
10 and up are said when a script calls say(n). The preview is the game's own reading of the file."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

import pygame

from deluxe.events import talk_text
from . import dialogue
from .art import photo


class DialogueTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.items = []
        self.entry = None
        self._build()

    def _build(self):
        top = ttk.Frame(self, padding=4)
        top.pack(fill='x')
        ttk.Label(top, text='Level').pack(side='left')
        self.f_level = ttk.Combobox(top, state='readonly', width=12)
        self.f_level.pack(side='left', padx=4)
        ttk.Label(top, text='Person').pack(side='left')
        self.f_person = ttk.Combobox(top, state='readonly', width=26)
        self.f_person.pack(side='left', padx=4)
        ttk.Label(top, text='Find').pack(side='left')
        self.find = tk.StringVar()
        ttk.Entry(top, textvariable=self.find, width=24).pack(side='left', padx=4)
        for w in (self.f_level, self.f_person):
            w.bind('<<ComboboxSelected>>', lambda e: self.fill())
        self.find.trace_add('write', lambda *a: self.fill())
        ttk.Button(top, text='New line', command=self.new).pack(side='left', padx=(16, 2))
        ttk.Button(top, text='Delete', command=self.delete).pack(side='left')

        body = ttk.Panedwindow(self, orient='vertical')
        body.pack(fill='both', expand=True)
        lst = ttk.Frame(body)
        self.list = ttk.Treeview(lst, columns=('level', 'person', 'n', 'text'), show='headings', height=14)
        for c, label, w in (('level', 'Level', 60), ('person', 'Person', 200), ('n', 'No.', 50), ('text', 'Says', 800)):
            self.list.heading(c, text=label)
            self.list.column(c, width=w, stretch=c == 'text')
        sb = ttk.Scrollbar(lst, orient='vertical', command=self.list.yview)
        self.list.configure(yscrollcommand=sb.set)
        self.list.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.list.bind('<<TreeviewSelect>>', lambda e: self._select())
        body.add(lst, weight=3)

        form = ttk.Frame(body, padding=8)
        body.add(form, weight=2)
        row = ttk.Frame(form)
        row.pack(fill='x')
        ttk.Label(row, text='Level').pack(side='left')
        self.level = tk.StringVar()
        ttk.Spinbox(row, from_=0, to=99, width=4, textvariable=self.level).pack(side='left', padx=4)
        ttk.Label(row, text='Person').pack(side='left', padx=(10, 0))
        self.person = ttk.Combobox(row, width=30)
        self.person.pack(side='left', padx=4)
        ttk.Label(row, text='Number').pack(side='left', padx=(10, 0))
        self.number = tk.StringVar()
        ttk.Spinbox(row, from_=1, to=999, width=5, textvariable=self.number).pack(side='left', padx=4)
        ttk.Button(row, text='Apply', command=self.apply).pack(side='left', padx=10)
        self.lines = []
        for n in (1, 2):
            r = ttk.Frame(form)
            r.pack(fill='x', pady=2)
            ttk.Label(r, text=f'Line {n}', width=7).pack(side='left')
            v = tk.StringVar()
            e = ttk.Entry(r, textvariable=v, width=90)
            e.pack(side='left')
            count = ttk.Label(r, text='', width=12)
            count.pack(side='left', padx=6)
            v.trace_add('write', lambda *a, v=v, c=count: self._count(v, c))
            e.bind('<Return>', lambda e: self.apply())
            e.bind('<KeyRelease>', lambda e: self._typed())
            self.lines.append(v)
        ttk.Label(form, text='How it shows in the game:').pack(anchor='w', pady=(8, 2))
        self.preview = ttk.Label(form)
        self.preview.pack(anchor='w')
        ttk.Label(form, text='Numbers 1-3 are chit-chat (picked at random); 10 and up are said from scripts '
                             'with say(n). Level 0 lines are heard on every level. Keep lines to about 70 '
                             'characters to fit the strip.', foreground='#555').pack(anchor='w', pady=6)

    # ── data ────────────────────────────────────────────────────────────────
    def people(self):
        return {c['id']: c.get('name', '') for c in self.app.project.tables['creatures']}

    def person_label(self, v):
        return f'{v} {self.people().get(v, "")}'.strip()

    def load(self):
        self.items = dialogue.parse(self.app.project.texts['talk'])
        levels = sorted({e.level for e in dialogue.entries(self.items)} | set(range(0, self.app.project.levels + 1)))
        self.f_level.config(values=['All'] + [f'{n} ' + ('(every level)' if n == 0 else '') for n in levels])
        self.f_level.set('All')
        who = sorted({e.person for e in dialogue.entries(self.items)})
        self.f_person.config(values=['All'] + [self.person_label(v) for v in who])
        self.f_person.set('All')
        self.person.config(values=[self.person_label(v) for v in sorted(self.people())])
        self.entry = None
        self.fill()

    def save_text(self):
        self.app.project.texts['talk'] = dialogue.write(self.items)
        self.app.project.touch('talk')
        self.app.changed()

    def fill(self):
        t = self.list
        t.delete(*t.get_children())
        lv, who, want = self.f_level.get(), self.f_person.get(), self.find.get().strip().lower()
        for i, e in enumerate(self.items):
            if not isinstance(e, dialogue.Entry):
                continue
            if lv not in ('', 'All') and e.level != int(lv.split()[0]):
                continue
            if who not in ('', 'All') and e.person != int(who.split()[0]):
                continue
            said = e.line1 + (' / ' + e.line2 if e.line2 is not None else '')
            if want and want not in said.lower():
                continue
            t.insert('', 'end', iid=str(i), values=(e.level, self.person_label(e.person), e.number, said))
        if self.entry is not None and self.entry in self.items:
            iid = str(self.items.index(self.entry))
            if t.exists(iid):
                t.selection_set(iid)

    def _select(self):
        sel = self.list.selection()
        if sel:
            self.show(self.items[int(sel[0])])

    def show(self, e):
        self.entry = e
        self.level.set(str(e.level))
        self.person.set(self.person_label(e.person))
        self.number.set(str(e.number))
        self.lines[0].set(e.line1)
        self.lines[1].set(e.line2 or '')
        self._preview()

    def _typed(self):
        """The lines apply as they are typed (the level, person and number with Apply)."""
        e = self.entry
        l1, l2 = self.lines[0].get(), self.lines[1].get() or None
        if e is None or (l1, l2) == (e.line1, e.line2) or any(c in l1 + (l2 or '') for c in '";'):
            return
        e.line1, e.line2 = l1, l2
        self.save_text()
        iid = str(self.items.index(e))
        if self.list.exists(iid):
            self.list.set(iid, 'text', l1 + (' / ' + l2 if l2 is not None else ''))
        self._preview()

    @staticmethod
    def _count(var, label):
        n = len(var.get())
        label.config(text=f'{n} letters', foreground='#a00' if n > 70 else '#555')

    def apply(self):
        e = self.entry
        if e is None:
            return
        try:
            level, number = int(self.level.get()), int(self.number.get())
            person = int(self.person.get().split()[0])
        except (ValueError, IndexError):
            messagebox.showerror('Dialogue', 'The level, person and number are numbers.')
            return
        l1, l2 = self.lines[0].get(), self.lines[1].get()
        if any(c in l1 + l2 for c in '";'):
            messagebox.showerror('Dialogue', 'A line may not contain " or ; (they end lines in the file).')
            return
        e.level, e.person, e.number, e.line1, e.line2 = level, person, number, l1, (l2 or None)
        self.save_text()
        self.fill()
        self._preview()

    def new(self):
        lv, who = self.f_level.get(), self.f_person.get()
        level = int(lv.split()[0]) if lv not in ('', 'All') else (self.entry.level if self.entry else 1)
        person = int(who.split()[0]) if who not in ('', 'All') else (self.entry.person if self.entry else -6)
        taken = {e.number for e in dialogue.entries(self.items) if e.level == level and e.person == person}
        number = next(n for n in range(10, 1000) if n not in taken)
        e = dialogue.Entry(level, person, number, 'Hello there.')
        # after that person's last line on that level, else at the end
        at = max((i for i, it in enumerate(self.items) if isinstance(it, dialogue.Entry) and it.level == level
                  and it.person == person), default=len(self.items) - 1)
        self.items.insert(at + 1, e)
        self.save_text()
        self.entry = e
        self.fill()
        self.show(e)

    def delete(self):
        e = self.entry
        if e is None or not messagebox.askyesno('Delete', f'Delete level {e.level}, person {e.person}, number '
                                                            f'{e.number}: "{e.line1}"?'):
            return
        self.items.remove(e)
        self.entry = None
        self.save_text()
        self.fill()

    # ── preview: the game's own reading of the file ─────────────────────────
    def _preview(self):
        e = self.entry
        s = pygame.Surface((640, 70))
        s.fill((0, 0, 0))
        got = talk_text(dialogue.write(self.items), e.level or 1, e.person, e.number) if e else None
        if got is None:
            font = pygame.font.Font(None, 20)
            s.blit(font.render('(the game would not find this line)', True, (255, 80, 80)), (8, 8))
        else:
            from deluxe.bgi import BGI
            from deluxe.pack import Pack, PackSource
            if getattr(self, '_src_root', None) != self.app.project.root:
                self._src = PackSource(Pack(self.app.project.root))
                self._src_root = self.app.project.root
            g = BGI(s, self._src)
            g.settextstyle(6, 0, 1)
            g.setcolor(15)
            line1, line2, x = got
            g.outtextxy(x, 3, line1)
            g.outtextxy(x + 1, 33, line2)
        self._img = photo(pygame.transform.scale(s, (960, 105)))
        self.preview.config(image=self._img)
