"""Which port the verifiers check: quest2 (the classic port, the default) or, with
QUEST_ENGINE=deluxe, Quest Deluxe (../../../deluxe) playing its packs/quest1. Import this before anything from quest2:

    QUEST_ENGINE=deluxe python verify_events.py

It registers the deluxe modules under the quest2 names, so the verifiers run unchanged.
"""
import importlib
import importlib.util
import os
import pkgutil
import sys

NAME = os.environ.get('QUEST_ENGINE', 'quest2')
if NAME != 'quest2':
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    sys.path.insert(0, os.path.join(repo, 'deluxe'))
    pkg = importlib.import_module(NAME)
    sys.modules['quest2'] = pkg
    for m in pkgutil.iter_modules(pkg.__path__):
        sys.modules[f'quest2.{m.name}'] = importlib.import_module(f'{NAME}.{m.name}')
    # the verifiers read the original's files (fonts, data) with the classic port's DataSource,
    # which Quest Deluxe, standing alone, doesn't have: lend it the classic one
    spec = importlib.util.spec_from_file_location(
        'classic_formats', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                        'quest2', 'formats.py'))
    classic_formats = sys.modules['classic_formats'] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(classic_formats)
    sys.modules['quest2.formats'].DataSource = classic_formats.DataSource
