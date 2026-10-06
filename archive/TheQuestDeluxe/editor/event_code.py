"""Writing level-script code for the Events tab's wizard: the `if` for a "when ... only if ..." rule, one line
for each thing it does, and putting that into the script's handler (made if the script has none yet)."""
from __future__ import annotations

import re

HEADERS = {'talk': 'def talk(npc):', 'dies': 'def dies(w):', 'level_start': 'def level_start():',
           'opened_chest': 'def opened_chest():', 'took': 'def took(item):'}

# what each kind of event is about: the handler it goes in, and the test for its subject
WHEN = {
    'talk': ('talk', 'npc == {id}'),
    'dies': ('dies', 'slot(w).type == {id}'),
    'arrive': ('level_start', None),
    'chest': ('opened_chest', None),
    'took': ('took', 'item == {id}'),
}

IF = {
    'm1': 'm1 == {n}',
    'm2': 'm2 == {n}',
    'has': 'has_any({n})',
    'hasnt': 'not has_any({n})',
    'rep': 'rep >= {n}',
    'coins': 'coins >= {n}',
}

DO = {
    'say': 'say({n})',
    'message': 'message({n[0]}, {n[1]})',
    'give': 'give({n})',
    'take': 'take_any({n})',
    'drop': 'put(ax, ay, {n})',
    'm1': 'm1 = {n}',
    'm2': 'm2 = {n}',
    'rep': 'change_rep({n})',
    'coins': 'coins += {n}',
    'next': 'next_level()',
}


def rule_lines(when: str, subject: int | None, conditions: list, actions: list) -> list[str]:
    """The statements of one rule. conditions: [(key of IF, n)]; actions: [(key of DO, n)] or
    ('message', (person, number)). Returns unindented lines, an `if` with its body indented four spaces."""
    handler, test = WHEN[when]
    tests = [test.format(id=subject)] if test else []
    tests += [IF[k].format(n=n) for k, n in conditions]
    body = [DO[k].format(n=n) for k, n in actions]
    if not body:
        body = ['pass']
    if not tests:
        return body
    return [f'if {" and ".join(tests)}:'] + ['    ' + line for line in body]


def add_to_handler(text: str, handler: str, lines: list[str]) -> str:
    """The script with `lines` added to the end of the handler's body (a body that is only `pass` is replaced);
    the handler is added at the end of the script if it has none. Blank lines and comments around it stay."""
    src = text.split('\n')
    start = next((i for i, line in enumerate(src) if re.match(rf'def {handler}\(', line)), None)
    if start is None:
        head = text.rstrip('\n')
        sep = '\n\n\n' if head.strip() else ''
        return head + sep + HEADERS[handler] + '\n' + '\n'.join('    ' + line if line else '' for line in lines) + '\n'
    last = start
    for i in range(start + 1, len(src)):
        line = src[i]
        if not line.strip():
            continue
        if line[0] in ' \t':
            last = i
        else:
            break
    body = src[start + 1:last + 1]
    real = [line for line in body if line.strip() and not line.strip().startswith('#')]
    if real and all(line.strip() == 'pass' for line in real):
        body = [line for line in body if line.strip() != 'pass']
    out = src[:start + 1] + body + ['    ' + line if line else '' for line in lines] + src[last + 1:]
    return '\n'.join(out)
