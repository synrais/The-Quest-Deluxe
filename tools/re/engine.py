"""Which port the verifiers check: quest2 (the classic port, the default) or, with
QUEST_ENGINE=deluxe, Quest Deluxe playing packs/quest1. Import this before anything from quest2:

    QUEST_ENGINE=deluxe python verify_events.py

It registers the deluxe modules under the quest2 names, so the verifiers run unchanged.
"""
import importlib
import os
import pkgutil
import sys

NAME = os.environ.get('QUEST_ENGINE', 'quest2')
if NAME != 'quest2':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    pkg = importlib.import_module(NAME)
    sys.modules['quest2'] = pkg
    for m in pkgutil.iter_modules(pkg.__path__):
        sys.modules[f'quest2.{m.name}'] = importlib.import_module(f'{NAME}.{m.name}')
