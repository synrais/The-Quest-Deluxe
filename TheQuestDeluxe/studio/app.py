"""The Studio window: sidebar of pages, top bar, status bar, Ctrl+K, and the open pack."""
from __future__ import annotations

import os
import sys
import time
import tkinter as tk
from tkinter import ttk

from . import icons, theme, ui
from .model import Session, load_settings, save_settings
from .theme import C, px

NAV = [
    ('home', 'Home', 'home', None),
    ('world', 'World', 'map', 'MAKE'),
    ('creatures', 'Creatures', 'skull', None),
    ('items', 'Items', 'sword', None),
    ('heroes', 'Heroes', 'helmet', None),
    ('spells', 'Spells', 'wand', None),
    ('tiles', 'Tiles', 'tiles', None),
    ('shops', 'Shops', 'coin', None),
    ('story', 'Story & talk', 'book', 'WRITE'),
    ('events', 'Events', 'bolt', None),
    ('doctor', 'Quest Doctor', 'check', 'QUEST'),
    ('mods', 'Mods', 'gear', None),
    ('settings', 'Settings', 'scroll', None),
]


def page_classes() -> dict:
    """The pages, by key (imported late: each is a module of its own)."""
    from .pages.base import Placeholder
    out = {}
    for key, title, icon, _ in NAV:
        cls = type(f'{key.title()}Page', (Placeholder,), {'key': key, 'title': title, 'icon': icon})
        out[key] = cls
    for key, mod, name in (('home', 'home', 'HomePage'), ('world', 'world', 'WorldPage'),
                           ('creatures', 'creatures', 'CreaturesPage'), ('items', 'items', 'ItemsPage'),
                           ('heroes', 'heroes', 'HeroesPage'), ('spells', 'spells', 'SpellsPage'),
                           ('tiles', 'tiles', 'TilesPage'), ('shops', 'shops', 'ShopsPage'),
                           ('story', 'story', 'StoryPage'), ('events', 'events', 'EventsPage'),
                           ('doctor', 'doctor', 'DoctorPage'), ('mods', 'mods', 'ModsPage'),
                           ('settings', 'settings', 'SettingsPage')):
        try:
            module = __import__(f'studio.pages.{mod}', fromlist=[name])
        except ModuleNotFoundError as e:
            if e.name != f'studio.pages.{mod}':
                raise
            continue
        out[key] = getattr(module, name)
    return out


