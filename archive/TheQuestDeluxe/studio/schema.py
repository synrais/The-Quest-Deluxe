"""What each table of the pack holds (its fields, their groups and hints), read from the editor's own descriptions.

The old editor describes every field of items, creatures, spells and classes once (editor/*_tab.py, as `Field` objects and
`GROUPS`). The Studio shows them in its own way but must never drift from them, so it reads the same descriptions instead
of copying them: a Schema wraps a legacy tab class without making its widgets.
"""
from __future__ import annotations

import importlib

from editor.table_tab import Field, TableTab

TABS = {'creatures': ('editor.creatures_tab', 'CreaturesTab'), 'items': ('editor.items_tab', 'ItemsTab'),
        'spells': ('editor.spells_tab', 'SpellsTab'), 'classes': ('editor.classes_tab', 'ClassesTab'),
        'tiles': ('editor.tiles_tab', 'TilesTab')}


class _App:
    """What a legacy tab expects of its app, as far as describing fields goes."""

    def __init__(self, session):
        self.project = session.project
        self.session = session

    def status(self, text):
        pass

    def pictures_changed(self, layer, v):
        self.session.pictures.forget(layer, v)

    def changed(self):
        pass


class Schema:
    def __init__(self, session, table: str):
        self.table = table
        table = 'tiles' if table in ('floors', 'walls', 'decos') else table
        mod, name = TABS[table]
        cls = getattr(importlib.import_module(mod), name)
        self.cls = cls
        self.t = cls.__new__(cls)                 # the tab without its widgets: only its descriptions are used
        self.t.app = _App(session)
        if self.table in ('floors', 'walls', 'decos'):
            self.t.kind = self.table
        self.session = session
        self.get, self.put, self.drop = TableTab.get, TableTab.put, TableTab.drop

    # descriptions ------------------------------------------------------------
    groups_override = None

    @property
    def groups(self):
        return self.groups_override if self.groups_override is not None else self.cls.GROUPS

    def set_kind(self, kind: str):
        """For the tiles: which of the three lists the tab describes."""
        self.table = kind
        self.t.kind = kind

    @property
    def intro(self):
        return getattr(self.cls, 'INTRO', '')

    @property
    def pictures(self):
        return self.t.PICTURES

    def all_fields(self) -> list:
        return self.t.fields()

    def fields(self, row) -> list:
        return [f for f in self.t.fields() if not f.when or f.when(row)]

    def label(self, row) -> str:
        return self.t.label(row)

    def uses(self, row) -> list:
        return self.t.uses(row)

    def after_change(self, row, key, old):
        return self.t.after_change(row, key, old)

    def duplicate_id(self, row) -> int:
        return self.t.duplicate_id(row)

    # a row shown: creatures get a read-only `_role` field the old tab fills in while it shows them
    def decorate(self, row):
        if self.table == 'creatures':
            from editor.creatures_tab import role
            row['_role'] = role(row['id'])

    def undecorate(self, row):
        row.pop('_role', None)
