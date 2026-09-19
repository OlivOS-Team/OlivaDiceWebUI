"""Number and publish successful main-branch builds as GitHub Releases."""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from zipfile import ZipFile


MANIFEST_PATH = 'app.json'
ARCHIVE_SPECS = {
    'OlivaDiceWebUI': ('OlivaDiceWebUI', 'OlivaDice WebUI（官方接入版）'),
    'OlivaDiceWebUIStandalone': (
        'OlivaDiceWebUIStandalone', 'OlivaDice WebUI（独立服务版）'),
}


def beijing_day(now=None):
    return (now or datetime.now(ZoneInfo('Asia/Shanghai'))).astimezone(
        ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d')


def next_build_number(refs, day):
    pattern = re.compile(r'^refs/tags/v' + re.escape(day) + r'\(([1-9]\d*)\)$')
    numbers = [int(match.group(1)) for ref in refs if (match := pattern.fullmatch(ref))]
    return max(numbers, default=0) + 1


def identify_archive(source):
    with ZipFile(source) as archive:
        if MANIFEST_PATH not in archive.namelist():
            raise ValueError('Plugin archive must contain app.json at its root')
        manifest = json.loads(archive.read(MANIFEST_PATH))
    namespace = manifest.get('namespace')
    if namespace not in ARCHIVE_SPECS:
        raise ValueError('Unknown plugin namespace: {}'.format(namespace))
    base_name, label = ARCHIVE_SPECS[namespace]
    return namespace, base_name, label


def stamp_archive(source, version):
    """Return a fixed-name OPK whose manifest contains the exact release version."""
    if not re.fullmatch(r'\d{8}\([1-9]\d*\)', version):
        raise ValueError('Invalid release version: {}'.format(version))
    _, base_name, _ = identify_archive(source)
    # The asset label carries the timestamped version while downloads keep this stable filename.
    target = source.with_name('{}.opk'.format(base_name))
    temporary = target.with_name(target.name + '.tmp')
    found_manifest = False
    try:
        with ZipFile(source) as original, ZipFile(temporary, 'w') as stamped:
            for item in original.infolist():
                data = original.read(item.filename)
                if item.filename == MANIFEST_PATH:
                    manifest = json.loads(data)
                    manifest['version'] = version
                    data = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
                    found_manifest = True
                stamped.writestr(item, data)
        if not found_manifest:
            raise ValueError('Plugin archive is missing {}'.format(MANIFEST_PATH))
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def gh(*args, check=True):
    result = subprocess.run(('gh',) + args, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result


def reserve_tag(repo, sha, day):
    refs = gh('api', 'repos/{}/git/matching-refs/tags/v{}'.format(repo, day),
              '--paginate', '--jq', '.[].ref').stdout.splitlines()
    number = next_build_number(refs, day)
    while True:
        tag = 'v{}({})'.format(day, number)
        created = gh('api', '-X', 'POST', 'repos/{}/git/refs'.format(repo),
                     '-f', 'ref=refs/tags/' + tag, '-f', 'sha=' + sha, check=False)
        if created.returncode == 0:
            return tag
        # Another run may have claimed this number after the listing.
        existing = gh('api', 'repos/{}/git/ref/tags/{}'.format(repo, tag), check=False)
        if existing.returncode:
            raise RuntimeError(created.stderr.strip() or created.stdout.strip())
        number += 1


def main():
    sources = [Path(value) for value in sys.argv[1:]]
    if len(sources) != len(ARCHIVE_SPECS):
        raise SystemExit('Usage: publish_release.py <official.opk> <standalone.opk>')
    for source in sources:
        if not source.is_file():
            raise SystemExit('Package not found: {}'.format(source))
    identified = [(source, identify_archive(source)) for source in sources]
    namespaces = {spec[0] for _, spec in identified}
    if namespaces != set(ARCHIVE_SPECS):
        raise SystemExit('Both official and standalone plugin archives are required')
    repo = os.environ['GITHUB_REPOSITORY']
    sha = os.environ['GITHUB_SHA']
    tag = reserve_tag(repo, sha, beijing_day())
    labelled_assets = []
    for source, (_, _, label) in identified:
        asset = stamp_archive(source, tag[1:])
        labelled_assets.append('{}#{} {}'.format(asset, label, tag))
    released = gh('release', 'create', tag, *labelled_assets, '--repo', repo,
                  '--verify-tag', '--generate-notes', '--latest')
    print(released.stdout.strip())


if __name__ == '__main__':
    main()
