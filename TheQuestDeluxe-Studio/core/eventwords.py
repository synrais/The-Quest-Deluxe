"""The words of the event builder: when something happens, only if, then (the keys event_code.py writes as script lines)."""
from __future__ import annotations

WHENS = [('talk', 'the hero talks to a person'), ('dies', 'a creature dies'),
         ('arrive', 'the hero arrives on the level'), ('chest', 'the hero opens a chest'),
         ('took', 'the hero picks up an item')]
CONDITIONS = [('m1', 'quest counter 1 is'), ('m2', 'quest counter 2 is'), ('has', 'the hero has the item'),
              ('hasnt', 'the hero has not the item'), ('rep', "the hero's reputation is at least"),
              ('coins', 'the hero has at least this much gold')]
ACTIONS = [('say', 'the person says a message'), ('message', 'show a message from a person'),
           ('give', 'give the hero an item'), ('take', 'take an item from the hero'),
           ('drop', 'put an item on the ground here'), ('coins', 'give the hero gold (a minus takes it)'),
           ('rep', 'change the hero\'s reputation by'), ('m1', 'set quest counter 1 to'),
           ('m2', 'set quest counter 2 to'), ('next', 'send the hero to the next level')]
NEEDS_ITEM = {'has', 'hasnt', 'give', 'take', 'drop'}
NEEDS_NUMBER = {'m1', 'm2', 'rep', 'coins'}
