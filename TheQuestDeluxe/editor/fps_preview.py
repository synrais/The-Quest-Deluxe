"""The hero's weapon (and shield) as FPS mode shows it in his hands, drawn by the game's own code (engine.hands) from the
project's pictures, with tools to set how it moves when he attacks, how it is turned, and where it sits in the hand."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pygame

from engine.hands import ATTACK_MS, Hands, attack_kind
from engine.state import SLOT_OFFHAND, SLOT_WEAPON

from .art import photo
from .uikit import tip

VIEW = 400                      # the FPS view is 400 x 400 pixels
SCALE = 0.5                     # shown this much smaller
ATTACKS = [(None, 'Automatic'), ('swing', 'Swing'), ('thrust', 'Thrust'), ('shoot', 'Shoot')]


class _Pack:
    """engine.pack.Pack's side of it that engine.hands asks for, from the editor's project."""

    def __init__(self, project):
        self.project = project

    def path(self, *parts):
        return self.project.path(*parts)

    def item(self, v):
        return next((r for r in self.project.tables['items'] if r['id'] == v), {})

    def item_type(self, v):
        return self.item(v).get('type', '') if v else ''


class _Bag:
    def __init__(self, project):
        self.project = project

    def __contains__(self, item):
        return self.project.picture('bag', item) is not None

    def __getitem__(self, item):
        return self.project.picture('bag', item)


class _Sprites:
    def __init__(self, project):
        self.bag = _Bag(project)


class _Game:
    """Just what Hands.draw reads from a game."""

    def __init__(self, bag):
        self.player = type('P', (), {'bag': bag})()
        self.renderer = object()
        self.swing = self.hand_fx = None
        self.swing_hand = 'right'
        self.slots_swapped = False


class FpsPreview(ttk.LabelFrame):
    def __init__(self, master, project, hero_box, place):
        super().__init__(master, text='In FPS mode: in his hand', padding=4)
        self.project, self.box, self.place, self.row = project, hero_box, place, None
        self.attacking = None
        left = ttk.Frame(self)
        left.pack(side='left', anchor='n')
        right = ttk.Frame(self)
        right.pack(side='left', anchor='n', padx=(8, 0))
        self.image = ttk.Label(left)
        self.image.pack()
        self.image.bind('<ButtonPress-1>', self.grab)
        self.image.bind('<B1-Motion>', self.drag)
        self.image.bind('<ButtonRelease-1>', self.drop)
        tip(self.image, 'The weapon or shield as FPS mode shows it in the hero\'s hand. Drag it to move it in his hand.')
        row = ttk.Frame(right)
        row.pack(anchor='w', pady=(4, 0))
        ttk.Label(row, text='Attack').pack(side='left')
        self.attack = ttk.Combobox(row, state='readonly', width=13, values=[t for _, t in ATTACKS])
        self.attack.pack(side='left', padx=4)
        self.attack.bind('<<ComboboxSelected>>', lambda e: self.place('fps_attack', ATTACKS[self.attack.current()][0]))
        tip(self.attack, 'How it moves when the hero attacks in FPS mode. Automatic: spears swing... thrust, launchers shoot, the rest swing.')
        row = ttk.Frame(right)
        row.pack(anchor='w', pady=(4, 0))
        ttk.Label(row, text='Turn').pack(side='left')
        self.turn = ttk.Spinbox(row, from_=-180, to=180, increment=15, width=6, command=self.turned)
        self.turn.pack(side='left', padx=4)
        self.turn.bind('<Return>', lambda e: self.turned())
        self.turn.bind('<FocusOut>', lambda e: self.turned())
        ttk.Label(row, text='\u00b0 anticlockwise').pack(side='left')
        tip(self.turn, 'Degrees to turn the bag picture so it stands upright in the hand (a crossbow: 90). Empty: automatic (a picture lying down is stood up).')
        pad = ttk.Frame(right)
        pad.pack(anchor='w', pady=(4, 0))
        ttk.Label(pad, text='Position').grid(row=0, column=0, rowspan=2, padx=(0, 6))
        for text, (dx, dy), col, rw_, hint in (('▲', (0, -1), 2, 0, 'Up a few pixels.'), ('◀', (-1, 0), 1, 1, 'Left a few pixels.'),
                                             ('▼', (0, 1), 2, 1, 'Down a few pixels.'), ('▶', (1, 0), 3, 1, 'Right a few pixels.')):
            b = ttk.Button(pad, text=text, width=3, command=lambda d=(dx, dy): self.nudge(*d))
            b.grid(row=rw_, column=col)
            tip(b, hint)
        self.where = ttk.Label(pad, text='')
        self.where.grid(row=0, column=4, rowspan=2, padx=8)
        bar = ttk.Frame(right)
        bar.pack(anchor='w', pady=(4, 0))
        for text, cmd, hint in (('Test attack', self.test_attack, 'Play the attack as the game does.'),
                                ('Reset', self.reset, 'Back to automatic and the usual place.')):
            b = ttk.Button(bar, text=text, command=cmd)
            b.pack(side='left', padx=2)
            tip(b, hint)
        hero_box.listeners.append(self.refresh)

    # ── what is in his hands ────────────────────────────────────────────────
    def mine(self):
        return self.row is not None and self.row.get('type') in ('weapon', 'launcher', 'shield')

    def mirror(self):
        """-1 for a weapon in the off hand (its sideways moves are the mirror), else 1."""
        return -1 if self.mine() and self.box.subject_slot() == 'shield' and self.row.get('type') != 'shield' else 1

    def show(self, row):
        self.row = row
        row = row or {}
        self.attack.set(next((t for v, t in ATTACKS if v == row.get('fps_attack')), ATTACKS[0][1]))
        self.turn.set('' if row.get('fps_turn') is None else row['fps_turn'])
        self.attack.config(state='readonly' if row.get('type') in ('weapon', 'launcher') else 'disabled')
        self.refresh()

    def frame(self, now):
        parts = self.box.parts()
        game = _Game({SLOT_WEAPON: parts.get('weapon', 0), SLOT_OFFHAND: parts.get('shield', 0)})
        if self.attacking:
            kind, t0 = self.attacking
            game.swing = (kind, t0, False)
            game.swing_hand = 'left' if self.box.subject_slot() == 'shield' else 'right'
        view = pygame.Surface((VIEW, VIEW))
        view.fill((70, 70, 84), (0, 0, VIEW, VIEW // 2))
        view.fill((96, 76, 56), (0, VIEW // 2, VIEW, VIEW // 2))
        Hands(_Pack(self.project), _Sprites(self.project)).draw(game, view, now)
        return pygame.transform.scale(view, (int(VIEW * SCALE), int(VIEW * SCALE)))

    def refresh(self):
        if not self.winfo_exists() or self.row is None:
            return
        self._photo = photo(self.frame(pygame.time.get_ticks()))
        self.image.config(image=self._photo)
        self.where.config(text=f'{int(self.row.get("fps_dx") or 0):+d}, {int(self.row.get("fps_dy") or 0):+d}')

    def test_attack(self):
        if not self.mine():
            return
        kind = attack_kind(self.row) if self.row.get('type') != 'shield' else 'swing'
        self.attacking = (kind, pygame.time.get_ticks())
        self.play()

    def play(self):
        if not self.attacking or not self.winfo_exists():
            return
        kind, t0 = self.attacking
        if pygame.time.get_ticks() - t0 > ATTACK_MS[kind]:
            self.attacking = None
        self.refresh()
        if self.attacking:
            self.after(30, self.play)

    # ── placing it ──────────────────────────────────────────────────────────
    def grab(self, event):
        if self.mine():
            self._from = (event.x, event.y, int(self.row.get('fps_dx') or 0), int(self.row.get('fps_dy') or 0))

    def drag(self, event):
        if self.mine() and getattr(self, '_from', None):
            x, y, dx, dy = self._from
            self.moved(dx + self.mirror() * round((event.x - x) / SCALE), dy + round((event.y - y) / SCALE), final=False)

    def drop(self, event):
        if self.mine() and getattr(self, '_from', None):
            self._from = None
            self.place('fps_dx', int(self.row.get('fps_dx') or 0))

    def moved(self, dx, dy, final=True):
        self.place('fps_dx', dx, final=False)
        self.place('fps_dy', dy, final=final)
        self.refresh()

    def nudge(self, dx, dy):
        if self.mine():
            self.moved(int(self.row.get('fps_dx') or 0) + 4 * self.mirror() * dx, int(self.row.get('fps_dy') or 0) + 4 * dy,
                       final=False)

    def turned(self):
        if not self.mine():
            return
        text = self.turn.get().strip()
        try:
            value = int(text) if text else None
        except ValueError:
            return
        if value != self.row.get('fps_turn'):
            self.place('fps_turn', value)

    def reset(self):
        if self.mine():
            for key in ('fps_attack', 'fps_turn', 'fps_dy'):
                self.place(key, None, final=False)
            self.place('fps_dx', 0)
