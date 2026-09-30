"""Which port the verifiers check: the classic port (engine/, the default) or, with
QUEST_ENGINE=deluxe, The Quest Deluxe (../../../TheQuestDeluxe) playing its packs/TheQuest. Import
this before anything from engine:

    QUEST_ENGINE=deluxe python verify_events.py

It registers the deluxe modules under the engine names, so the verifiers run unchanged.
"""
import importlib
import importlib.util
import os
import pkgutil
import sys

NAME = os.environ.get('QUEST_ENGINE', 'engine')
if NAME != 'engine':
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    sys.path.insert(0, os.path.join(repo, 'TheQuestDeluxe'))
    pkg = importlib.import_module(NAME)
    sys.modules['engine'] = pkg
    for m in pkgutil.iter_modules(pkg.__path__):
        sys.modules[f'engine.{m.name}'] = importlib.import_module(f'{NAME}.{m.name}')
    # the verifiers read the original's files (fonts, data) with the classic port's DataSource,
    # which The Quest Deluxe, standing alone, doesn't have: lend it the classic one
    spec = importlib.util.spec_from_file_location(
        'classic_formats', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                        'engine', 'formats.py'))
    classic_formats = sys.modules['classic_formats'] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(classic_formats)
    sys.modules['engine.formats'].DataSource = classic_formats.DataSource
