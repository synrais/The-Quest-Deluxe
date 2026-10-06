"""How the pack's tables are described: every field of an item, creature, spell, class or tile once, with its group and hint.

The Studio builds its forms from these descriptions (studio/schema.py); nothing here makes a widget. A table's description
is a `Described` subclass: `fields()` lists the `Field`s (dotted keys like 'look.colour' reach nested values), `GROUPS`
puts them in sections, `after_change` tidies related fields, `uses` says where an entry is used.
"""
from __future__ import annotations


class Field:
    def __init__(self, key, label, kind='int', choices=None, when=None, hint='', default=None, width=8,
                 fmt=None, parse=None, suggest=None, spin=None):
        self.spin = spin                  # (low, high): a number with little up and down arrows
        self.suggest = suggest            # 'custom' text with a drop-down of values to start it from
        self.key, self.label, self.kind = key, label, kind
        self.fmt, self.parse = fmt, parse        # 'custom': row -> text, text -> value (ValueError if wrong)
        self.choices = choices            # [(value, label)] for 'choice' and 'multi'
        self.when = when                  # row -> bool: does the field apply to this entry?
        self.hint, self.default, self.width = hint, default, width


class Described:
    TABLE = ''
    ICON_LAYER = ''                       # the layer whose pictures change with this table ('item', 'mon', ...)
    PICTURES: list = []                   # [(label, sprite folder, is_bag_cell)]
    INTRO = ''
    # The form in sections: [(title, open at first, what it is for, [field keys])]. A field in no section goes in
    # "More"; a field with no section at all stays at the top (the number, the name).
    GROUPS: list = []

    app = None                            # what the description reads the pack through: .project, .pictures_changed(layer, v)

    @property
    def rows(self) -> list:
        return self.app.project.tables[self.TABLE]

    def fields(self) -> list:
        return []

    def uses(self, row) -> list:
        return []

    def duplicate_id(self, row) -> int:
        return self.app.project.next_id(self.TABLE, row['id'] + 1)

    def label(self, row) -> str:
        return f'{row["id"]}  {row.get("name", "")}'

    def after_change(self, row, key, old):
        """A field changed from old (subclasses fix up related fields here)."""

    def ask(self, title: str, text: str) -> bool:
        """A yes/no question to the person (the Studio puts its own window here); no by default."""
        return False

    # ── fields, with dotted keys for nested values ('look.colour') ──────────
    @staticmethod
    def get(row, key, default=None):
        for part in key.split('.')[:-1]:
            row = row.get(part) or {}
        return row.get(key.split('.')[-1], default)

    @staticmethod
    def put(row, key, value):
        *path, last = key.split('.')
        for part in path:
            row = row.setdefault(part, {})
        row[last] = value

    @staticmethod
    def drop(row, key):
        *path, last = key.split('.')
        for part in path:
            row = row.get(part) or {}
        row.pop(last, None)
