"""Validated management adapter for the optional ChanceCustom plugin.

ChanceCustom keeps its live configuration in ``ChanceCustom.load.dictCustomData``.
The adapter deliberately works through that object and its save hook so edits take
effect immediately and remain compatible with the plugin's desktop configuration UI.
"""

import copy
import hashlib
import importlib
import io
import json
import re
import threading
import zipfile

from . import service


DATA_VERSION = 2
MAX_RULES = 10000
MAX_TEXT = 20000
MAX_PACKAGE_BYTES = 8 * 1024 * 1024
DEFAULT_KEYS = ('一天上限', '一周上限', '一月上限', '一次间隔', '回复间隔', '权限限制')
DEFAULT_LABELS = {
    '一天上限': '达到每日上限',
    '一周上限': '达到每周上限',
    '一月上限': '达到每月上限',
    '一次间隔': '单次触发冷却',
    '回复间隔': '回复间隔冷却',
    '权限限制': '权限不足',
}
MATCH_TYPES = {'full', 'contain', 'perfix', 'reg'}
MATCH_PLACES = {'1', '2', '3'}
_lock = threading.RLock()


def _plugin_loaded(proc):
    try:
        return 'ChanceCustom' in proc.get_plugin_list()
    except Exception:
        return False


def _module(proc, required=True):
    if not _plugin_loaded(proc):
        if required:
            raise service.InvalidInput('需要安装并加载 ChanceCustom 才能管理程心自定义')
        return None
    try:
        module = importlib.import_module('ChanceCustom')
    except (ImportError, AttributeError):
        if required:
            raise service.InvalidInput('ChanceCustom 已登记，但运行模块不可用，请检查插件日志') from None
        return None
    load = getattr(module, 'load', None)
    if load is None or not isinstance(getattr(load, 'dictCustomData', None), dict):
        if required:
            raise service.InvalidInput('ChanceCustom 尚未完成配置初始化')
        return None
    return module


def _version(module):
    value = getattr(getattr(module, 'main', None), 'version', '')
    return str(value or '')


def _state(module):
    value = module.load.dictCustomData
    version = value.get('dataVersion')
    if isinstance(version, bool) or not isinstance(version, int):
        raise service.InvalidInput('ChanceCustom 配置缺少有效的数据版本')
    if version != DATA_VERSION:
        raise service.InvalidInput('暂不支持 ChanceCustom 数据版本 {}，当前仅支持版本 {}'.format(
            version, DATA_VERSION))
    for key in ('data', 'defaultVar', 'ccpkList'):
        if not isinstance(value.get(key), dict):
            raise service.InvalidInput('ChanceCustom 配置中的 {} 结构无效'.format(key))
    return value


def _scope(value, bot):
    if not isinstance(bot, str) or not bot or len(bot) > 256:
        raise service.InvalidInput('请选择有效的配置范围')
    rules = value['data'].get(bot, {})
    defaults = value['defaultVar'].get(bot, {})
    packages = value['ccpkList'].get(bot, {})
    if not isinstance(rules, dict) or not isinstance(defaults, dict) or not isinstance(packages, dict):
        raise service.InvalidInput('ChanceCustom 当前范围的数据结构无效')
    return rules, defaults, packages


def _revision(rules, defaults, packages):
    raw = json.dumps([rules, defaults, packages], ensure_ascii=False, sort_keys=True,
                     separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:20]


def _text(value, label, maximum=MAX_TEXT, allow_empty=True):
    if not isinstance(value, str):
        raise service.InvalidInput('{}必须是文本'.format(label))
    value = value.strip() if label in ('关键词', '包名称') else value
    if not allow_empty and not value:
        raise service.InvalidInput('{}不能为空'.format(label))
    if len(value) > maximum:
        raise service.InvalidInput('{}不能超过 {} 个字符'.format(label, maximum))
    return value


def _validate_rule(value):
    if not isinstance(value, dict):
        raise service.InvalidInput('回复规则格式无效')
    key = _text(value.get('key'), '关键词', 500, False)
    division = _text(str(value.get('division', '1')), '分群/分人', 4000)
    match_type = value.get('matchType')
    match_place = str(value.get('matchPlace', ''))
    priority = value.get('priority')
    reply = _text(value.get('value'), '回复内容')
    if match_type not in MATCH_TYPES:
        raise service.InvalidInput('匹配方式无效')
    if match_place not in MATCH_PLACES:
        raise service.InvalidInput('触发场景无效')
    if isinstance(priority, bool) or not isinstance(priority, int) or not -1000000000 <= priority <= 1000000000:
        raise service.InvalidInput('优先级必须是 -1000000000 到 1000000000 的整数')
    if match_type == 'reg':
        try:
            re.compile('^{}$'.format(key))
        except re.error as exc:
            raise service.InvalidInput('正则表达式无效：{}'.format(exc)) from None
    return {'key': key, 'division': division, 'matchType': match_type,
            'matchPlace': match_place, 'priority': priority, 'value': reply}


