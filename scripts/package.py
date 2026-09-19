"""Build both installable OlivOS plugin editions from the shared source tree."""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
OFFICIAL = ROOT / 'OlivaDiceWebUI'
STANDALONE = ROOT / 'OlivaDiceWebUIStandalone'
SHARED_FILES = (
    'deck_management.py',
    'gui_parity.py',
    'reply_notes.json',
    'service.py',
    'switch_notes.json',
)


def version(plugin):
    return json.loads((plugin / 'app.json').read_text(encoding='utf-8'))['version']


def included(source):
    return (source.is_file() and '__pycache__' not in source.parts
            and source.suffix != '.pyc' and source.name != '.DS_Store')


def build_archive(plugin, install_name, web_dir, shared_files=()):
    if not (plugin / web_dir / 'olivadice.html').is_file():
        raise SystemExit('Missing {} frontend build: npm run build --prefix frontend'.format(install_name))
    target = DIST / '{}-{}.opk'.format(install_name, version(plugin))
    with ZipFile(target, 'w', compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        for source in sorted(plugin.rglob('*')):
            if included(source):
                bundle.write(source, source.relative_to(plugin))
        for name in shared_files:
            bundle.write(OFFICIAL / name, name)
        for name in ('README.md', 'LICENSE'):
            bundle.write(ROOT / name, name)
    return target


def main():
    DIST.mkdir(exist_ok=True)
    return (
        build_archive(OFFICIAL, 'OlivaDiceWebUI', 'webui'),
        build_archive(STANDALONE, 'OlivaDiceWebUIStandalone', 'web', SHARED_FILES),
    )


if __name__ == '__main__':
    for archive in main():
        print(archive)
