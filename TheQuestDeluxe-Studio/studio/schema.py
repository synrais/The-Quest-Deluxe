"""What each table of the pack holds (its fields, their groups and hints), read from the descriptions in core/fields.

Every field of items, creatures, spells, classes and tiles is described once there (`Field` objects and `GROUPS`). The Studio
builds its forms from them; a Schema wraps one description for a session.
"""
from __future__ import annotations

import importlib

from . import ui
from core.fields.base import Described, Field   # noqa: F401  (Field is used by the pages)

TABS = {'creatures': ('core.fields.creatures', 'CreaturesTable'), 'items': ('core.fields.items', 'ItemsTable'),
        'spells': ('core.fields.spells', 'SpellsTable'), 'classes': ('core.fields.classes', 'ClassesTable'),
        'tiles': ('core.fields.tiles', 'TilesTable')}


class _App:
    """What a description expects of its app: the project, and to be told when a picture changes."""

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
        self.t = cls()
        self.t.app = _App(session)
        if self.table in ('floors', 'walls', 'decos'):
            self.t.kind = self.table
        self.t.ask = lambda title, text: ui.confirm(session.root, title, text)
        self.session = session
        self.get, self.put, self.drop = Described.get, Described.put, Described.drop

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
            from core.fields.creatures import role
            row['_role'] = role(row['id'])

    def undecorate(self, row):
        row.pop('_role', None)
