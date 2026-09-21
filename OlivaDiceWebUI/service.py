"""Validated, narrow access to the live OlivaDiceCore state."""

import copy
import datetime
import importlib.util
import json
import re
import threading
from pathlib import Path

LOCK = threading.RLock()
REPLY_NOTES = json.loads(Path(__file__).with_name('reply_notes.json').read_text(encoding='utf-8'))
SWITCH_NOTES = json.loads(Path(__file__).with_name('switch_notes.json').read_text(encoding='utf-8'))

# Section, label, lower bound, upper bound, description. Keep aligned with
# OlivaDiceCore.console.dictConsoleSwitchTemplate rather than duplicating state.
SWITCHES = {
    'globalEnable': ('运行', '全局开关', 0, 1, ''),
    'userConfigCount': ('运行', '用户记录刷写计数', 1, 100000, ''),
    'pulseInterval': ('运行', '心跳间隔（秒）', 1, 86400, ''),
    'autoAcceptGroupAdd': ('接入', '自动同意入群邀请', 0, 1, ''),
    'autoAcceptFriendAdd': ('接入', '自动同意好友请求', 0, 1, ''),
    'recordBotJoinGroup': ('接入', '记录机器人入群', 0, 1, ''),
    'disableReplyPrivate': ('接入', '关闭私聊回复', 0, 1, ''),
    'disablePrivate': ('接入', '关闭私聊处理', 0, 1, ''),
    'messageFliterMode': ('消息', '消息过滤模式', 0, 3, ''),
    'messageSplitGate': ('消息', '消息分页阈值', 1, 100000, '超过此长度时分页'),
    'messageSplitPageLimit': ('消息', '最多分页数', 1, 1000, ''),
    'messageSplitDelay': ('消息', '分页间隔（毫秒）', 0, 60000, ''),
    'messageSplitAutoShowPage': ('消息', '自动显示分页', 0, 1, ''),
    'messageSplitManualShowPage': ('消息', '手动显示分页', 0, 1, ''),
    'largeRollLimit': ('掷骰', '大规模掷骰上限', 1, 100000, ''),
    'multiRollDetail': ('掷骰', '显示多轮掷骰详情', 0, 1, ''),
    'randomMode': ('掷骰', '随机模式', 0, 1, ''),
    'drawRecommendMode': ('牌堆与帮助', '抽牌推荐模式', 0, 1, ''),
    'drawListMode': ('牌堆与帮助', '牌堆列表模式', 0, 3, ''),
    'helpRecommendGate': ('牌堆与帮助', '帮助推荐阈值', 0, 100000, ''),
    'censorMode': ('内容与默认值', '内容审查模式', 0, 1, ''),
    'censorMatchMode': ('内容与默认值', '内容审查匹配模式', 0, 1, ''),
    'defaultShowDefault': ('内容与默认值', '默认显示技能值', 0, 1, ''),
    'defaultAutoSn': ('内容与默认值', '默认自动群名片', 0, 1, ''),
    'portEnable': ('导入导出', '启用端口功能', 0, 1, ''),
    'portCodeTTL': ('导入导出', '端口验证码有效期（秒）', 0, 2592000, ''),
    'portSplitGate': ('导入导出', '端口分页阈值', 1, 100000, ''),
    'portExportFileLimit': ('导入导出', '端口导出文件上限', -100000, 1000, ''),
}


class InvalidInput(ValueError):
    pass


def _core():
    import OlivaDiceCore
    return OlivaDiceCore


def _bots(proc):
    return proc.Proc_data.get('bot_info_dict', {})


def _check_account(proc, bot_hash, allow_unity=True):
    if not isinstance(bot_hash, str) or (bot_hash != 'unity' and bot_hash not in _bots(proc)) or (bot_hash == 'unity' and not allow_unity):
        raise InvalidInput('账号不存在')


def _save_value(mapping, key, value, save):
    old = copy.deepcopy(mapping[key])
    mapping[key] = value
    try:
        save()
    except Exception:
        mapping[key] = old
        raise
    return value


def _content_hash(core, bot_hash):
    user_config = getattr(core, 'userConfig', None)
    if user_config is None:
        return bot_hash
    redirected = user_config.getRedirectedBotHash(bot_hash)
    return redirected if isinstance(redirected, str) else bot_hash


def accounts(proc):
    with LOCK:
        result = [{'hash': 'unity', 'label': '全局设置', 'platform': 'global', 'model': '', 'id': 'unity'}]
        for bot_hash, info in _bots(proc).items():
            platform = getattr(info, 'platform', {}) or {}
            name = str(platform.get('platform', '未知平台'))
            model = str(platform.get('model', ''))
            bot_id = str(getattr(info, 'id', bot_hash))
            result.append({'hash': bot_hash, 'label': '{} · {}'.format(name, bot_id),
                           'platform': name, 'model': model, 'id': bot_id})
        return result


