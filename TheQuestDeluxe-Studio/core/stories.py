"""The story screens: stories.txt holds each as `number lines` followed by that many lines of text. Story 0 opens a new game,
1 follows character creation, the numbers a level's STORIES setting names show before it, and 8 and 9 end the game (9 after a
good ending)."""
from __future__ import annotations

import re

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
