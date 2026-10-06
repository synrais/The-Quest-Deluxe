"""stories.txt: the story pages (`number lines` then that many lines of text), read and written the game's way."""
from __future__ import annotations

from editor.stories_tab import Story, parse, write

PAGE_LINES = 15
PAGE_WIDTH = 78
RESERVED = {0: 'opens a new game', 1: 'after character creation', 8: 'the ending', 9: 'the good ending'}


def stories(project) -> list:
    return [it for it in parse(project.texts['stories']) if isinstance(it, Story)]


def used_by(project) -> dict:
    """Which story numbers are shown where: {number: 'before level n'} (plus the reserved ones)."""
    out = dict(RESERVED)
    for n in range(1, project.levels + 1):
        for s in project.constant(n, 'STORIES', []) or []:
            out[s] = f'before level {n}'
    return out


def next_number(project) -> int:
    return max([9] + [s.number for s in stories(project)]) + 1


def add_story(project, lines, number=None) -> int:
    """Append a story; returns its number (the next free one from 10 up unless given)."""
    items = parse(project.texts['stories'])
    no = number if number is not None else next_number(project)
    items.append(Story(no, list(lines)))
    project.texts['stories'] = write(items)
    project.touch('stories')
    return no