def _package_info(value):
    if not isinstance(value, dict):
        raise service.InvalidInput('回复包信息无效')
    return {
        'name': _text(value.get('name'), '包名称', 200, False),
        'author': _text(value.get('author', ''), '作者', 200),
        'version': _text(str(value.get('version', '')), '版本', 100),
        'info': _text(value.get('info', ''), '说明', 10000),
    }


def _validate_package(value):
    if not isinstance(value, dict) or value.get('type') != 'ccpk' or value.get('dataVersion') != DATA_VERSION:
        raise service.InvalidInput('仅支持数据版本 2 的 CCPK 回复包')
    info = _package_info(value.get('info'))
    rules = value.get('data')
    if not isinstance(rules, dict) or len(rules) > MAX_RULES:
        raise service.InvalidInput('回复包规则列表无效或数量过多')
    checked = {}
    for stored_key, rule in rules.items():
        item = _validate_rule(rule)
        if not isinstance(stored_key, str) or stored_key != item['key']:
            raise service.InvalidInput('回复包中的规则键与关键词不一致')
        checked[stored_key] = item
    return {'type': 'ccpk', 'dataVersion': DATA_VERSION, 'info': info, 'data': checked}


def _package_summary(name, value):
    info = value.get('info', {}) if isinstance(value, dict) else {}
    data = value.get('data', {}) if isinstance(value, dict) else {}
    return {'name': str(name), 'author': str(info.get('author', '')),
            'version': str(info.get('version', '')), 'description': str(info.get('info', '')),
            'ruleCount': len(data) if isinstance(data, dict) else 0}


def snapshot(proc, bot):
    module = _module(proc, required=False)
    if module is None:
        return {'available': False, 'version': '', 'dataVersion': None, 'revision': '',
                'rules': [], 'defaults': [], 'packages': [],
                'reason': 'OlivOS 当前未加载 ChanceCustom 插件。'}
    with _lock:
        try:
            value = _state(module)
            rules, defaults, packages = _scope(value, bot)
        except service.InvalidInput as exc:
            return {'available': True, 'writable': False, 'version': _version(module),
                    'dataVersion': module.load.dictCustomData.get('dataVersion'), 'revision': '',
                    'rules': [], 'defaults': [], 'packages': [], 'reason': str(exc)}
        rule_list = []
        for stored_key, raw in rules.items():
            if not isinstance(raw, dict):
                continue
            item = copy.deepcopy(raw)
            item['key'] = str(item.get('key', stored_key))
            item['division'] = str(item.get('division', '1'))
            item['matchType'] = str(item.get('matchType', 'full'))
            item['matchPlace'] = str(item.get('matchPlace', '3'))
            try:
                item['priority'] = int(item.get('priority', 0))
            except (TypeError, ValueError):
                item['priority'] = 0
            item['value'] = str(item.get('value', ''))
            rule_list.append(item)
        rule_list.sort(key=lambda item: (-item['priority'], item['key']))
        global_defaults = value['defaultVar'].get('unity', {})
        default_list = []
        for key in DEFAULT_KEYS:
            own = str(defaults.get(key, ''))
            inherited = str(global_defaults.get(key, '')) if isinstance(global_defaults, dict) else ''
            default_list.append({'key': key, 'label': DEFAULT_LABELS[key], 'value': own,
                                 'effective': own if bot == 'unity' or own else inherited,
                                 'inherited': bot != 'unity' and not own})
        return {'available': True, 'writable': True, 'version': _version(module),
                'dataVersion': value['dataVersion'], 'revision': _revision(rules, defaults, packages),
                'rules': rule_list, 'defaults': default_list,
                'packages': [_package_summary(name, package)
                             for name, package in sorted(packages.items())], 'reason': ''}


def _mutate(proc, bot, expected_revision, callback):
    module = _module(proc)
    with _lock:
        value = _state(module)
        rules, defaults, packages = _scope(value, bot)
        if expected_revision and expected_revision != _revision(rules, defaults, packages):
            raise service.InvalidInput('配置已被其他窗口修改，请刷新后重试')
        before = copy.deepcopy(value)
        value['data'].setdefault(bot, rules)
        value['defaultVar'].setdefault(bot, defaults)
        value['ccpkList'].setdefault(bot, packages)
        try:
            result = callback(value['data'][bot], value['defaultVar'][bot], value['ccpkList'][bot])
            module.load.saveCustomData()
        except service.InvalidInput:
            value.clear()
            value.update(before)
            raise
        except Exception:
            value.clear()
            value.update(before)
            raise service.InvalidInput('ChanceCustom 保存失败，请查看 OlivOS 日志') from None
        return result


