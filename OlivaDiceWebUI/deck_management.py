"""Cross-platform deck file and Extiverse operations."""

import io
import os
import re
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from . import service

KINDS = {
    'classic': ('deckclassic', {'.json', '.json5'}),
    'yaml': ('deckyaml', {'', '.yaml', '.yml'}),
    'excel': ('deckexcel', {'.xlsx', '.xls'}),
}
MAX_DECK_BYTES = 12 * 1024 * 1024


def _scope(proc, bot):
    service._check_account(proc, bot)
    return bot


def _filename(name):
    if not isinstance(name, str) or not name or len(name) > 180 or name in ('.', '..') or '..' in name or any(char in name for char in '/\\\0:'):
        raise service.InvalidInput('牌堆文件名无效')
    return name


def _folder(bot, kind):
    if kind not in KINDS:
        raise service.InvalidInput('牌堆类型无效')
    return Path(service._core().data.dataDirRoot) / bot / 'extend' / KINDS[kind][0]


def deck_files(proc, bot):
    _scope(proc, bot)
    with service.LOCK:
        results = []
        for kind in KINDS:
            folder = _folder(bot, kind)
            if not folder.is_dir():
                continue
            for path in folder.iterdir():
                if path.is_file() and path.suffix.lower() in KINDS[kind][1]:
                    groups = _loaded_groups(proc, bot, path.name)
                    results.append({'name': path.name, 'kind': kind, 'size': path.stat().st_size,
                                    'scope': bot, 'loaded': groups is not None,
                                    'groupCount': len(groups or [])})
        return sorted(results, key=lambda item: item['name'].lower())


def deck_folder(proc, bot):
    _scope(proc, bot)
    return str(Path(service._core().data.dataDirRoot) / bot / 'extend')


def _target(bot, kind, name):
    _filename(name)
    if kind not in KINDS or Path(name).suffix.lower() not in KINDS[kind][1]:
        raise service.InvalidInput('牌堆文件类型与扩展名不匹配')
    return _folder(bot, kind) / name


def _loaded_groups(proc, bot, name):
    core = service._core()
    data = getattr(core, 'drawCardData', None)
    if data is None:
        return None
    indexes = getattr(data, 'dictDeckIndex', {})
    targets = ['unity'] if bot == 'unity' else [service._content_hash(core, bot)]
    if bot == 'unity':
        targets.extend(service._content_hash(core, item) for item in service._bots(proc))
    for target in targets:
        index = indexes.get(target, {})
        if isinstance(index, dict):
            match = service._matching_deck(index, name)
            if match and match[1]:
                return match[1]
    return None


def install_file(proc, bot, kind, name, raw, verify=False):
    _scope(proc, bot)
    target = _target(bot, kind, name)
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_DECK_BYTES:
        raise service.InvalidInput('牌堆文件为空或超过 12 MiB')
    if kind == 'excel' and target.suffix.lower() == '.xlsx' and not raw.startswith(b'PK'):
        raise service.InvalidInput('XLSX 文件格式无效')
    with service.LOCK:
        core = service._core()
        target.parent.mkdir(parents=True, exist_ok=True)
        old = target.read_bytes() if target.exists() else None
        temporary = target.with_name(target.name + '.webui-upload')
        try:
            temporary.write_bytes(raw)
            os.replace(temporary, target)
            core.drawCard.reloadDeck()
            groups = _loaded_groups(proc, bot, name)
            if verify and not groups:
                raise service.InvalidInput('下载内容不是可加载的牌堆，已自动回滚')
        except Exception:
            temporary.unlink(missing_ok=True)
            if old is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(old)
            try:
                core.drawCard.reloadDeck()
            except Exception:
                pass
            raise
        return {'name': name, 'kind': kind, 'scope': bot, 'groups': groups or []}


def remove_file(proc, bot, kind, name):
    _scope(proc, bot)
    target = _target(bot, kind, name)
    with service.LOCK:
        if not target.is_file():
            raise service.InvalidInput('牌堆文件不存在')
        old = target.read_bytes()
        target.unlink()
        try:
            service._core().drawCard.reloadDeck()
        except Exception:
            target.write_bytes(old)
            raise
        return True