class Studio:
    def __init__(self, root: tk.Tk, pack: str | None = None):
        self.root = root
        self.settings = load_settings()
        theme.make_dpi_aware()
        theme.apply(root, self.settings.get('theme', 'dark'))
        ui.install_wheel(root)
        root.title('The Quest Studio')
        self.session: Session | None = None
        self.pages: dict = {}
        self.current = None
        self.toasts = ui.Toasts(root)
        self.closed = False
        self.problems = []
        self._doctor_job = None
        root.protocol('WM_DELETE_WINDOW', self.quit)
        root.report_callback_exception = self._crashed
        self.shell = None
        w, h = self._size()
        root.geometry(f'{w}x{h}+{(root.winfo_screenwidth() - w) // 2}+{max(0, (root.winfo_screenheight() - h) // 3)}')
        root.minsize(min(1200, w), min(700, h))
        path = pack or self._first_pack()
        if not path:
            self.closed = True
            root.destroy()
            return
        self.open(path)
        root.bind_all('<Control-k>', lambda e: self.palette())
        root.bind_all('<Control-s>', lambda e: self.save())
        root.bind_all('<Control-z>', lambda e: self._undo(False))
        root.bind_all('<Control-y>', lambda e: self._undo(True))
        root.bind_all('<Control-Shift-Z>', lambda e: self._undo(True))
        root.bind_all('<F5>', lambda e: self.play())

    # ── start up ────────────────────────────────────────────────────────────
    def _size(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        return min(sw - 40, 1560), min(sh - 80, 940)

    def _first_pack(self):
        from .pages.welcome import choose_pack
        last = self.settings.get('last')
        if last and os.path.exists(os.path.join(last, 'quest.json')) and '--choose' not in sys.argv:
            return last
        self.root.update_idletasks()
        return choose_pack(self.root, last)

    def open(self, path: str):
        from editor import custom
        if self.session is not None:
            self.session.close()
        if custom.is_locked(path):
            ui.inform(self.root, 'Locked', 'The first 7 levels of The Quest are locked: they are never edited.\n\n'
                      'Make a quest of your own (it starts as a copy of them, in Custom Maps).')
            return
        self.session = Session(self.root, path)
        self.session.on_status = self._status_changed
        self.settings['last'] = path
        recent = [p for p in self.settings.get('recent', []) if p != path]
        self.settings['recent'] = ([path] + recent)[:8]
        save_settings(self.settings)
        self._build_shell()
        self.session.history_hooks.append(self._history_changed)
        self.go('home')

    # ── the window ──────────────────────────────────────────────────────────
    def _build_shell(self):
        self.session.listeners.clear()               # the pages below are made afresh and listen again
        self.session.on('any', lambda scope, source: self.changed_world())
        for w in self.root.winfo_children():
            if w is not self.toasts.box:
                w.destroy()
        for p in self.pages.values():
            p.destroy()
        self.pages = {}
        self.current = None
        r = self.root
        theme.apply(r, self.settings.get('theme', 'dark'))
        icons.clear()
        top = ttk.Frame(r, style='Bg.TFrame')
        top.pack(fill='x')
        self._topbar(top)
        bar = ttk.Frame(r, style='Bg.TFrame')              # packed before the body, so a page that wants more room never pushes it off
        bar.pack(fill='x', side='bottom')
        self._statusbar(bar)
        body = ttk.Frame(r, style='Bg.TFrame')
        body.pack(fill='both', expand=True)
        side = ttk.Frame(body, style='Side.TFrame', width=px(208))
        side.pack(side='left', fill='y')
        side.pack_propagate(False)
        self._sidebar(side)
        ttk.Separator(body, orient='vertical').pack(side='left', fill='y')
        self.content = ttk.Frame(body)
        self.content.pack(side='left', fill='both', expand=True)
        classes = page_classes()
        for key, cls in classes.items():
            page = cls(self.content, self)
            self.pages[key] = page
        self._history_changed()
        self._status_changed()
        self.changed_world()

    def _topbar(self, top):
        r = ttk.Frame(top, style='Bg.TFrame', padding=(px(14), px(8)))
        r.pack(fill='x')
        ttk.Label(r, image=icons.icon('sparkle', C['accent'], px(22)), style='Bg.TLabel').pack(side='left')
        ttk.Label(r, text='Quest Studio', style='Bg.TLabel', font=(theme.FONT, 13, 'bold')).pack(side='left', padx=(px(8), px(18)))
        self.pack_btn = ttk.Button(r, text=f'{self.session.project.quest.get("title") or self.session.project.name}  ▾',
                                   style='Flat.TButton', command=self._pack_menu)
        self.pack_btn.pack(side='left')
        right = ttk.Frame(r, style='Bg.TFrame')
        right.pack(side='right')
        self.play_btn = ui.button(right, 'Play', self.play, 'play', 'Accent.TButton', 'Test the game (F5)')
        self.play_btn.pack(side='right', padx=(px(10), 0))
        self.hero_pick = ttk.Combobox(right, state='readonly', width=11)
        self.hero_pick.pack(side='right')
        ui.tip(self.hero_pick, 'Which hero to play as when you test.')
        self.doctor_btn = ui.button(right, 'Check', lambda: self.go('doctor'), 'check', 'Flat.TButton',
                                    'The Quest Doctor: what is missing or broken')
        self.doctor_btn.pack(side='right', padx=px(6))
        ui.vsep(right).pack(side='right', fill='y', padx=px(8), pady=px(2))
        self.redo_btn = ui.button(right, '', lambda: self._undo(True), 'redo', 'Tool.TButton')
        self.redo_btn.pack(side='right')
        self.undo_btn = ui.button(right, '', lambda: self._undo(False), 'undo', 'Tool.TButton')
        self.undo_btn.pack(side='right')
        search = ttk.Button(r, text='  Search or jump to anything…   Ctrl+K', style='TButton', command=self.palette,
                            image=icons.icon('search', C['dim'], px(14)), compound='left', width=34)
        search.pack(side='left', padx=px(24), fill='x')
        menu = ui.button(r, '', self._main_menu, 'gear', 'Tool.TButton', 'Menu: packs, saving, theme')
        menu.pack(side='right', padx=px(6))
        self._menu_btn = menu
        self._fill_heroes()

    def _fill_heroes(self):
        classes = self.session.project.tables['classes']
        names = [f'{c["id"]} {c["name"]}' for c in classes]
        self.hero_pick.config(values=names)
        want = self.settings.get('hero')
        self.hero_pick.set(next((n for n in names if n.split()[0] == str(want)), names[0] if names else ''))
        self.hero_pick.bind('<<ComboboxSelected>>', lambda e: self.settings.__setitem__(
            'hero', int(self.hero_pick.get().split()[0])) or save_settings(self.settings))

    def _sidebar(self, side):
        ttk.Frame(side, style='Side.TFrame', height=px(10)).pack()
        self.nav_buttons = {}
        for key, title, icon, header in NAV:
            if header:
                ttk.Label(side, text=header, style='Bg.TLabel', foreground=C['faint'], font=(theme.FONT, 8, 'bold'),
                          padding=(px(18), px(14), 0, px(4))).pack(fill='x')
            row = tk.Frame(side, bg=C['bg'], cursor='hand2')
            row.pack(fill='x', padx=px(8), pady=1)
            img = tk.Label(row, image=icons.icon(icon, C['dim'], px(18)), bg=C['bg'])
            img.pack(side='left', padx=(px(10), px(10)), pady=px(7))
            txt = tk.Label(row, text=title, bg=C['bg'], fg=C['dim'], anchor='w', font=(theme.FONT, 10))
            txt.pack(side='left', fill='x', expand=True)
            badge = tk.Label(row, text='', bg=C['bg'], fg=C['bad'], font=(theme.FONT, 9, 'bold'))
            badge.pack(side='right', padx=px(8))
            for w in (row, img, txt, badge):
                w.bind('<Button-1>', lambda e, k=key: self.go(k))
                w.bind('<Enter>', lambda e, k=key: self._nav_paint(k, hover=True))
                w.bind('<Leave>', lambda e, k=key: self._nav_paint(k, hover=False))
            self.nav_buttons[key] = (row, img, txt, badge, icon)
        self._nav_paint_all()

    def _nav_paint(self, key, hover=None):
        row, img, txt, badge, icon = self.nav_buttons[key]
        on = key == self.current
        bg = C['select'] if on else C['hover'] if hover else C['bg']
        fg = C['accent'] if on else C['text'] if hover else C['dim']
        for w in (row, img, txt, badge):
            w.configure(bg=bg)
        txt.configure(fg=fg, font=(theme.FONT, 10, 'bold' if on else 'normal'))
        img.configure(image=icons.icon(icon, C['accent'] if on else C['text'] if hover else C['dim'], px(18)))

    def _nav_paint_all(self):
        for k in self.nav_buttons:
            self._nav_paint(k)

    def _statusbar(self, bar):
        inner = ttk.Frame(bar, style='Bg.TFrame', padding=(px(14), px(4)))
        inner.pack(fill='x')
        self.save_label = ttk.Label(inner, text='', style='Bg.TLabel', foreground=C['dim'])
        self.save_label.pack(side='left')
        self.hint = ttk.Label(inner, text='', style='Bg.TLabel', foreground=C['faint'])
        self.hint.pack(side='right')

    # ── status ──────────────────────────────────────────────────────────────
    def _status_changed(self):
        if self.session is None or not hasattr(self, 'save_label'):
            return
        st = self.session.status
        text, colour = {'saved': ('All changes saved', C['ok']), 'unsaved': ('Saving…', C['warn']),
                        'saving': ('Saving…', C['warn']),
                        'error': (f'Could not save: {self.session.last_error}', C['bad'])}[st]
        try:
            self.save_label.configure(text='●  ' + text, foreground=colour)
        except tk.TclError:
            pass

    def _history_changed(self):
        if self.session is None or not hasattr(self, 'undo_btn'):
            return
        h = self.session.history
        try:
            self.undo_btn.state(['!disabled'] if h.can_undo() else ['disabled'])
            self.redo_btn.state(['!disabled'] if h.can_redo() else ['disabled'])
            ui.tip(self.undo_btn, f'Undo {h.can_undo()} (Ctrl+Z)' if h.can_undo() else 'Nothing to undo')
            ui.tip(self.redo_btn, f'Redo {h.can_redo()} (Ctrl+Y)' if h.can_redo() else 'Nothing to redo')
        except tk.TclError:
            pass

    def say(self, text, kind='info', action=None):
        self.toasts.show(text, kind, action=action)

    def set_hint(self, text):
        try:
            self.hint.configure(text=text)
        except tk.TclError:
            pass

    def changed_world(self):
        """Something in the quest changed that the Doctor and Home may care about: read it again a moment after the last change."""
        if self._doctor_job is not None:
            self.root.after_cancel(self._doctor_job)
        self._doctor_job = self.root.after(900, self.run_doctor)

    def run_doctor(self):
        from . import doctor
        self._doctor_job = None
        if self.session is None or self.closed:
            return
        try:
            self.problems = doctor.check(self.session)
        except Exception as e:                                         # noqa: BLE001 - the Doctor must never stop the Studio
            import traceback
            traceback.print_exc()
            self.problems = []
        self.update_badges()
        for key in ('doctor', 'home'):
            page = self.pages.get(key)
            if page is not None and page.built and page.visible:
                page.render() if hasattr(page, 'render') else page.reload()

    def update_badges(self):
        ign = set(self.settings.get('ignored', {}).get(self.session.project.root, []))
        live = [p for p in self.problems if p.key not in ign and p.severity in ('error', 'warn')]
        self.set_badge('doctor', len(live))
        try:
            self.doctor_btn.configure(text=f'Check  ({len(live)})' if live else 'Check')
        except tk.TclError:
            pass

    def set_badge(self, key, n):
        if key in self.nav_buttons:
            self.nav_buttons[key][3].configure(text=str(n) if n else '')

    # ── pages ───────────────────────────────────────────────────────────────
    def go(self, key, **where):
        if key not in self.pages:
            return
        if self.current and self.current in self.pages:
            self.pages[self.current].hide()
            self.pages[self.current].pack_forget()
        self.current = key
        self.set_hint('')
        page = self.pages[key]
        page.pack(fill='both', expand=True)
        try:                                           # a box on the page just left may still hold the keyboard
            w = self.root.focus_get()
            if w is not None and not w.winfo_viewable():
                self.root.focus_set()
        except (KeyError, tk.TclError):
            pass
        page.show(**where)
        self._nav_paint_all()

    def page(self, key):
        return self.pages[key]

    def reload_all(self):
        for p in self.pages.values():
            if p.built:
                p.reload()

    # ── commands ────────────────────────────────────────────────────────────
    def _undo(self, redo):
        w = self.root.focus_get()
        if isinstance(w, (tk.Text, tk.Entry, ttk.Entry, ttk.Spinbox)) and not (isinstance(w, ttk.Combobox) and str(w.cget('state')) == 'readonly') \
                and w.winfo_viewable():
            return                                     # a box being typed in has its own undo
        label = self.session.redo() if redo else self.session.undo()
        if label:
            self.say(f'{"Redid" if redo else "Undid"}: {label}')
        else:
            self.say('Nothing to redo' if redo else 'Nothing to undo')

    def save(self):
        ok, made = self.session.save_now(True)
        if not ok:
            self.say(f'Could not save: {self.session.last_error}', 'bad')
        elif isinstance(made, str) and made.startswith('!'):
            self.say('Saved. (The zip of your additions could not be made.)', 'warn')
        elif made:
            self.say(f'Saved, and a zip of your additions was made:\n{made}', 'ok')
        else:
            self.say('Saved.', 'ok')

    def play(self, level=None, at=None, **kw):
        from .play import launch
        launch(self, level, at, **kw)

    def palette(self):
        from .palette_cmd import CommandPalette
        CommandPalette(self)

    def _pack_menu(self):
        from editor import custom
        m = tk.Menu(self.root, tearoff=False)
        for name in custom.packs():
            m.add_command(label=name, command=lambda n=name: self.open(custom.pack_dir(n)))
        m.add_separator()
        m.add_command(label='New quest…', command=self.new_pack)
        b = self.pack_btn
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def new_pack(self):
        from .pages.welcome import new_pack_dialog
        path = new_pack_dialog(self.root)
        if path:
            self.open(path)

    def _main_menu(self):
        m = tk.Menu(self.root, tearoff=False)
        m.add_command(label='Save now (and make the zip)', accelerator='Ctrl+S', command=self.save)
        m.add_command(label='Quests…', command=lambda: self._switch())
        m.add_command(label='New quest…', command=self.new_pack)
        m.add_separator()
        m.add_command(label='Send my edits…', command=self.send_edits)
        m.add_command(label='Restore my saved edits…', command=self.restore_edits)
        m.add_command(label='Recover pictures without entries', command=self.recover_pictures)
        m.add_command(label='Wishes…', command=self.wishes)
        m.add_separator()
        m.add_command(label='Switch to the ' + ('light' if theme.name() == 'dark' else 'dark') + ' theme',
                      command=self.toggle_theme)
        m.add_command(label='Shortcuts and help', command=self.help)
        m.add_separator()
        m.add_command(label='Quit', command=self.quit)
        b = self._menu_btn
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def _switch(self):
        from .pages.welcome import choose_pack
        path = choose_pack(self.root, self.settings.get('last'), force=True)
        if path:
            self.open(path)

    def toggle_theme(self):
        self.settings['theme'] = 'light' if theme.name() == 'dark' else 'dark'
        save_settings(self.settings)
        keep = self.current
        self._build_shell()
        self.go(keep or 'home')

    def send_edits(self):
        from editor.send_window import SendWindow
        SendWindow(self)

    def restore_edits(self):
        from .pages.tools import restore_edits
        restore_edits(self)

    def recover_pictures(self):
        from .pages.tools import recover_pictures
        recover_pictures(self)

    def wishes(self):
        from editor.wishes import WishesWindow
        WishesWindow(self)

    def help(self):
        from .pages.tools import show_help
        show_help(self)

    # editor.send_window / wishes expect these of their app:
    @property
    def project(self):
        return self.session.project

    def status(self, text):
        self.say(text)

    def changed(self):
        self.session.touched()

    def save_zip_only(self):
        return self.session.save_now(True)

    # ── leaving ─────────────────────────────────────────────────────────────
    def _crashed(self, exc, val, tb):
        import traceback
        text = ''.join(traceback.format_exception(exc, val, tb))
        try:
            from editor import side_save
            os.makedirs(side_save.home_dir(), exist_ok=True)
            with open(os.path.join(side_save.home_dir(), 'studio_crash.txt'), 'a', encoding='utf-8') as fh:
                fh.write(time.strftime('%Y-%m-%d %H:%M:%S\n') + text + '\n')
        except Exception:                              # noqa: BLE001
            pass
        sys.stderr.write(text)
        if self.session is not None:
            self.session.autosave()
        try:
            self.say('Something went wrong, but your work is saved. (studio_crash.txt has the details)', 'bad')
        except Exception:                              # noqa: BLE001
            pass

    def quit(self):
        if self.session is not None:
            self.session.close()
        self.closed = True
        self.root.destroy()


def main():
    theme.make_dpi_aware()
    root = tk.Tk()
    app = Studio(root)
    if not app.closed:
        root.mainloop()
