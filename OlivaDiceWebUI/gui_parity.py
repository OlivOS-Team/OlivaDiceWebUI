"""Operations that mirror the native GUI without depending on Tk or local dialogs."""

import copy
import datetime
import importlib
import io
import json
import re
import tempfile
import zipfile
from pathlib import Path

from . import service

DEFAULT_RECOVER_MODULES = [
    'OlivaDiceCore', 'OlivaDiceJoy', 'OlivaDiceMaster',
    'OlivaDiceLogger', 'OlivaDiceOdyssey', 'OlivaStoryCore',
]
LIST_KEYS = {'masterList', 'noticeGroupList', 'pulseUrlList'}


def _data_file(bot, filename):
    return Path(service._core().data.dataDirRoot) / bot / 'console' / filename


def _json_dict(data, kind):
    if not isinstance(data, dict) or len(data) > 5000:
        raise service.InvalidInput(f'{kind}必须是 JSON 对象')
    return data


def _pairs(value, key):
    if not isinstance(value, list) or len(value) > 1000:
        raise service.InvalidInput(f'{key} 必须是列表')
    for pair in value:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2 or any(not isinstance(v, str) or len(v) > 2048 for v in pair):
            raise service.InvalidInput(f'{key} 的每项必须是两个文本值')
    return value


def _config_value(key, value, current):
    if key in service.SWITCHES:
        if type(value) is not int:
            raise service.InvalidInput(f'{key} 必须是整数')
        _, _, minimum, maximum, _ = service.SWITCHES[key]
        if not minimum <= value <= maximum:
            raise service.InvalidInput(f'{key} 超出允许范围')
    elif key in LIST_KEYS:
        _pairs(value, key)
    elif key in current:
        previous = current[key]
        if type(previous) is int:
            if type(value) is not int or not -2147483648 <= value <= 2147483647:
                raise service.InvalidInput(f'{key} 必须是 32 位整数')
        elif type(previous) is str:
            if not isinstance(value, str) or len(value) > 20000:
                raise service.InvalidInput(f'{key} 必须是文本')
        else:
            raise service.InvalidInput(f'不支持导入配置项：{key}')
    else:
        raise service.InvalidInput(f'当前运行环境不存在配置项：{key}')
    return value


def config_snapshot(proc, bot):
    service._check_account(proc, bot)
    with service.LOCK:
        return copy.deepcopy(service._core().console.dictConsoleSwitch.get(bot, {}))


def config_apply(proc, bot, action, data=None, key=None):
    service._check_account(proc, bot)
    with service.LOCK:
        core = service._core()
        console = core.console
        current = console.dictConsoleSwitch.get(bot)
        if not isinstance(current, dict):
            raise service.InvalidInput('此账号没有配置')
        old = copy.deepcopy(current)
        template = copy.deepcopy(console.dictConsoleSwitchTemplate['default'])
        if action == 'import':
            incoming = _json_dict(data, '配置')
            for name, value in incoming.items():
                _config_value(name, value, current)
            next_config = copy.deepcopy(current)
            next_config.update(copy.deepcopy(incoming))
        elif action == 'reset':
            next_config = template
            next_config['masterList'] = copy.deepcopy(current.get('masterList', []))
        elif action == 'reset-key':
            next_config = copy.deepcopy(current)
            if key in template:
                next_config[key] = copy.deepcopy(template[key])
            elif key in current and type(current[key]) is int:
                del next_config[key]
            else:
                raise service.InvalidInput('配置项不存在或不能恢复')
        elif action == 'reload':
            path = _data_file(bot, 'switch.json')
            incoming = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
            _json_dict(incoming, '配置')
            for name, value in incoming.items():
                _config_value(name, value, current)
            next_config = template
            next_config.update(incoming)
            next_config['masterList'] = copy.deepcopy(current.get('masterList', []))
        elif action == 'set-list':
            if key not in LIST_KEYS:
                raise service.InvalidInput('不是列表配置项')
            next_config = copy.deepcopy(current)
            next_config[key] = _pairs(data, key)
        else:
            raise service.InvalidInput('配置操作无效')
        console.dictConsoleSwitch[bot] = next_config
        try:
            console.saveConsoleSwitch()
        except Exception:
            console.dictConsoleSwitch[bot] = old
            raise
        return copy.deepcopy(next_config)