def _odyssey(proc):
    try:
        available = 'OlivaDiceOdyssey' in proc.get_plugin_list()
    except (AttributeError, TypeError):
        available = False
    if not available:
        return None
    import OlivaDiceOdyssey
    return OlivaDiceOdyssey


def _entry_catalog(data):
    result = []
    if not isinstance(data, dict):
        return result
    for kind in KINDS:
        entries = data.get(kind, [])
        if not isinstance(entries, list):
            continue
        for item in entries:
            if isinstance(item, dict) and isinstance(item.get('name'), str):
                result.append({'name': item['name'], 'kind': kind, 'author': str(item.get('author', '')),
                               'version': str(item.get('version', '')), 'description': str(item.get('desc', ''))})
    return result


def market(proc, refresh=False):
    odyssey = _odyssey(proc)
    if odyssey is None:
        return {'available': False, 'decks': []}
    import requests
    with service.LOCK:
        cached = odyssey.webTool.gExtiverseDeck
    if refresh or not isinstance(cached, dict) or not cached:
        url = odyssey.cnmodsData.strExtiverseDeckMain
        response = requests.get(url, timeout=15, proxies=service._core().webTool.get_system_proxy(),
                                headers={'User-Agent': service._core().data.bot_version_short_header})
        response.raise_for_status()
        cached = response.json()
        if not isinstance(cached, dict):
            raise service.InvalidInput('牌堆市场响应无效')
        with service.LOCK:
            odyssey.webTool.gExtiverseDeck = cached
    return {'available': True, 'decks': _entry_catalog(cached)}


def _safe_url(url):
    if not isinstance(url, str) or urlsplit(url).scheme != 'https' or not urlsplit(url).netloc:
        raise service.InvalidInput('牌堆市场下载地址无效')
    return url


def _download(url, maximum):
    import requests
    core = service._core()
    data = bytearray()
    with requests.get(_safe_url(url), timeout=30, stream=True,
                      proxies=core.webTool.get_system_proxy(),
                      headers={'User-Agent': core.data.bot_version_short_header}) as response:
        response.raise_for_status()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > maximum:
                raise service.InvalidInput('下载内容过大')
    return bytes(data)


def _safe_resources(raw):
    resources = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        if len(infos) > 1000 or sum(info.file_size for info in infos) > 100 * 1024 * 1024:
            raise service.InvalidInput('牌堆资源包过大')
        for info in infos:
            if info.is_dir():
                continue
            normalized = info.filename.replace('\\', '/')
            path = Path(normalized)
            if path.is_absolute() or '..' in path.parts or ':' in normalized or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise service.InvalidInput('牌堆资源包包含不安全路径')
            resources.append((path, archive.read(info)))
    return resources


def market_install(proc, bot, kind, name):
    _scope(proc, bot)
    _filename(name)
    if kind not in KINDS:
        raise service.InvalidInput('牌堆类型无效')
    odyssey = _odyssey(proc)
    if odyssey is None:
        raise service.InvalidInput('需要 OlivaDiceOdyssey 才能安装市场牌堆')
    catalog = odyssey.webTool.gExtiverseDeck
    entries = catalog.get(kind, []) if isinstance(catalog, dict) else []
    if not isinstance(entries, list):
        entries = []
    entry = next((item for item in entries if isinstance(item, dict) and item.get('name') == name), None)
    if entry is None or not isinstance(entry.get('download_link'), list):
        raise service.InvalidInput('请先刷新市场并选择有效牌堆')
    links = entry['download_link']
    if not links:
        raise service.InvalidInput('此牌堆没有下载地址')
    last_error = None
    result = None
    ext = {'classic': '.json', 'yaml': '.yaml', 'excel': '.xlsx'}[kind]
    for link in links[:5]:
        try:
            data = _download(link, MAX_DECK_BYTES)
            result = install_file(proc, bot, kind, name + ext, data, verify=True)
            break
        except Exception as exc:
            last_error = exc
    if result is None:
        raise service.InvalidInput('牌堆下载或加载失败：{}'.format(last_error))
    resource_files = []
    for url in entry.get('resource_link', [])[:5] if isinstance(entry.get('resource_link'), list) else []:
        resource_files.extend(_safe_resources(_download(url, 30 * 1024 * 1024)))
    with service.LOCK:
        root = Path('data')
        for relative, content in resource_files:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return result
