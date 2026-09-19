import http.client
import io
import json
import os
import sys
import tempfile
import threading
import types
import unittest
import zipfile
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from OlivaDiceWebUI import deck_management, gui_parity, main, server, service  # noqa: E402


class FakeProc:
    Proc_data = {'bot_info_dict': {'bot-1': types.SimpleNamespace(
        id='123', platform={'platform': 'qq', 'model': 'onebot'})}}

    def get_plugin_list(self):
        return ['OlivaDiceCore', 'OlivaDiceMaster']


class WebUITest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.saved_switches = []
        self.saved_replies = []
        fake = types.ModuleType('OlivaDiceCore')
        fake.console = types.SimpleNamespace(
            dictConsoleSwitch={'unity': {'globalEnable': 1}, 'bot-1': {'globalEnable': 1, 'extensionMode': 3, 'masterList': []}},
            saveConsoleSwitch=lambda: self.saved_switches.append(True),
            dictBackupConfig={'unity': {'isBackup': 0, 'startDate': '2026-09-17',
                                        'passDay': 1, 'backupTime': '04:00:00', 'maxBackupCount': 1}},
            saveBackupConfig=lambda: self.saved_switches.append('backup'),
            getAllAccountRelations=lambda: {},
            dictConsoleSwitchTemplate={'default': {'globalEnable': 1, 'masterList': [], 'noticeGroupList': [], 'pulseUrlList': []}},
            dictBackupConfigTemplate={'default': {'isBackup': 0, 'startDate': '', 'passDay': 1, 'backupTime': '04:00:00', 'maxBackupCount': 1}},
        )
        fake.data = types.SimpleNamespace(dataDirRoot=self.temp_dir.name, bot_content={'masterKey': 'test-key'})
        fake.msgCustom = types.SimpleNamespace(
            dictStrCustom={'strHello': '默认回复'},
            dictStrCustomDict={'bot-1': {'strHello': '你好'}},
            dictStrCustomUpdateDict={'bot-1': {}},
        )
        fake.msgCustomManager = types.SimpleNamespace(
            saveMsgCustomByBotHash=lambda bot: self.saved_replies.append(bot),
        )
        fake.helpDocData = types.SimpleNamespace(
            dictHelpDoc={'bot-1': {'default': '帮助'}},
            dictHelpDocDefault={'bot-1': {}},
        )
        fake.helpDoc = types.SimpleNamespace(
            setHelpDocByBotHash=lambda bot, key, value: (
                fake.helpDocData.dictHelpDoc[bot].update({key: value}),
                fake.helpDocData.dictHelpDocDefault[bot].update({key: value})),
            delHelpDocByBotHash=lambda bot, key: (
                fake.helpDocData.dictHelpDoc[bot].pop(key),
                fake.helpDocData.dictHelpDocDefault[bot].pop(key)),
        )
        fake.drawCardData = types.SimpleNamespace(
            dictDeckTemp={'基础': ['X']},
            dictDeck={'bot-1': {'基础': ['X'], 'A': ['B']}, 'unity': {'基础': ['X'], 'Global': ['G']}},
            dictDeckIndex={'bot-1': {'sample.json': ['A', 'B']}, 'unity': {'shared.json': ['Global']}},
        )
        fake.drawCard = types.SimpleNamespace(reloadDeck=lambda: None)
        self.previous = sys.modules.get('OlivaDiceCore')
        sys.modules['OlivaDiceCore'] = fake
        self.fake = fake

    def tearDown(self):
        self.temp_dir.cleanup()
        if self.previous is None:
            del sys.modules['OlivaDiceCore']
        else:
            sys.modules['OlivaDiceCore'] = self.previous

    def test_service_persists_and_validates(self):
        self.assertEqual(service.set_switch(FakeProc(), 'bot-1', 'globalEnable', 0), 0)
        self.assertEqual(self.saved_switches, [True])
        self.assertEqual(service.set_reply(FakeProc(), 'bot-1', 'strHello', '新的回复'), '新的回复')
        self.assertEqual(self.fake.msgCustom.dictStrCustomUpdateDict['bot-1']['strHello'], '新的回复')
        self.assertEqual(self.saved_replies, ['bot-1'])
        with self.assertRaises(service.InvalidInput):
            service.set_switch(FakeProc(), 'bot-1', 'globalEnable', True)
        with self.assertRaises(service.InvalidInput):
            service.set_reply(FakeProc(), 'bot-1', 'unknown', 'x')

    def test_more_than_one_thousand_replies_are_available(self):
        values = {f'strCustom{index:04d}': f'回复 {index}' for index in range(1001)}
        self.fake.msgCustom.dictStrCustomDict['bot-1'] = values
        result = service.replies(FakeProc(), 'bot-1')
        self.assertEqual(len(result), 1001)
        self.assertEqual(result[-1]['key'], 'strCustom1000')

    def test_extended_service_routes_to_core_and_validates(self):
        proc = FakeProc()
        self.assertEqual(service.set_reply(proc, 'bot-1', 'strHello', reset=True), '默认回复')
        self.assertNotIn('strHello', self.fake.msgCustom.dictStrCustomUpdateDict['bot-1'])
        self.assertEqual(service.change_master(proc, 'bot-1', 'add', '456')[0]['id'], '456')
        self.assertEqual(service.change_master(proc, 'bot-1', 'remove', '456'), [])
        with self.assertRaises(service.InvalidInput):
            service.change_master(proc, 'bot-1', 'add', '4abc')
        self.assertEqual(service.set_help_doc(proc, 'bot-1', '新词条', '内容'), '内容')
        self.assertEqual(service.help_docs(proc, 'bot-1')[-1]['key'], '新词条')
        service.set_help_doc(proc, 'bot-1', '新词条', delete=True)
        self.assertEqual(service.decks(proc, 'bot-1')[0]['name'], '内置牌堆')
        self.assertEqual(service.decks(proc, 'bot-1')[1]['count'], 2)
        self.assertEqual(service.deck_group_count(proc, 'bot-1'), 2)
        self.assertEqual(service.decks(proc, 'unity')[1]['name'], 'shared.json')
        self.assertEqual(service.deck_group_count(proc, 'unity'), 2)
        self.assertTrue(service.reload_decks(proc))
        self.assertEqual(service.set_backup(proc, {'isBackup': 1, 'startDate': '2026-09-17',
            'passDay': 2, 'backupTime': '05:00:00', 'maxBackupCount': 3})['settings']['passDay'], 2)
        with self.assertRaises(service.InvalidInput):
            service.set_backup(proc, {'isBackup': 1})

    def test_gui_config_and_reply_batch_operations(self):
        proc = FakeProc()
        self.assertEqual(next(item for item in service.switches(proc, 'bot-1') if item['key'] == 'extensionMode')['value'], 3)
        self.assertEqual(service.set_switch(proc, 'bot-1', 'extensionMode', 5), 5)
        self.assertEqual(gui_parity.config_apply(proc, 'bot-1', 'import', {'extensionMode': 7})['extensionMode'], 7)
        self.assertEqual(gui_parity.config_apply(proc, 'bot-1', 'import', {'globalEnable': 0})['globalEnable'], 0)
        with self.assertRaises(service.InvalidInput):
            gui_parity.config_apply(proc, 'bot-1', 'import', {'globalEnable': 'off'})
        gui_parity.config_apply(proc, 'bot-1', 'reset-key', key='extensionMode')
        self.assertNotIn('extensionMode', self.fake.console.dictConsoleSwitch['bot-1'])
        self.assertEqual(gui_parity.config_apply(proc, 'bot-1', 'reset')['globalEnable'], 1)
        self.assertEqual(gui_parity.replies_apply(proc, 'bot-1', 'add', key='strExtra', value='新回复')['strExtra'], '新回复')
        self.assertEqual(gui_parity.replies_apply(proc, 'bot-1', 'reset')['strExtra'], '新回复')
        self.assertEqual(self.fake.msgCustom.dictStrCustomUpdateDict['bot-1']['strExtra'], '新回复')
        self.assertNotIn('strExtra', gui_parity.replies_apply(proc, 'bot-1', 'delete', key='strExtra'))
        self.assertEqual(gui_parity.replies_apply(proc, 'bot-1', 'import', {'strHello': '导入内容'})['strHello'], '导入内容')
        self.assertEqual(gui_parity.replies_apply(proc, 'bot-1', 'reset')['strHello'], '默认回复')
        self.assertEqual(gui_parity.recover_modules(proc, 'bot-1', ['OlivaDiceCore']), ['OlivaDiceCore'])
        self.assertEqual(gui_parity.master_command(), '.master test-key')

    def test_deck_file_scope_and_zip_path_validation(self):
        proc = FakeProc()
        deck_management.install_file(proc, 'bot-1', 'classic', 'mydeck.json', b'{"A":["B"]}')
        deck_management.install_file(proc, 'bot-1', 'yaml', 'oldstyle', b'A:\n  - B\n')
        self.assertEqual(deck_management.deck_files(proc, 'bot-1')[0]['name'], 'mydeck.json')
        self.assertEqual(len(deck_management.deck_files(proc, 'bot-1')), 2)
        self.assertEqual(deck_management.deck_files(proc, 'unity'), [])
        deck_management.install_file(proc, 'unity', 'classic', 'shared.json', b'{"Global":["G"]}')
        self.assertEqual(deck_management.deck_files(proc, 'unity')[0]['scope'], 'unity')
        with self.assertRaises(service.InvalidInput):
            deck_management.install_file(proc, 'bot-1', 'classic', '../evil.json', b'{}')
        self.assertTrue(deck_management.remove_file(proc, 'bot-1', 'classic', 'mydeck.json'))
        self.assertTrue(deck_management.remove_file(proc, 'unity', 'classic', 'shared.json'))
        with self.assertRaises(service.InvalidInput):
            gui_parity._check_zip(b'not a zip')
        invalid_zip = io.BytesIO()
        with zipfile.ZipFile(invalid_zip, 'w') as archive:
            archive.writestr('../outside.txt', 'escape')
        with self.assertRaises(service.InvalidInput):
            gui_parity._check_zip(invalid_zip.getvalue())
        with self.assertRaises(service.InvalidInput):
            deck_management.market_install(proc, 'bot-1', 'unknown', 'Example')

    def test_menu_opens_local_webui(self):
        import webbrowser
        original = webbrowser.open
        opened = []
        webbrowser.open = lambda url: opened.append(url) or True
        try:
            event = types.SimpleNamespace(data=types.SimpleNamespace(event='OlivaDiceWebUIStandalone_001'))
            main.Event.menu(event, FakeProc())
            self.assertEqual(opened, ['http://127.0.0.1:8765/'])
        finally:
            webbrowser.open = original

    def test_plugin_registration_is_standalone(self):
        manifest = json.loads((Path(__file__).parents[1] / 'OlivaDiceWebUI/app.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['name'], 'OlivaDice WebUI（独立服务版）')
        self.assertEqual(manifest['namespace'], 'OlivaDiceWebUIStandalone')
        self.assertEqual(manifest['menu_config'][0]['event'], 'OlivaDiceWebUIStandalone_001')
        self.assertEqual(server.CONFIG_DIR, Path('./plugin/data/OlivaDiceWebUIStandalone'))

    def test_market_install_uses_selected_catalog_entry(self):
        module = types.ModuleType('OlivaDiceOdyssey')
        module.webTool = types.SimpleNamespace(gExtiverseDeck={
            'classic': [{'name': 'Example', 'download_link': ['https://example.test/deck.json']}],
        })
        original_module = sys.modules.get('OlivaDiceOdyssey')
        original_download = deck_management._download
        sys.modules['OlivaDiceOdyssey'] = module
        deck_management._download = lambda url, maximum: b'{"A":["B"]}'
        class OdysseyProc(FakeProc):
            def get_plugin_list(self):
                return super().get_plugin_list() + ['OlivaDiceOdyssey']
        try:
            deck_management.market_install(OdysseyProc(), 'bot-1', 'classic', 'Example')
            self.assertEqual((Path(self.temp_dir.name) / 'bot-1/extend/deckclassic/Example.json').read_bytes(), b'{"A":["B"]}')
            with self.assertRaises(service.InvalidInput):
                deck_management.market_install(OdysseyProc(), 'bot-1', 'yaml', 'Example')
        finally:
            deck_management._download = original_download
            if original_module is None:
                del sys.modules['OlivaDiceOdyssey']
            else:
                sys.modules['OlivaDiceOdyssey'] = original_module

    def test_account_archive_round_trip(self):
        module = types.ModuleType('OlivaDiceMaster')
        def export(_bot, _proc, path):
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('console/switch.json', '{}')
            return True, 'exported'
        imported = []
        def import_archive(path, bot, _proc, sourceBotHash):
            with zipfile.ZipFile(path) as archive:
                imported.append((bot, sourceBotHash, archive.read('console/switch.json')))
            return True, 'imported', sourceBotHash
        module.accountManager = types.SimpleNamespace(exportAccountData=export, importAccountDataFromZip=import_archive)
        previous = sys.modules.get('OlivaDiceMaster')
        sys.modules['OlivaDiceMaster'] = module
        try:
            raw = gui_parity.account_export(FakeProc(), 'bot-1')
            self.assertEqual(gui_parity.account_import(FakeProc(), 'bot-1', 'original', raw), 'imported')
            self.assertEqual(imported, [('bot-1', 'original', b'{}')])
        finally:
            if previous is None:
                del sys.modules['OlivaDiceMaster']
            else:
                sys.modules['OlivaDiceMaster'] = previous

    def test_http_auth_origin_and_update(self):
        httpd = HTTPServer(('127.0.0.1', 0), server.handler_factory(FakeProc(), 'test-token'))
        original_port = server.PORT
        original_public_origin = server.PUBLIC_ORIGIN
        original_network_file = server.NETWORK_FILE
        server.PORT = httpd.server_port
        server.NETWORK_FILE = Path(self.temp_dir.name) / 'network-http.json'
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            def request(method, path, body=None, headers=None):
                conn = http.client.HTTPConnection('127.0.0.1', httpd.server_port)
                conn.request(method, path, body=body, headers=headers or {})
                response = conn.getresponse()
                result = response.status, json.loads(response.read())
                conn.close()
                return result

            self.assertEqual(request('GET', '/api/accounts')[0], 401)
            auth = {'Authorization': 'Bearer test-token', 'Content-Type': 'application/json'}
            self.assertEqual(request('GET', '/api/accounts', headers=auth)[1]['version'], server.plugin_version())
            self.assertEqual(request('GET', '/api/server-config', headers=auth)[0], 200)
            network = json.dumps({'bind': '127.0.0.1', 'port': 9876, 'publicOrigin': ''})
            self.assertEqual(request('POST', '/api/server-config', network, auth)[1]['saved']['port'], 9876)
            payload = json.dumps({'bot': 'bot-1', 'key': 'globalEnable', 'value': 0})
            self.assertEqual(request('POST', '/api/switches', payload,
                                     dict(auth, Origin='https://evil.example'))[0], 403)
            server.PUBLIC_ORIGIN = 'https://dice.example'
            remote_auth = dict(auth, Host='dice.example')
            self.assertEqual(request('GET', '/api/accounts', headers=remote_auth)[0], 200)
            self.assertEqual(request('GET', '/api/accounts', headers=dict(auth, Host='evil.example'))[0], 400)
            self.assertEqual(request('POST', '/api/switches', payload,
                                     dict(remote_auth, Origin='http://127.0.0.1:{}'.format(server.PORT)))[0], 403)
            self.assertEqual(request('POST', '/api/switches', payload,
                                     dict(remote_auth, Origin='https://dice.example'))[0], 200)
            self.assertEqual(request('POST', '/api/switches', payload, auth)[0], 200)
            self.assertEqual(self.fake.console.dictConsoleSwitch['bot-1']['globalEnable'], 0)
            self.assertEqual(request('GET', '/api/config?bot=bot-1', headers=auth)[1]['config']['globalEnable'], 0)
            self.assertEqual(request('POST', '/api/config', json.dumps({'bot': 'bot-1', 'action': 'reset'}), auth)[0], 200)
            binary = dict(auth, **{'Content-Type': 'application/octet-stream'})
            self.assertEqual(request('POST', '/api/deck-files/upload?bot=bot-1&kind=classic&name=sample.json', b'{"A":["B"]}', binary)[0], 200)
            self.assertEqual(request('GET', '/api/deck-files?bot=bot-1', headers=auth)[1]['files'][0]['name'], 'sample.json')
            self.assertEqual(request('GET', '/api/decks?bot=unity', headers=auth)[1]['decks'][1]['name'], 'shared.json')
            self.assertEqual(request('POST', '/api/deck-files/upload?bot=unity&kind=classic&name=shared.json', b'{"Global":["G"]}', binary)[0], 200)
            self.assertEqual(request('GET', '/api/deck-files?bot=unity', headers=auth)[1]['files'][0]['scope'], 'unity')
            self.assertEqual(request('POST', '/api/account/import?bot=bot-1&source=source', b'not a zip', dict(auth, **{'Content-Type': 'application/zip'}))[0], 400)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()
            server.PORT = original_port
            server.PUBLIC_ORIGIN = original_public_origin
            server.NETWORK_FILE = original_network_file

    def test_public_origin_validation(self):
        self.assertEqual(server._parse_origin('https://dice.example:8443'), 'https://dice.example:8443')
        for origin in ('http://0.0.0.0:8765', 'https://dice.example/path',
                       'https://user@dice.example', 'ftp://dice.example', 'https://dice.example:bad'):
            with self.assertRaises(ValueError):
                server._parse_origin(origin)

    def test_network_settings_persist_and_validate(self):
        original = server.NETWORK_FILE
        server.NETWORK_FILE = Path(self.temp_dir.name) / 'network.json'
        try:
            with patch.dict(os.environ, {}, clear=True):
                saved = server.save_network({'bind': '0.0.0.0', 'port': 9876,
                                             'publicOrigin': 'http://192.168.1.10:9876'})
                self.assertEqual(saved['afterRestart']['port'], 9876)
                self.assertTrue(saved['restartRequired'])
                self.assertEqual(server._read_network()['bind'], '0.0.0.0')
                before = server.NETWORK_FILE.read_bytes()
                for invalid in ({'bind': '0.0.0.0', 'port': 9876, 'publicOrigin': ''},
                                {'bind': '127.0.0.1', 'port': 0, 'publicOrigin': ''},
                                {'bind': '127.0.0.1', 'port': True, 'publicOrigin': ''}):
                    with self.assertRaises(ValueError):
                        server.save_network(invalid)
                self.assertEqual(server.NETWORK_FILE.read_bytes(), before)
        finally:
            server.NETWORK_FILE = original

    def test_frontend_bundle_is_served(self):
        httpd = HTTPServer(('127.0.0.1', 0), server.handler_factory(FakeProc(), 'test-token'))
        original_port = server.PORT
        server.PORT = httpd.server_port
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection('127.0.0.1', httpd.server_port)
            conn.request('GET', '/')
            page = conn.getresponse()
            html = page.read().decode('utf-8')
            self.assertEqual(page.status, 200)
            self.assertIn('id="root"', html)
            self.assertIn('assets/', html)
            conn.close()
            asset = '/' + html.split('src="./')[1].split('"')[0]
            conn = http.client.HTTPConnection('127.0.0.1', httpd.server_port)
            conn.request('GET', asset)
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertGreater(len(response.read()), 1000)
            conn.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()
            server.PORT = original_port


if __name__ == '__main__':
    unittest.main()
