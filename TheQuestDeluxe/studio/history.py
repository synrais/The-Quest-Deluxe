"""Undo and redo for everything in a quest: tables, tiles, text, level maps, scripts, pictures.

An edit names the parts of the quest it touches (its scopes); the history keeps a copy of those parts from before and after,
so Ctrl+Z puts them back whatever the edit was. Scopes: 'items' 'creatures' 'spells' 'classes' 'skills' (tables), 'tiles',
'quest', 'texts', ('map', n), ('script', n), ('shops', n), ('pic', folder, id).
"""
from __future__ import annotations

import copy
import time

TABLES = ('items', 'creatures', 'spells', 'classes', 'skills')


class History:
    LIMIT = 150

    def __init__(self, project, notify):
        self.project = project
        self.notify = notify                     # notify(scope): the part of the quest that changed
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []
        self.listeners = []

    # ── copies of the parts of the quest ────────────────────────────────────
    def capture(self, scope):
        p = self.project
        if scope in TABLES:
            return copy.deepcopy(p.tables[scope])
        if scope == 'tiles':
            return copy.deepcopy(p.tiles)
        if scope == 'quest':
            return copy.deepcopy(p.quest)
        if scope == 'texts':
            return dict(p.texts)
        kind = scope[0]
        if kind == 'map':
            return copy.deepcopy(p.grid(scope[1]).sq)
        if kind == 'script':
            return p.scripts.get(scope[1], '')
        if kind == 'shops':
            return dict(p.shops.get(scope[1], {}))
        if kind == 'pic':
            rel = f'{scope[1]}/{scope[2]}.png'
            if rel in p.pictures:
                return p.pictures[rel]
            import os
            path = p.path('sprites', scope[1], f'{scope[2]}.png')
            if os.path.exists(path):
                with open(path, 'rb') as fh:
                    return fh.read()
            return None
        raise KeyError(scope)

    def restore(self, scope, state):
        p = self.project
        if scope in TABLES:
            p.tables[scope][:] = copy.deepcopy(state)
        elif scope == 'tiles':
            p.tiles.clear()
            p.tiles.update(copy.deepcopy(state))
        elif scope == 'quest':
            p.quest.clear()
            p.quest.update(copy.deepcopy(state))
            p.quest['levels'] = max(1, int(p.quest.get('levels', 1)))
        elif scope == 'texts':
            p.texts.clear()
            p.texts.update(state)
        elif scope[0] == 'map':
            p.grid(scope[1]).sq[:] = copy.deepcopy(state)
        elif scope[0] == 'script':
            p.scripts[scope[1]] = state
        elif scope[0] == 'shops':
            p.shops[scope[1]] = dict(state)
        elif scope[0] == 'pic':
            rel = f'{scope[1]}/{scope[2]}.png'
            p.pictures[rel] = state
        self.touch(scope)

    def touch(self, scope):
        p = self.project
        if scope in TABLES or scope in ('tiles', 'quest', 'texts'):
            if scope == 'texts':
                for k in p.texts:
                    p.touch(k)
            else:
                p.touch(scope)
        elif scope[0] == 'pic':
            p.touch('pictures')
        elif scope[0] in ('map', 'script', 'shops') and scope[1] > p.levels:
            p.dirty.discard(scope)                       # a level that is gone (undone, or removed): its folder goes
            p.dirty.add(('drop_level', scope[1]))
        else:
            p.touch(scope)

    # ── recording ───────────────────────────────────────────────────────────
    def begin(self, scopes):
        return {s: self.capture(s) for s in scopes}

    def commit(self, label, before, merge=None):
        after = {s: self.capture(s) for s in before}
        now = time.monotonic()
        last = self.undo_stack[-1] if self.undo_stack else None
        if merge and last and last.get('merge') == merge and now - last['time'] < 1.5 and set(last['before']) == set(before):
            last['after'], last['time'] = after, now             # typing in one box, dragging one slider: one step
        else:
            self.undo_stack.append({'label': label, 'before': before, 'after': after, 'merge': merge, 'time': now})
            del self.undo_stack[:-self.LIMIT]
        self.redo_stack.clear()
        for s in before:
            self.touch(s)
        self._changed()

    def can_undo(self) -> str | None:
        return self.undo_stack[-1]['label'] if self.undo_stack else None

    def can_redo(self) -> str | None:
        return self.redo_stack[-1]['label'] if self.redo_stack else None

    def undo(self):
        if not self.undo_stack:
            return None
        e = self.undo_stack.pop()
        for s, state in e['before'].items():
            self.restore(s, state)
        self.redo_stack.append(e)
        for s in e['before']:
            self.notify(s)
        self._changed()
        return e['label']

    def redo(self):
        if not self.redo_stack:
            return None
        e = self.redo_stack.pop()
        for s, state in e['after'].items():
            self.restore(s, state)
        self.undo_stack.append(e)
        for s in e['after']:
            self.notify(s)
        self._changed()
        return e['label']

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._changed()

    def _changed(self):
        for fn in self.listeners:
            fn()
