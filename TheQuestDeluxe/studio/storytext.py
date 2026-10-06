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


def get(project, number):
    return next((s for s in stories(project) if s.number == number), None)


def _store(project, items):
    project.texts['stories'] = write(items)
    project.touch('stories')


def set_lines(project, number, lines):
    items = parse(project.texts['stories'])
    st = next((it for it in items if isinstance(it, Story) and it.number == number), None)
    if st is None:
        return False
    st.lines = list(lines)
    _store(project, items)
    return True


def renumber(project, old, new):
    items = parse(project.texts['stories'])
    if any(isinstance(it, Story) and it.number == new for it in items):
        return False
    for it in items:
        if isinstance(it, Story) and it.number == old:
            it.number = new
            _store(project, items)
            return True
    return False


def delete(project, number):
    items = parse(project.texts['stories'])
    keep = [it for it in items if not (isinstance(it, Story) and it.number == number)]
    _store(project, keep)


def wrap(text: str, width: int = 72) -> list:
    """Paragraphs wrapped to the page's width, blank lines kept."""
    import textwrap
    out = []
    for para in text.split('\n'):
        out += textwrap.wrap(para, width) or ['']
    while out and out[-1] == '':
        out.pop()
    return out
