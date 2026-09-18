"""Build the installable OlivOS plugin archive from this repository."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'OlivaDiceWebUI'
VERSION = __import__('json').loads((PLUGIN / 'app.json').read_text(encoding='utf-8'))['version']
ARCHIVE = ROOT / 'dist' / ('OlivaDiceWebUI-{}.zip'.format(VERSION))

if not (PLUGIN / 'web' / 'olivadice.html').is_file():
    raise SystemExit('Missing frontend build: cd frontend && npm ci && npm run build')

ARCHIVE.parent.mkdir(exist_ok=True)
with ZipFile(ARCHIVE, 'w', compression=ZIP_DEFLATED, compresslevel=9) as bundle:
    for source in sorted(PLUGIN.rglob('*')):
        if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc' and source.name != '.DS_Store':
            bundle.write(source, source.relative_to(ROOT))
    for name in ('README.md', 'LICENSE'):
        bundle.write(ROOT / name, 'OlivaDiceWebUI/' + name)

print(ARCHIVE)