def switches(proc, bot_hash):
    _check_account(proc, bot_hash)
    with LOCK:
        console = _core().console
        values = console.dictConsoleSwitch.get(bot_hash, {})
        template = console.dictConsoleSwitchTemplate.get('default', {})
        result = [{'key': key, 'section': section, 'label': label, 'value': values[key],
                 'min': minimum, 'max': maximum, 'description': description or SWITCH_NOTES.get(key, '')}
                for key, (section, label, minimum, maximum, description) in SWITCHES.items()
                if key in values and type(values[key]) is int]
        result.extend({'key': key, 'section': '插件配置', 'label': key, 'value': value,
                       'min': -2147483648, 'max': 2147483647,
                       'description': SWITCH_NOTES.get(key, '运行中的扩展配置项'), 'custom': key not in template}
                      for key, value in values.items() if key not in SWITCHES and type(value) is int)
        return result


def set_switch(proc, bot_hash, key, value):
    _check_account(proc, bot_hash)
    if type(value) is not int:
        raise InvalidInput('设置值必须是整数')
    with LOCK:
        console = _core().console
        values = console.dictConsoleSwitch.get(bot_hash, {})
        if key not in values or type(values[key]) is not int:
            raise InvalidInput('此账号缺少设置项')
        minimum, maximum = (SWITCHES[key][2:4] if key in SWITCHES else (-2147483648, 2147483647))
        if not minimum <= value <= maximum:
            raise InvalidInput('设置值超出允许范围')
        return _save_value(values, key, value, console.saveConsoleSwitch)


def replies(proc, bot_hash):
    _check_account(proc, bot_hash, False)
    with LOCK:
        core = _core()
        values = core.msgCustom.dictStrCustomDict.get(bot_hash, {})
        updates = core.msgCustom.dictStrCustomUpdateDict.get(bot_hash, {})
        from . import gui_parity
        defaults = gui_parity._reply_defaults(proc, bot_hash)
        return [{'key': key, 'value': value, 'note': REPLY_NOTES.get(key, ''), 'modified': key in updates,
                 'default': defaults.get(key) if isinstance(defaults.get(key), str) else None}
                for key, value in values.items() if isinstance(key, str) and isinstance(value, str)]


def set_reply(proc, bot_hash, key, value=None, reset=False):
    _check_account(proc, bot_hash, False)
    if not isinstance(key, str) or (not reset and not isinstance(value, str)):
        raise InvalidInput('回复键和值必须是文本')
    if not reset and len(value) > 20000:
        raise InvalidInput('回复内容过长')
    with LOCK:
        core = _core()
        current = core.msgCustom.dictStrCustomDict.get(bot_hash, {})
        if key not in current or not isinstance(current[key], str):
            raise InvalidInput('回复键不存在')
        changes = core.msgCustom.dictStrCustomUpdateDict.setdefault(bot_hash, {})
        original = current[key]
        old_changes = changes.copy()
        if reset:
            from . import gui_parity
            default = gui_parity._reply_defaults(proc, bot_hash).get(key)
            if not isinstance(default, str):
                raise InvalidInput('此回复没有可恢复的默认值')
            current[key] = default
            changes.pop(key, None)
        else:
            current[key] = value
            changes[key] = value
        try:
            core.msgCustomManager.saveMsgCustomByBotHash(bot_hash)
        except Exception:
            current[key] = original
            changes.clear()
            changes.update(old_changes)
            raise
        return current[key]


def masters(proc, bot_hash):
    _check_account(proc, bot_hash, False)
    with LOCK:
        values = _core().console.dictConsoleSwitch.get(bot_hash, {})
        return [{'id': str(pair[0]), 'platform': str(pair[1])} for pair in values.get('masterList', [])
                if isinstance(pair, (list, tuple)) and len(pair) == 2]


def change_master(proc, bot_hash, action, master_id):
    _check_account(proc, bot_hash, False)
    if action not in ('add', 'remove') or not isinstance(master_id, str) or not master_id.isdecimal() or len(master_id) > 32:
        raise InvalidInput('请输入有效的数字骰主 ID')
    with LOCK:
        console = _core().console
        values = console.dictConsoleSwitch.get(bot_hash, {})
        if not isinstance(values.get('masterList'), list):
            raise InvalidInput('此账号没有骰主列表')
        existing = [pair for pair in values['masterList']
                    if not isinstance(pair, (list, tuple)) or not pair or str(pair[0]) != master_id]
        if action == 'add':
            info = _bots(proc)[bot_hash]
            platform = str((getattr(info, 'platform', {}) or {}).get('platform', ''))
            existing.append([master_id, platform])
        _save_value(values, 'masterList', existing, console.saveConsoleSwitch)
        return masters(proc, bot_hash)