def recover_modules(proc, bot, modules=None):
    service._check_account(proc, bot, False)
    path = _data_file(bot, 'recover_model.json')
    with service.LOCK:
        if modules is None:
            if not path.is_file():
                return DEFAULT_RECOVER_MODULES.copy()
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                values = data.get('modules')
                return values if isinstance(values, list) and all(isinstance(item, str) for item in values) and values else DEFAULT_RECOVER_MODULES.copy()
            except (ValueError, OSError, AttributeError):
                return DEFAULT_RECOVER_MODULES.copy()
        if not isinstance(modules, list) or len(modules) > 50 or any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,99}', name) for name in modules):
            raise service.InvalidInput('恢复模块列表格式无效')
        clean = modules or DEFAULT_RECOVER_MODULES.copy()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'modules': clean}, ensure_ascii=False, indent=2), encoding='utf-8')
        return clean


def _reply_defaults(proc, bot):
    defaults = {}
    available = set(proc.get_plugin_list()) if hasattr(proc, 'get_plugin_list') else {'OlivaDiceCore'}
    for name in recover_modules(proc, bot):
        if name not in available:
            continue
        try:
            module = importlib.import_module(name)
            values = getattr(getattr(module, 'msgCustom', None), 'dictStrCustom', {})
            if isinstance(values, dict):
                defaults.update({key: value for key, value in values.items() if isinstance(key, str) and isinstance(value, str)})
        except (ImportError, AttributeError):
            continue
    return defaults


def replies_snapshot(proc, bot):
    service._check_account(proc, bot, False)
    with service.LOCK:
        return copy.deepcopy(service._core().msgCustom.dictStrCustomDict.get(bot, {}))


def replies_apply(proc, bot, action, data=None, key=None, value=None):
    service._check_account(proc, bot, False)
    with service.LOCK:
        core = service._core()
        current = core.msgCustom.dictStrCustomDict.get(bot)
        if not isinstance(current, dict):
            raise service.InvalidInput('此账号没有回复词')
        updates = core.msgCustom.dictStrCustomUpdateDict.setdefault(bot, {})
        old, old_updates = copy.deepcopy(current), copy.deepcopy(updates)
        defaults = _reply_defaults(proc, bot)
        custom_existing = {name: text for name, text in current.items() if name not in defaults}
        if action == 'import':
            incoming = _json_dict(data, '回复词')
            if any(not isinstance(k, str) or len(k) > 200 or not isinstance(v, str) or len(v) > 20000 for k, v in incoming.items()):
                raise service.InvalidInput('回复词键或内容格式无效')
            next_values = {**defaults, **custom_existing}
            next_values.update(incoming)
            next_updates = {**custom_existing, **incoming}
        elif action == 'reset':
            next_values = {**defaults, **custom_existing}
            next_updates = custom_existing
        elif action == 'reload':
            path = _data_file(bot, 'customReply.json')
            incoming = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
            _json_dict(incoming, '回复词')
            if any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 20000 for k, v in incoming.items()):
                raise service.InvalidInput('回复词文件格式无效')
            next_values = {**defaults, **custom_existing}
            next_values.update(incoming)
            next_updates = {**custom_existing, **incoming}
        elif action == 'add':
            if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,199}', key) or key in current or not isinstance(value, str) or len(value) > 20000:
                raise service.InvalidInput('自定义回复键或内容无效')
            next_values = dict(current, **{key: value})
            next_updates = dict(updates, **{key: value})
        elif action == 'delete':
            if key not in current or key in defaults:
                raise service.InvalidInput('只能删除自定义回复词')
            next_values = dict(current)
            next_updates = dict(updates)
            next_values.pop(key)
            next_updates.pop(key, None)
        else:
            raise service.InvalidInput('回复词操作无效')
        core.msgCustom.dictStrCustomDict[bot] = next_values
        core.msgCustom.dictStrCustomUpdateDict[bot] = next_updates
        try:
            core.msgCustomManager.saveMsgCustomByBotHash(bot)
        except Exception:
            core.msgCustom.dictStrCustomDict[bot] = old
            core.msgCustom.dictStrCustomUpdateDict[bot] = old_updates
            raise
        return copy.deepcopy(next_values)


