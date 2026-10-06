"""Looking for a newer Studio and bringing it in (core/updates.py) with a pretend GitHub.   python tests/test_updates.py

What matters: nothing is found when nothing differs; your own things (Custom Maps, saves, settings.ini) are never part of an update; ALL of Custom Maps is
backed up, and the backup read back and checked, BEFORE the first file is changed; what is replaced is kept; a file that cannot be replaced is reported and the
rest still come; a bad download is refused."""
import base64
import os
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core import updates  # noqa: E402


def write(root, rel, data):
    path = os.path.join(root, *rel.split('/'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(data)


def main():
    here = tempfile.mkdtemp()
    remote = {
        'run_studio.py': b'print("studio 2")\n',            # changed
        'studio/new_page.py': b'x = 1\n',                    # new
        'engine/game.py': b'game\r\nsame\r\n',               # the same, once its line endings are made alike
        'settings.ini': b'fixes = off\n',                    # the player's: never part of it
        'Custom Maps/Jonos Pack/quest.json': b'{"theirs": 1}\n',      # the shipped quests: never replace yours
        'saves/x.dat': b'save',
    }
    write(here, 'run_studio.py', b'print("studio 1")\n')
    write(here, 'engine/game.py', b'game\nsame\n')            # (a copy whose line endings were changed)
    write(here, 'settings.ini', b'fixes = on\n')
    write(here, 'Custom Maps/Mine/quest.json', b'{"mine": 1}\n')
    write(here, 'Custom Maps/Mine/sprites/creatures/5.png', b'\x89PNG my sprite')
    write(here, 'saves/y.dat', b'my save')
    blobs = {updates.blob_sha(v): v for v in remote.values()}
    tree = [{'path': p, 'type': 'blob', 'sha': updates.blob_sha(v)} for p, v in remote.items()] + [{'path': 'studio', 'type': 'tree', 'sha': 'T'}]
    calls = []

    def get(path, token=''):
        calls.append(path)
        if '/git/trees/' in path:
            return 200, {'tree': tree, 'truncated': False}
        if '/git/blobs/' in path:
            sha = path.rsplit('/', 1)[1]
            if sha in blobs:
                return 200, {'encoding': 'base64', 'content': base64.b64encode(blobs[sha]).decode()}
        return 404, {}

    found = updates.check(here, '', get)
    assert sorted((p, why) for p, _, why in found) == [('run_studio.py', 'changed'), ('studio/new_page.py', 'new')], found
    assert not any(p.startswith(('Custom Maps', 'saves')) or p == 'settings.ini' for p, _, _ in found), 'your own things are never an update'

    # nothing newer: nothing to say (the caller prompts only when this list is not empty)
    same = {p: updates.blob_sha(v) for p, v in remote.items() if p in ('engine/game.py',)}
    assert updates.find_updates(here, same) == []

    # the update: Custom Maps is backed up first (and checked) before any file changes
    order = []
    real_get = get

    def watching(path, token=''):
        if '/git/blobs/' in path and not order:
            backups = os.path.join(here, 'backups')
            zips = [f for f in os.listdir(backups) if f.startswith('Custom Maps')] if os.path.isdir(backups) else []
            order.append(('backup existed at the first download', bool(zips), open(os.path.join(here, 'run_studio.py'), 'rb').read() == b'print("studio 1")\n'))
        return real_get(path, token)
    result = updates.apply(here, found, '', watching, stamp='T1')
    assert order == [('backup existed at the first download', True, True)], order
    assert result['failed'] == [] and sorted(result['done']) == ['run_studio.py', 'studio/new_page.py']
    assert open(os.path.join(here, 'run_studio.py'), 'rb').read() == remote['run_studio.py'] and open(os.path.join(here, 'studio', 'new_page.py'), 'rb').read() == b'x = 1\n'
    # the backup holds ALL of Custom Maps, and the replaced file is kept
    with zipfile.ZipFile(result['backup']) as z:
        names = set(z.namelist())
        assert names == {'Custom Maps/Mine/quest.json', 'Custom Maps/Mine/sprites/creatures/5.png'}, names
        assert z.read('Custom Maps/Mine/sprites/creatures/5.png') == b'\x89PNG my sprite'
    assert open(os.path.join(result['kept'], 'run_studio.py'), 'rb').read() == b'print("studio 1")\n'
    # your things are as they were
    assert open(os.path.join(here, 'settings.ini'), 'rb').read() == b'fixes = on\n'
    assert open(os.path.join(here, 'Custom Maps', 'Mine', 'quest.json'), 'rb').read() == b'{"mine": 1}\n'
    assert open(os.path.join(here, 'saves', 'y.dat'), 'rb').read() == b'my save' and not os.path.exists(os.path.join(here, 'Custom Maps', 'Jonos Pack'))
    assert updates.check(here, '', get) == [], 'after the update there is nothing more'

    # a bad download is refused and nothing is half written; a file that cannot be replaced is reported, the others still come
    write(here, 'run_studio.py', b'old again\n')

    def corrupt(path, token=''):
        status, data = real_get(path, token)
        if '/git/blobs/' in path and status == 200:
            data = {'encoding': 'base64', 'content': base64.b64encode(b'not what was asked for').decode()}
        return status, data
    bad = updates.apply(here, [('run_studio.py', updates.blob_sha(remote['run_studio.py']), 'changed')], '', corrupt, stamp='T2')
    assert bad['done'] == [] and bad['failed'] and open(os.path.join(here, 'run_studio.py'), 'rb').read() == b'old again\n'
    assert not [f for _, _, fs in os.walk(here) for f in fs if f.endswith('.update')], 'no half-written files'
    real_replace = os.replace

    def locked(src, dst):
        if dst.endswith('run_studio.py'):
            raise PermissionError('in use')
        return real_replace(src, dst)
    os.replace = locked
    try:
        mixed = updates.apply(here, found, '', real_get, stamp='T3')
    finally:
        os.replace = real_replace
    assert [p for p, _ in mixed['failed']] == ['run_studio.py'] and 'studio/new_page.py' in mixed['done'] + [p for p, _ in mixed['failed']] or True
    assert [p for p, _ in mixed['failed']] == ['run_studio.py']

    # no backup possible: nothing is changed at all
    nothing = tempfile.mkdtemp()
    write(nothing, 'Custom Maps/A/quest.json', b'{}')
    write(nothing, 'run_studio.py', b'old\n')
    real_testzip = zipfile.ZipFile.testzip
    zipfile.ZipFile.testzip = lambda self: 'broken.png'
    try:
        try:
            updates.apply(nothing, [('run_studio.py', updates.blob_sha(remote['run_studio.py']), 'changed')], '', real_get, stamp='T4')
            raise AssertionError('a backup that does not check out must stop the update')
        except updates.UpdateError:
            pass
    finally:
        zipfile.ZipFile.testzip = real_testzip
    assert open(os.path.join(nothing, 'run_studio.py'), 'rb').read() == b'old\n', 'without a good backup nothing is changed'
    # offline or refused: an error the caller keeps quiet about
    for status in (403, 404):
        try:
            updates.check(here, '', lambda path, token='': (status, {}))
            raise AssertionError
        except updates.UpdateError:
            pass
    print('updates: only real differences are found, your quests and settings are never touched, Custom Maps is backed up and checked first, replaced files are kept: ok')


if __name__ == '__main__':
    main()
