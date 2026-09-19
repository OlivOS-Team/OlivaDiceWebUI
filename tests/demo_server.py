"""Run a disposable WebUI demo without OlivOS or real bot data."""

import sys
import tempfile
import types
import zipfile
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from OlivaDiceWebUIStandalone.server import PORT, handler_factory  # noqa: E402


class DemoProc:
    Proc_data = {'bot_info_dict': {
        'demo-qq': types.SimpleNamespace(id='10001', platform={'platform': 'QQ', 'model': 'OneBot'}),
        'demo-discord': types.SimpleNamespace(id='olive-demo', platform={'platform': 'Discord', 'model': 'Bot'}),
    }}

    def get_plugin_list(self):
        return ['OlivaDiceCore', 'OlivaDiceMaster', 'OlivaDiceWebUIStandalone']


core = types.ModuleType('OlivaDiceCore')
demo_data = tempfile.TemporaryDirectory(prefix='olivadice-webui-demo-')
data_root = Path(demo_data.name)
core.data = types.SimpleNamespace(dataDirRoot=str(data_root), bot_content={'masterKey': 'DEMO-MASTER-KEY'}, bot_version_short_header='OlivaDiceDemo')
core.webTool = types.SimpleNamespace(get_system_proxy=lambda: None)
base = {
    'globalEnable': 1, 'userConfigCount': 100, 'pulseInterval': 300,
    'autoAcceptGroupAdd': 1, 'autoAcceptFriendAdd': 1, 'recordBotJoinGroup': 1,
    'disableReplyPrivate': 0, 'disablePrivate': 0, 'messageFliterMode': 0,
    'messageSplitGate': 650, 'messageSplitPageLimit': 10, 'messageSplitDelay': 1000,
    'messageSplitAutoShowPage': 1, 'messageSplitManualShowPage': 0,
    'largeRollLimit': 300, 'multiRollDetail': 1, 'randomMode': 0,
    'drawRecommendMode': 1, 'drawListMode': 2, 'helpRecommendGate': 25,
    'censorMode': 1, 'censorMatchMode': 1, 'defaultShowDefault': 0,
    'defaultAutoSn': 0, 'portEnable': 1, 'portCodeTTL': 86400,
    'portSplitGate': 550, 'portExportFileLimit': 10, 'masterAutoUpdate': 1,
    'masterList': [], 'noticeGroupList': [], 'pulseUrlList': [],
}
core.console = types.SimpleNamespace(
    dictConsoleSwitch={'unity': base.copy(), 'demo-qq': dict(base, masterList=[['123456789', 'QQ']]),
                       'demo-discord': dict(base, masterList=[])},
    saveConsoleSwitch=lambda: None,
    dictBackupConfig={'unity': {'isBackup': 0, 'startDate': '2026-09-17', 'passDay': 1,
                                'backupTime': '04:00:00', 'maxBackupCount': 3}},
    saveBackupConfig=lambda: None,
    dictConsoleSwitchTemplate={'default': base.copy()},
    dictBackupConfigTemplate={'default': {'isBackup': 0, 'startDate': '', 'passDay': 1,
                                          'backupTime': '04:00:00', 'maxBackupCount': 1}},
)
demo_relations = {}
core.console.getAllAccountRelations = lambda: demo_relations.copy()
core.msgCustom = types.SimpleNamespace(
    dictStrCustom={'strHello': '你好，我是青果骰。', 'strForGroupOnly': '此功能仅对群聊开放。', 'strBotName': '青果骰'},
    dictStrCustomDict={
        'demo-qq': {'strHello': '欢迎使用青果骰！请发送 .help 查看帮助。',
                    'strForGroupOnly': '此功能仅对群聊开放。', 'strBotName': '小青果酱',
                    'strRoll': '{tUserName} 掷出了 {tRollResult}', 'strHelp': '发送 .help 指令 查看帮助'},
        'demo-discord': {'strHello': 'Hello from OlivaDice!', 'strBotName': 'Olive Demo'},
    },
    dictStrCustomUpdateDict={'demo-qq': {'strHello': '欢迎使用青果骰！请发送 .help 查看帮助。'}, 'demo-discord': {}},
)
core.msgCustomManager = types.SimpleNamespace(saveMsgCustomByBotHash=lambda bot_hash: None)
core.helpDocData = types.SimpleNamespace(
    dictHelpDoc={'demo-qq': {'default': '输入 .help 指令 查看青果骰帮助。', '指令': '使用 .r 掷骰，使用 .help 查询帮助。', '跑团': '欢迎来到青果骰跑团。'},
                 'demo-discord': {'default': 'Send .help to view commands.'}},
    dictHelpDocDefault={'demo-qq': {'跑团': '欢迎来到青果骰跑团。'}, 'demo-discord': {}},
)

def set_help(bot, key, value):
    core.helpDocData.dictHelpDoc.setdefault(bot, {})[key] = value
    core.helpDocData.dictHelpDocDefault.setdefault(bot, {})[key] = value


def del_help(bot, key):
    core.helpDocData.dictHelpDoc.get(bot, {}).pop(key, None)
    core.helpDocData.dictHelpDocDefault.get(bot, {}).pop(key, None)

core.helpDoc = types.SimpleNamespace(setHelpDocByBotHash=set_help, delHelpDocByBotHash=del_help)
core.drawCardData = types.SimpleNamespace(dictDeckIndex={
    'demo-qq': {'基础牌堆.json': ['塔罗牌', '随机事件', '天气'], '跑团扩展.yaml': ['人物', '地点', '线索']},
    'demo-discord': {'demo-deck.json': ['Fate', 'Weather']},
})
core.drawCard = types.SimpleNamespace(reloadDeck=lambda: None)
for bot in ('demo-qq', 'demo-discord'):
    folder = data_root / bot / 'extend' / 'deckclassic'
    folder.mkdir(parents=True)
    (folder / 'sample.json').write_text('{"sample": ["A", "B"]}', encoding='utf-8')
sys.modules['OlivaDiceCore'] = core
master = types.ModuleType('OlivaDiceMaster')


def demo_link(slave, main, bots):
    if slave == main or any(slave in values for values in demo_relations.values()):
        return False, '此账号已有主账号'
    demo_relations.setdefault(main, []).append(slave)
    return True, '已关联'


def demo_unlink(slave, _main, bots):
    for main, values in demo_relations.items():
        if slave in values:
            values.remove(slave)
            return True, '已取消关联'
    return False, '当前没有关联'


master.accountManager = types.SimpleNamespace(linkAccount=demo_link, unlinkAccount=demo_unlink)


def demo_export(bot, _proc, path):
    with zipfile.ZipFile(path, 'w') as output:
        output.writestr('console/switch.json', '{}')
    return True, '已导出演示账号'


def demo_copy(source, target, _proc):
    return True, f'已将 {source} 的演示数据复制到 {target}'


def demo_import(path, target, _proc, sourceBotHash=None):
    return True, f'已将 {sourceBotHash} 的演示压缩包导入到 {target}', sourceBotHash


master.accountManager.exportAccountData = demo_export
master.accountManager.importAccountData = demo_copy
master.accountManager.importAccountDataFromZip = demo_import
sys.modules['OlivaDiceMaster'] = master

if __name__ == '__main__':
    httpd = HTTPServer(('127.0.0.1', PORT), handler_factory(DemoProc(), 'oliva-demo-2026'))
    print('OlivaDice WebUI demo: http://127.0.0.1:{}/'.format(PORT), flush=True)
    print('Demo token: oliva-demo-2026', flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
