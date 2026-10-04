"""Your additions kept off to the side (editor/side_save.py) and the recovery of pictures without entries (recover.py).

    python tests/test_side_save.py
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from editor import pack_edits, recover, side_save  # noqa: E402
from editor.project import Project  # noqa: E402


def game():
    """A copy of the game folder (engine not needed): packs and the baseline."""
    tmp = tempfile.mkdtemp()
    deluxe = os.path.join(tmp, 'TheQuestDeluxe')
    shutil.copytree(os.path.join(ROOT, 'packs'), os.path.join(deluxe, 'packs'))
    os.makedirs(os.path.join(deluxe, 'editor'))
    return tmp, deluxe


def load(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def main():
    tmp, deluxe = game()
    shipped = os.path.join(deluxe, 'packs', 'TheQuest')
    saved = os.path.join(tmp, 'saved')
    assert side_save.save_zip(deluxe, saved)[0] is None, 'nothing added: nothing kept'

    # his additions: a new creature, a changed item, a new picture and a new map tile layout
    cr = load(os.path.join(shipped, 'creatures.json'))
    cr['creatures'].append({'id': 150, 'name': 'Bro Beast', 'life': 99})
    json.dump(cr, open(os.path.join(shipped, 'creatures.json'), 'w'))
    it = load(os.path.join(shipped, 'items.json'))
    it['items'][0]['name'] = 'His Own Name'
    json.dump(it, open(os.path.join(shipped, 'items.json'), 'w'))
    shutil.copy(os.path.join(shipped, 'sprites', 'creatures', '1.png'), os.path.join(shipped, 'sprites', 'creatures', '150.png'))
    first_id = it['items'][0]['id']

    path, report = side_save.save_zip(deluxe, saved, when=1760000000)
    assert path and os.path.basename(path).startswith('QuestEdits_2025-10-09_')
    meta = side_save.read_meta(path)
    assert meta['complete'] and [r['id'] for r in meta['delta']['creatures.json']['creatures']['rows']] == [150]
    assert [r['id'] for r in meta['delta']['items.json']['items']['rows']] == [first_id]
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    assert 'TheQuestDeluxe/packs/TheQuest/sprites/creatures/150.png' in names and 'tables_full/creatures.json' in names
    assert len(side_save.saved_zips(saved)) == 1
    again, _ = side_save.save_zip(deluxe, saved, when=1760000100)       # nothing new: no second copy of the same
    assert len(side_save.saved_zips(saved)) == 1 and again == path
    cr['creatures'][-1]['life'] = 100                                   # an edit: another zip, the first one left as it was
    json.dump(cr, open(os.path.join(shipped, 'creatures.json'), 'w'))
    second, _ = side_save.save_zip(deluxe, saved, when=1760000200)
    assert second != path and os.path.exists(path) and len(side_save.saved_zips(saved)) == 2
    assert side_save.saved_zips(saved)[0] == second

    # a new game is dragged over his: the shipped tables and baseline come back, his pictures are not touched
    tmp2, fresh = game()
    shutil.copytree(os.path.join(shipped, 'sprites', 'creatures'), os.path.join(fresh, 'packs', 'TheQuest', 'sprites', 'creatures'),
                    dirs_exist_ok=True)                                # his picture stayed
    assert not any(r['id'] == 150 for r in load(os.path.join(fresh, 'packs', 'TheQuest', 'creatures.json'))['creatures'])
    todo = side_save.apply(fresh, path)
    assert any('creatures' in t and '150' in t for t in todo) and any('His Own Name' in t for t in todo), todo
    assert side_save.apply(fresh, path, write=True) == todo
    now = load(os.path.join(fresh, 'packs', 'TheQuest', 'creatures.json'))
    assert any(r['id'] == 150 and r['name'] == 'Bro Beast' for r in now['creatures'])
    assert load(os.path.join(fresh, 'packs', 'TheQuest', 'items.json'))['items'][0]['name'] == 'His Own Name'
    assert side_save.apply(fresh, path) == [], 'put back: nothing more to do'
    Project(os.path.join(fresh, 'packs', 'TheQuest'))                  # and it still loads as a pack

    # a zip from the old tool (no side_save.json, whole tables): only the missing rows come back
    old = os.path.join(tmp, 'old.zip')
    with zipfile.ZipFile(old, 'w') as z:
        z.writestr('TheQuestDeluxe/packs/TheQuest/creatures.json', json.dumps(cr))
    tmp3, again = game()
    todo = side_save.apply(again, old, write=True)
    assert todo and any(r['id'] == 150 for r in load(os.path.join(again, 'packs', 'TheQuest', 'creatures.json'))['creatures'])

    # pictures without an entry
    tmp4, lost = game()
    pack = os.path.join(lost, 'packs', 'TheQuest')
    cr = load(os.path.join(pack, 'creatures.json'))
    gone = [r['id'] for r in cr['creatures'] if r['id'] > 0][-2:]
    cr['creatures'] = [r for r in cr['creatures'] if r['id'] not in gone]
    json.dump(cr, open(os.path.join(pack, 'creatures.json'), 'w'))
    project = Project(pack)
    found = recover.orphans(project)
    assert sorted(found['creatures']) == sorted(gone), found
    made = recover.recover(project)
    assert len(made) >= 2 and not recover.orphans(project)
    assert any(r['id'] == gone[0] and r['name'].startswith('Recovered') for r in project.tables['creatures'])
    project.save()
    assert any(r['id'] == gone[0] for r in load(os.path.join(pack, 'creatures.json'))['creatures'])
    print('side save: a zip kept off to the side on every save, put back after an update, pictures without entries recovered: ok')


if __name__ == '__main__':
    main()