def backup_apply(proc, action, data=None, key=None):
    if not service._master_installed(proc):
        raise service.InvalidInput('需要 OlivaDiceMaster 才能管理备份')
    with service.LOCK:
        console = service._core().console
        current = console.dictBackupConfig.get('unity', {})
        template = copy.deepcopy(console.dictBackupConfigTemplate['default'])
        if not template.get('startDate'):
            template['startDate'] = datetime.date.today().isoformat()
        if action == 'import':
            incoming = _json_dict(data, '备份配置')
            next_values = dict(current, **incoming)
        elif action == 'reset':
            next_values = template
        elif action == 'reset-key':
            if key not in template:
                raise service.InvalidInput('备份配置项没有默认值')
            next_values = dict(current, **{key: template[key]})
        elif action == 'reload':
            path = _data_file('unity', 'backup.json')
            incoming = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
            next_values = dict(template, **_json_dict(incoming, '备份配置'))
        else:
            raise service.InvalidInput('备份操作无效')
        # Use the same validation as the ordinary backup form.
        validated = service.set_backup(proc, {name: next_values.get(name) for name in ('isBackup', 'startDate', 'passDay', 'backupTime', 'maxBackupCount')})
        return validated


def master_command():
    key = service._core().data.bot_content.get('masterKey')
    return '.master {}'.format(key) if isinstance(key, str) and key else None


def account_copy(proc, source, target):
    service._check_account(proc, source, False)
    service._check_account(proc, target, False)
    if source == target or not service._master_installed(proc):
        raise service.InvalidInput('请选择不同的源账号和目标账号，并加载 OlivaDiceMaster')
    with service.LOCK:
        import OlivaDiceMaster
        ok, message = OlivaDiceMaster.accountManager.importAccountData(source, target, proc)
        if not ok:
            raise service.InvalidInput(message)
        return message


def account_export(proc, bot):
    service._check_account(proc, bot, False)
    if not service._master_installed(proc):
        raise service.InvalidInput('需要 OlivaDiceMaster 才能导出账号')
    with service.LOCK:
        import OlivaDiceMaster
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'account.zip'
            ok, message = OlivaDiceMaster.accountManager.exportAccountData(bot, proc, str(path))
            if not ok:
                raise service.InvalidInput(message)
            if path.stat().st_size > 100 * 1024 * 1024:
                raise service.InvalidInput('账号压缩包超过 100 MiB')
            return path.read_bytes()


def _check_zip(raw):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > 10000 or sum(item.file_size for item in entries) > 1024 * 1024 * 1024:
                raise service.InvalidInput('压缩包内容过大')
            for item in entries:
                parts = Path(item.filename.replace('\\', '/')).parts
                if not parts or '..' in parts or ':' in item.filename or item.filename.startswith(('/', '\\')) or (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise service.InvalidInput('压缩包包含不安全路径或链接')
    except zipfile.BadZipFile:
        raise service.InvalidInput('不是有效的 ZIP 压缩包') from None


def account_import(proc, bot, source, raw):
    service._check_account(proc, bot, False)
    if not service._master_installed(proc):
        raise service.InvalidInput('需要 OlivaDiceMaster 才能导入账号')
    if not isinstance(source, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', source) or source == 'unity':
        raise service.InvalidInput('请输入压缩包原账号的 Hash')
    _check_zip(raw)
    with service.LOCK:
        import OlivaDiceMaster
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'account.zip'
            path.write_bytes(raw)
            ok, message, _ = OlivaDiceMaster.accountManager.importAccountDataFromZip(str(path), bot, proc, sourceBotHash=source)
            if not ok:
                raise service.InvalidInput(message)
            return message
