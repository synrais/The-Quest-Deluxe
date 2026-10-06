"""The session: the open pack, its history, its pictures, saving as you go, and a small bus that tells pages what changed."""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager

from editor import side_save
from editor.project import Project

from .history import History, TABLES
from .pictures import Pictures

SETTINGS = os.path.join(os.path.expanduser('~'), '.quest_studio.json')
FOLDER_LAYER = {'floors': 'floor', 'walls': 'wall', 'decos': 'deco', 'items': 'item', 'creatures': 'mon', 'bag': 'bag',
                'spells': 'spell'}
AUTOSAVE_MS = 1500


def load_settings() -> dict:
    try:
        with open(SETTINGS, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_settings(data: dict):
    try:
        with open(SETTINGS, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=1)
    except OSError:
        pass


class Session:
    """Everything about the pack being edited. Pages read self.project, change it only inside `with session.edit(...)`."""

    def __init__(self, root, path: str):
        self.root = root                      # a Tk widget (for after())
        self.project = Project(path)
        self.pictures = Pictures(self.project)
        self.history = History(self.project, self._undone)
        self.listeners: dict[str, list] = {}
        self.status = 'saved'                 # 'saved' | 'unsaved' | 'saving' | 'error'
        self.saved_at = time.time()
        self._job = None
        self.on_status = None                 # called when `status` changes
        self.last_error = ''
        self.history.listeners.append(self._history_changed)
        self.history_hooks = []

    # ── the bus ─────────────────────────────────────────────────────────────
    def on(self, topic: str, fn):
        self.listeners.setdefault(topic, []).append(fn)

    def off_all(self, owner):
        for fns in self.listeners.values():
            fns[:] = [f for f in fns if getattr(f, '__self__', None) is not owner]

    def notify(self, scope, source=None):
        topic = scope if isinstance(scope, str) else scope[0]
        for fn in list(self.listeners.get(topic, ())) + list(self.listeners.get('any', ())):
            try:
                fn(scope, source)
            except Exception as e:                # noqa: BLE001 - a page that fails must not stop the others
                import traceback
                traceback.print_exc()
                self.last_error = str(e)

    def _undone(self, scope):
        if not isinstance(scope, str) and scope[0] == 'pic':
            layer = FOLDER_LAYER.get(scope[1])
            if layer:
                self.pictures.forget(layer, scope[2])
        self.notify(scope, None)

    def _history_changed(self):
        self._mark_unsaved()
        for fn in self.history_hooks:
            fn()

    # ── editing ─────────────────────────────────────────────────────────────
    @contextmanager
    def edit(self, label: str, *scopes, merge=None, source=None):
        """with session.edit('Rename the orc', 'creatures'): ... — the history keeps a before and an after."""
        before = self.history.begin(scopes)
        try:
            yield
        finally:
            self.history.commit(label, before, merge)
            for s in scopes:
                if not isinstance(s, str) and s[0] == 'pic':
                    layer = FOLDER_LAYER.get(s[1])
                    if layer:
                        self.pictures.forget(layer, s[2])
                self.notify(s, source)

    def begin_stroke(self, *scopes):
        """For a long gesture (a brush stroke): capture now, commit when it ends."""
        return self.history.begin(scopes)

    def end_stroke(self, label, before, source=None):
        self.history.commit(label, before)
        for s in before:
            self.notify(s, source)

    def undo(self):
        return self.history.undo()

    def redo(self):
        return self.history.redo()

    # ── saving ──────────────────────────────────────────────────────────────
    def _mark_unsaved(self):
        if self.status != 'unsaved':
            self.status = 'unsaved'
            if self.on_status:
                self.on_status()
        if self._job is not None:
            self.root.after_cancel(self._job)
        self._job = self.root.after(AUTOSAVE_MS, self.autosave)

    def touched(self):
        """Something was changed without the history (a wizard, an import): save soon."""
        self._mark_unsaved()

    def autosave(self) -> bool:
        self._job = None
        if not self.project.dirty:
            if self.status != 'saved':
                self.status = 'saved'
                if self.on_status:
                    self.on_status()
            return True
        self.status = 'saving'
        if self.on_status:
            self.on_status()
        try:
            self.project.save()
        except Exception as e:                    # noqa: BLE001
            self.status = 'error'
            self.last_error = str(e)
            if self.on_status:
                self.on_status()
            self._job = self.root.after(5000, self.autosave)
            return False
        self.status = 'saved'
        self.saved_at = time.time()
        if self.on_status:
            self.on_status()
        return True

    def save_now(self, zip_too: bool = True):
        """Save now, and make the zip of the additions (what Send my edits sends). Returns (ok, zip path or message)."""
        ok = self.autosave()
        made = None
        if ok and zip_too:
            try:
                before = side_save.saved_zips()
                path, _ = side_save.save_zip()
                made = path if path and path not in before else None
            except Exception as e:                # noqa: BLE001
                return True, f'!{e}'
        return ok, made

    # ── helpers pages use ───────────────────────────────────────────────────
    def rows(self, table: str) -> list:
        return self.project.tables[table]

    def row(self, table: str, v):
        return next((r for r in self.project.tables[table] if r['id'] == v), None)

    def name_of(self, table: str, v) -> str:
        r = self.row(table, v)
        return (r.get('name') if r else None) or f'#{v}'

    @property
    def levels(self) -> int:
        return self.project.levels

    def close(self):
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None
        self.autosave()
