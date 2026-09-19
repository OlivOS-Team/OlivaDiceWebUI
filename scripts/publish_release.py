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


def beijing_day(now=None):
    return (now or datetime.now(ZoneInfo('Asia/Shanghai'))).astimezone(
        ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d')


def next_build_number(refs, day):
    pattern = re.compile(r'^refs/tags/v' + re.escape(day) + r'\(([1-9]\d*)\)$')
    numbers = [int(match.group(1)) for ref in refs if (match := pattern.fullmatch(ref))]
    return max(numbers, default=0) + 1


def stamp_archive(source, version):
    """Return a ZIP with a GitHub-safe name and the exact plugin version."""
    match = re.fullmatch(r'(\d{8})\(([1-9]\d*)\)', version)
    if not match:
        raise ValueError('Invalid release version: {}'.format(version))
    # GitHub normalizes parentheses in uploaded asset filenames to periods.
    target = source.with_name('OlivaDiceWebUIStandalone-{}.{}.zip'.format(*match.groups()))
    temporary = target.with_suffix('.zip.tmp')
    found_manifest = False
    try:
        with ZipFile(source) as original, ZipFile(temporary, 'w') as stamped:
            for item in original.infolist():
                data = original.read(item.filename)
                if item.filename == 'OlivaDiceWebUIStandalone/app.json':
                    manifest = json.loads(data)
                    manifest['version'] = version
                    data = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
                    found_manifest = True
                stamped.writestr(item, data)
        if not found_manifest:
            raise ValueError('Plugin archive is missing OlivaDiceWebUIStandalone/app.json')
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
    if len(sys.argv) != 2:
        raise SystemExit('Usage: publish_release.py dist/OlivaDiceWebUIStandalone-<version>.zip')
    source = Path(sys.argv[1])
    if not source.is_file():
        raise SystemExit('Package not found: {}'.format(source))
    repo = os.environ['GITHUB_REPOSITORY']
    sha = os.environ['GITHUB_SHA']
    tag = reserve_tag(repo, sha, beijing_day())
    asset = stamp_archive(source, tag[1:])
    labelled_asset = '{}#OlivaDiceWebUIStandalone {}'.format(asset, tag)
    released = gh('release', 'create', tag, labelled_asset, '--repo', repo,
                  '--verify-tag', '--generate-notes', '--latest')
    print(released.stdout.strip())


if __name__ == '__main__':
    main()