def relations(proc):
    with LOCK:
        if not _master_installed(proc):
            return {'available': False, 'accountHashes': [], 'relations': []}
        console = _core().console
        current = console.getAllAccountRelations()
        known = set(_bots(proc)) | set(console.dictConsoleSwitch)
        known.update(master for master in current if isinstance(master, str))
        known.update(slave for slaves in current.values() if isinstance(slaves, list)
                     for slave in slaves if isinstance(slave, str))
        return {'available': True, 'accountHashes': sorted(known - {'unity'}), 'relations': [
            {'master': master, 'slave': slave}
            for master, slaves in current.items() if isinstance(slaves, list)
            for slave in slaves
            if isinstance(master, str) and isinstance(slave, str)
        ]}


def change_relation(proc, action, slave, master=None):
    if action not in ('link', 'unlink'):
        raise InvalidInput('账号关系操作无效')
    if not _master_installed(proc):
        raise InvalidInput('需要 OlivaDiceMaster 才能管理账号关系')
    with LOCK:
        if action == 'link':
            known = set(relations(proc)['accountHashes'])
            if (not isinstance(slave, str) or not isinstance(master, str)
                    or slave not in known or master not in known):
                raise InvalidInput('主账号或从账号不在已保存的账号列表中')
            if master == slave:
                raise InvalidInput('主从账号不能相同')
        if action == 'unlink':
            if not isinstance(slave, str) or not slave or not any(
                    isinstance(slaves, list) and slave in slaves
                    for slaves in _core().console.getAllAccountRelations().values()):
                raise InvalidInput('账号关系不存在，请刷新后重试')
        import OlivaDiceMaster
        if action == 'link':
            ok, message = OlivaDiceMaster.accountManager.linkAccount(slave, master, None)
        else:
            ok, message = OlivaDiceMaster.accountManager.unlinkAccount(slave, None, None)
        if not ok:
            raise InvalidInput(message)
        return relations(proc)


def help_docs(proc, bot_hash):
    _check_account(proc, bot_hash, False)
    with LOCK:
        core = _core()
        data = getattr(core, 'helpDocData', None)
        if data is None:
            return []
        content_hash = _content_hash(core, bot_hash)
        values = data.dictHelpDoc.get(content_hash, {})
        custom = data.dictHelpDocDefault.get(content_hash, {})
        return [{'key': key, 'value': value, 'custom': key in custom}
                for key, value in values.items() if isinstance(key, str) and isinstance(value, str)]


def set_help_doc(proc, bot_hash, key, value=None, delete=False):
    _check_account(proc, bot_hash, False)
    if not isinstance(key, str) or not key.strip() or len(key) > 100 or (not delete and (not isinstance(value, str) or len(value) > 20000)):
        raise InvalidInput('帮助词条格式无效')
    with LOCK:
        core = _core()
        if not hasattr(core, 'helpDocData') or not hasattr(core, 'helpDoc'):
            raise InvalidInput('帮助文档未加载')
        custom = core.helpDocData.dictHelpDocDefault.get(_content_hash(core, bot_hash), {})
        if delete:
            if key not in custom:
                raise InvalidInput('只能删除自定义词条')
            core.helpDoc.delHelpDocByBotHash(bot_hash, key)
            return None
        core.helpDoc.setHelpDocByBotHash(bot_hash, key.strip(), value)
        return value


def _deck_aliases(name):
    """Return the names Core may derive from a deck filename.

    Older Core releases use ``rstrip`` for extensions, so keep the historical
    spelling in addition to the normal stem when matching a loaded index.
    """
    value = Path(name).name
    lowered = value.lower()
    aliases = {value, Path(value).stem}
    for extension in ('.json5', '.json', '.yaml', '.yml', '.xlsx', '.xls'):
        if lowered.endswith(extension):
            aliases.add(value.rstrip(extension))
    return {item.casefold() for item in aliases if item}


def _matching_deck(index, filename):
    aliases = _deck_aliases(filename)
    for name, groups in index.items():
        if isinstance(name, str) and isinstance(groups, list) and name.casefold() in aliases:
            return name, groups
    return None


