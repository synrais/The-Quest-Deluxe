"""talk.txt as a list of entries, written back in the original's layout:

    level person number "first line;                     (one line)
    level person number "first line"                     (two lines)
    "second line;

Blank lines and anything that isn't an entry are kept where they are, so the file round-trips
unchanged; the game reads it character by character (deluxe.events.talk_text), quirks included.
"""
from __future__ import annotations

import re

HEAD = re.compile(r'^\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*"(.*)$')


class Entry:
    def __init__(self, level, person, number, line1, line2=None, raw=None):
        self.level, self.person, self.number = level, person, number
        self.line1, self.line2 = line1, line2
        self.raw = raw                    # the entry as the file had it, until it is changed
        self._as_read = (level, person, number, line1, line2)

    def text(self) -> str:
        if self.raw is not None and (self.level, self.person, self.number, self.line1, self.line2) == self._as_read:
            return self.raw
        if self.line2 is None:
            return f'{self.level} {self.person} {self.number} "{self.line1};'
        return f'{self.level} {self.person} {self.number} "{self.line1}"\n"{self.line2};'

    @property
    def key(self):
        return self.level, self.person, self.number


def parse(text: str) -> list:
    """Entries and the other lines (kept as strings), in file order."""
    out, lines, i = [], text.split('\n'), 0
    while i < len(lines):
        line = lines[i]
        m = HEAD.match(line)
        if m and line.endswith(';'):
            out.append(Entry(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)[:-1], raw=line))
        elif m and line.endswith('"') and i + 1 < len(lines) and lines[i + 1].startswith('"') and \
                lines[i + 1].endswith(';'):
            out.append(Entry(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)[:-1],
                             lines[i + 1][1:-1], raw=line + '\n' + lines[i + 1]))
            i += 1
        else:
            out.append(line)
        i += 1
    return out


def write(items: list) -> str:
    return '\n'.join(it.text() if isinstance(it, Entry) else it for it in items)


def entries(items: list) -> list:
    return [it for it in items if isinstance(it, Entry)]