def change_rule(proc, bot, action, rule=None, original_key=None, revision=''):
    if action not in ('create', 'update', 'delete'):
        raise service.InvalidInput('规则操作无效')
    checked = _validate_rule(rule) if action != 'delete' else None
    if action == 'create' and len(checked['value']) < 2:
        raise service.InvalidInput('新增规则的回复内容至少需要 2 个字符')
    if original_key is not None:
        original_key = _text(original_key, '关键词', 500, False)

    def apply(rules, _defaults, _packages):
        if action == 'create':
            if checked['key'] in rules:
                raise service.InvalidInput('同名关键词已经存在')
            if len(rules) >= MAX_RULES:
                raise service.InvalidInput('回复规则数量已达到上限')
            rules[checked['key']] = checked
        elif action == 'update':
            if original_key not in rules:
                raise service.InvalidInput('原回复规则不存在，请刷新后重试')
            if checked['key'] != original_key and checked['key'] in rules:
                raise service.InvalidInput('新关键词与已有规则重名')
            rules.pop(original_key)
            rules[checked['key']] = checked
        else:
            if original_key not in rules:
                raise service.InvalidInput('回复规则不存在，请刷新后重试')
            rules.pop(original_key)
        return checked['key'] if checked else original_key

    return _mutate(proc, bot, revision, apply)


def set_defaults(proc, bot, values, revision=''):
    if not isinstance(values, dict) or set(values) != set(DEFAULT_KEYS):
        raise service.InvalidInput('默认回复字段不完整')
    checked = {key: _text(values[key], DEFAULT_LABELS[key]) for key in DEFAULT_KEYS}

    def apply(_rules, defaults, _packages):
        defaults.update(checked)
        return copy.deepcopy(checked)

    return _mutate(proc, bot, revision, apply)


def import_package(proc, bot, filename, raw, revision=''):
    if not isinstance(filename, str) or not filename.lower().endswith('.ccpk'):
        raise service.InvalidInput('请选择 .ccpk 回复包')
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_PACKAGE_BYTES:
        raise service.InvalidInput('CCPK 文件为空或超过 8 MiB')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = [item for item in archive.infolist() if not item.is_dir()]
            if len(entries) != 1 or entries[0].filename.replace('\\', '/') != 'data.json':
                raise service.InvalidInput('CCPK 必须只包含根目录下的 data.json')
            entry = entries[0]
            if entry.flag_bits & 1 or entry.file_size > MAX_PACKAGE_BYTES:
                raise service.InvalidInput('CCPK 已加密或解压后过大')
            payload = json.loads(archive.read(entry).decode('utf-8'))
    except service.InvalidInput:
        raise
    except (OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile):
        raise service.InvalidInput('CCPK 文件损坏或 data.json 格式无效') from None
    package = _validate_package(payload)

    def apply(rules, _defaults, packages):
        if len(set(rules) | set(package['data'])) > MAX_RULES:
            raise service.InvalidInput('安装后回复规则数量会超过 {} 条'.format(MAX_RULES))
        rules.update(copy.deepcopy(package['data']))
        packages[package['info']['name']] = copy.deepcopy(package)
        return package['info']['name']

    return _mutate(proc, bot, revision, apply)


def manage_package(proc, bot, action, name, revision=''):
    if action not in ('uninstall', 'unbind', 'reinstall'):
        raise service.InvalidInput('回复包操作无效')
    name = _text(name, '包名称', 200, False)

    def apply(rules, _defaults, packages):
        package = packages.get(name)
        if not isinstance(package, dict):
            raise service.InvalidInput('回复包不存在，请刷新后重试')
        package = _validate_package(package)
        package_rules = package.get('data', {})
        retained = []
        installed = 0
        if action == 'uninstall':
            for key, original in package_rules.items():
                if key in rules and rules[key] == original:
                    rules.pop(key)
                elif key in rules:
                    retained.append(key)
            packages.pop(name)
        elif action == 'unbind':
            packages.pop(name)
        else:
            missing = [key for key in package_rules if key not in rules]
            if len(rules) + len(missing) > MAX_RULES:
                raise service.InvalidInput('重新安装后回复规则数量会超过 {} 条'.format(MAX_RULES))
            for key, original in package_rules.items():
                if key not in rules:
                    rules[key] = copy.deepcopy(original)
                    installed += 1
        return {'name': name, 'retained': retained, 'installed': installed}

    return _mutate(proc, bot, revision, apply)


def export_package(proc, bot, spec):
    if not isinstance(spec, dict):
        raise service.InvalidInput('导出参数无效')
    module = _module(proc)
    with _lock:
        value = _state(module)
        rules, _defaults, _packages = _scope(value, bot)
        keys = spec.get('keys')
        if not isinstance(keys, list) or not keys or len(keys) > MAX_RULES:
            raise service.InvalidInput('请至少选择一条回复规则')
        if len(set(keys)) != len(keys) or any(not isinstance(key, str) or key not in rules for key in keys):
            raise service.InvalidInput('导出规则列表包含无效项目')
        package = {'type': 'ccpk', 'dataVersion': DATA_VERSION,
                   'info': _package_info(spec.get('info')),
                   'data': {key: copy.deepcopy(rules[key]) for key in keys}}
        raw_json = json.dumps(package, ensure_ascii=False, indent=4).encode('utf-8')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('data.json', raw_json)
        filename = re.sub(r'[^\w.()-]+', '_', package['info']['name'], flags=re.UNICODE).strip('._')
        return stream.getvalue(), '{}.ccpk'.format(filename or 'ChanceCustom')