def _global_deck_index(proc, data):
    """Read global deck entries, including compatibility with older Core builds."""
    indexes = getattr(data, 'dictDeckIndex', {})
    direct = indexes.get('unity', {})
    result = dict(direct) if isinstance(direct, dict) else {}
    root = Path(_core().data.dataDirRoot) / 'unity' / 'extend'
    for folder, extensions in (('deckclassic', {'.json', '.json5'}),
                               ('deckyaml', {'', '.yaml', '.yml'}),
                               ('deckexcel', {'.xlsx', '.xls'})):
        location = root / folder
        if not location.is_dir():
            continue
        for path in location.iterdir():
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue
            for bot_hash in _bots(proc):
                index = indexes.get(_content_hash(_core(), bot_hash), {})
                if not isinstance(index, dict):
                    continue
                match = _matching_deck(index, path.name)
                if match:
                    result.setdefault(match[0], match[1])
                    break
    return result


def decks(proc, bot_hash):
    _check_account(proc, bot_hash)
    with LOCK:
        core = _core()
        data = getattr(core, 'drawCardData', None)
        if data is None:
            return []
        content_hash = _content_hash(core, bot_hash)
        loaded = getattr(data, 'dictDeck', {}).get(content_hash, {})
        builtins = getattr(data, 'dictDeckTemp', {})
        builtin_groups = [name for name in builtins
                          if isinstance(name, str) and isinstance(loaded.get(name), list)]
        result = ([{'name': '内置牌堆', 'groups': builtin_groups, 'count': len(builtin_groups)}]
                  if builtin_groups else [])
        index = (_global_deck_index(proc, data) if bot_hash == 'unity'
                 else getattr(data, 'dictDeckIndex', {}).get(content_hash, {}))
        result.extend({'name': name, 'groups': groups, 'count': len(groups)}
                      for name, groups in index.items() if isinstance(name, str) and isinstance(groups, list))
        return result


def deck_group_count(proc, bot_hash):
    _check_account(proc, bot_hash)
    with LOCK:
        core = _core()
        data = getattr(core, 'drawCardData', None)
        if data is None:
            return 0
        if bot_hash == 'unity':
            return len({group for deck in decks(proc, bot_hash) for group in deck['groups']})
        loaded = getattr(data, 'dictDeck', {}).get(_content_hash(core, bot_hash), {})
        return sum(isinstance(name, str) and isinstance(cards, list)
                   for name, cards in loaded.items())


def reload_decks(proc):
    with LOCK:
        core = _core()
        if not hasattr(core, 'drawCard'):
            raise InvalidInput('牌堆模块未加载')
        core.drawCard.reloadDeck()
        return True


def _master_installed(proc):
    try:
        return 'OlivaDiceMaster' in proc.get_plugin_list()
    except (AttributeError, TypeError):
        return importlib.util.find_spec('OlivaDiceMaster') is not None


def backup(proc):
    with LOCK:
        values = getattr(_core().console, 'dictBackupConfig', {}).get('unity', {})
        return {'available': _master_installed(proc), 'settings': {key: values.get(key) for key in
                ('isBackup', 'startDate', 'passDay', 'backupTime', 'maxBackupCount')}}


def set_backup(proc, settings):
    if not _master_installed(proc):
        raise InvalidInput('需要安装 OlivaDiceMaster 才能启用备份')
    if not isinstance(settings, dict):
        raise InvalidInput('备份配置格式错误')
    required = ('isBackup', 'startDate', 'passDay', 'backupTime', 'maxBackupCount')
    if any(key not in settings for key in required) or any(key not in required for key in settings):
        raise InvalidInput('备份配置不完整')
    if type(settings['isBackup']) is not int or settings['isBackup'] not in (0, 1):
        raise InvalidInput('备份开关无效')
    if type(settings['passDay']) is not int or not 1 <= settings['passDay'] <= 365:
        raise InvalidInput('备份间隔须为 1–365 天')
    if type(settings['maxBackupCount']) is not int or not 1 <= settings['maxBackupCount'] <= 100:
        raise InvalidInput('保留数量须为 1–100')
    if not isinstance(settings['startDate'], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', settings['startDate']):
        raise InvalidInput('开始日期格式应为 YYYY-MM-DD')
    try:
        datetime.date.fromisoformat(settings['startDate'])
    except ValueError:
        raise InvalidInput('开始日期无效') from None
    if not isinstance(settings['backupTime'], str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d', settings['backupTime']):
        raise InvalidInput('备份时间格式应为 HH:MM:SS')
    with LOCK:
        console = _core().console
        values = console.dictBackupConfig.get('unity', {})
        if not values:
            raise InvalidInput('备份模块尚未初始化')
        old = values.copy()
        values.update(settings)
        try:
            console.saveBackupConfig()
        except Exception:
            values.clear()
            values.update(old)
            raise
        return backup(proc)
