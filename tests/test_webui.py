import base64
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
from OlivaDiceWebUI import bridge, deck_management, gui_parity, main, service  # noqa: E402
from OlivaDiceWebUIStandalone import main as standalone_main  # noqa: E402
from OlivaDiceWebUIStandalone import server as standalone_server  # noqa: E402


class FakeProc:
    Proc_data = {'bot_info_dict': {'bot-1': types.SimpleNamespace(
        id='123', platform={'platform': 'qq', 'model': 'onebot'})}}

    def get_plugin_list(self):
        return ['OlivaDiceCore', 'OlivaDiceMaster']


class WebUITest(unittest.TestCase):
    def setUp(self):
        bridge.clear_transfers()
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
        bridge.clear_transfers()
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

    def test_menu_uses_official_webui_bridge(self):
        replies = []
        event = types.SimpleNamespace(
            data=types.SimpleNamespace(
                namespace='OlivaDiceWebUI',
                event=bridge.EVENT_REQUEST,
                webui={'request_id': 'request-1', 'session': 'session-1'},
                payload={'method': 'GET', 'path': '/api/accounts'},
            ),
            send=lambda kind, request_id, payload: replies.append((kind, request_id, payload)) or True,
        )
        main.Event.menu(event, FakeProc())
        self.assertEqual(replies[0][0:2], ('webui', 'request-1'))
        self.assertTrue(replies[0][2]['ok'])
        self.assertEqual(replies[0][2]['result']['accounts'][1]['hash'], 'bot-1')

    def test_plugin_editions_have_distinct_registrations(self):
        root = Path(__file__).parents[1]
        official = json.loads((root / 'OlivaDiceWebUI/app.json').read_text(encoding='utf-8'))
        standalone_manifest = json.loads((root / 'OlivaDiceWebUIStandalone/app.json').read_text(encoding='utf-8'))
        self.assertEqual(official['name'], 'OlivaDice WebUI（官方接入版）')
        self.assertEqual(official['namespace'], 'OlivaDiceWebUI')
        self.assertEqual(standalone_manifest['name'], 'OlivaDice WebUI（独立服务版）')
        self.assertEqual(standalone_manifest['namespace'], 'OlivaDiceWebUIStandalone')
        self.assertNotEqual(official['namespace'], standalone_manifest['namespace'])
        self.assertEqual(standalone_server.CONFIG_DIR, Path('./plugin/data/OlivaDiceWebUIStandalone'))

    def test_standalone_menu_and_http_service(self):
        import webbrowser
        original_open = webbrowser.open
        opened = []
        webbrowser.open = lambda url: opened.append(url) or True
        try:
            event = types.SimpleNamespace(data=types.SimpleNamespace(event='OlivaDiceWebUIStandalone_001'))
            standalone_main.Event.menu(event, FakeProc())
            self.assertEqual(opened, ['http://127.0.0.1:8765/'])
        finally:
            webbrowser.open = original_open

        httpd = HTTPServer(('127.0.0.1', 0), standalone_server.handler_factory(FakeProc(), 'test-token'))
        original_port = standalone_server.PORT
        standalone_server.PORT = httpd.server_port
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            def request(path, headers=None):
                connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port)
                connection.request('GET', path, headers=headers or {})
                response = connection.getresponse()
                body = response.read()
                connection.close()
                return response.status, body

            self.assertEqual(request('/api/accounts')[0], 401)
            status, body = request('/api/accounts', {'Authorization': 'Bearer test-token'})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['accounts'][1]['hash'], 'bot-1')
            status, page = request('/')
            self.assertEqual(status, 200)
            self.assertIn(b'id="root"', page)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()
            standalone_server.PORT = original_port

    def test_standalone_network_settings_are_isolated(self):
        original = standalone_server.NETWORK_FILE
        standalone_server.NETWORK_FILE = Path(self.temp_dir.name) / 'network.json'
        try:
            with patch.dict(os.environ, {}, clear=True):
                saved = standalone_server.save_network({
                    'bind': '0.0.0.0', 'port': 9876,
                    'publicOrigin': 'http://192.168.1.10:9876',
                })
                self.assertEqual(saved['afterRestart']['port'], 9876)
                self.assertEqual(standalone_server._read_network()['bind'], '0.0.0.0')
        finally:
            standalone_server.NETWORK_FILE = original

    def test_standalone_defaults_to_all_interfaces(self):
        self.assertEqual(standalone_server.DEFAULT_NETWORK['bind'], '0.0.0.0')
        self.assertEqual(standalone_server.DEFAULT_NETWORK['port'], 8765)
        self.assertEqual(standalone_server.DEFAULT_NETWORK['publicOrigin'], '')

    def test_standalone_wildcard_bind_without_public_origin(self):
        """A wildcard listener must be usable for plain LAN access with no domain."""
        accepted = standalone_server._validate_network(
            {'bind': '0.0.0.0', 'port': 8765, 'publicOrigin': ''})
        self.assertEqual(accepted['bind'], '0.0.0.0')
        self.assertEqual(accepted['publicOrigin'], '')
        saved = standalone_server._validate_network(
            {'bind': '127.0.0.1', 'port': 8765, 'publicOrigin': ''})
        self.assertEqual(saved['bind'], '127.0.0.1')
        with_origin = standalone_server._validate_network(
            {'bind': '0.0.0.0', 'port': 8765, 'publicOrigin': 'http://dice.example.com'})
        self.assertEqual(with_origin['publicOrigin'], 'http://dice.example.com')
        for wildcard in ('0.0.0.0/0', 'localhost', 'not-an-ip'):
            with self.assertRaises(ValueError):
                standalone_server._validate_network(
                    {'bind': wildcard, 'port': 8765, 'publicOrigin': ''})

    def test_standalone_public_origin_rejects_unnavigable_addresses(self):
        for value in ('0.0.0.0:8765', 'http://0.0.0.0:8765', 'http://[::]', 'ftp://x.test',
                      'http://x.test/path', 'http://user:pw@x.test'):
            with self.assertRaises(ValueError, msg=value):
                standalone_server._validate_network(
                    {'bind': '0.0.0.0', 'port': 8765, 'publicOrigin': value})

    def test_standalone_trusted_origins_cover_every_reachable_host(self):
        original = (standalone_server.BIND_HOST, standalone_server.BIND_IS_LOOPBACK,
                    standalone_server.PORT, standalone_server.PUBLIC_ORIGIN)
        try:
            standalone_server.PORT = 8765
            standalone_server.PUBLIC_ORIGIN = 'http://10.0.0.5:8765'
            standalone_server.BIND_HOST, standalone_server.BIND_IS_LOOPBACK = '0.0.0.0', False
            origins = standalone_server._trusted_origins()
            self.assertIn('127.0.0.1:8765', origins)
            self.assertIn('localhost:8765', origins)
            self.assertEqual(origins['10.0.0.5:8765'], 'http://10.0.0.5:8765')
        finally:
            (standalone_server.BIND_HOST, standalone_server.BIND_IS_LOOPBACK,
             standalone_server.PORT, standalone_server.PUBLIC_ORIGIN) = original

    def test_standalone_menu_opens_loopback_for_wildcard_bind(self):
        original = (standalone_server.BIND_HOST, standalone_server.BIND_IS_LOOPBACK, standalone_server.PORT)
        try:
            standalone_server.BIND_HOST, standalone_server.BIND_IS_LOOPBACK = '0.0.0.0', False
            self.assertEqual(standalone_main._local_url(), 'http://127.0.0.1:8765/')
            standalone_server.BIND_HOST, standalone_server.BIND_IS_LOOPBACK = '127.0.0.1', True
            self.assertEqual(standalone_main._local_url(), 'http://127.0.0.1:8765/')
            standalone_server.BIND_HOST, standalone_server.BIND_IS_LOOPBACK = '192.168.1.7', False
            self.assertEqual(standalone_main._local_url(), 'http://192.168.1.7:8765/')
        finally:
            standalone_server.BIND_HOST, standalone_server.BIND_IS_LOOPBACK, standalone_server.PORT = original

    def test_frontend_bundle_is_embedded_and_restorable(self):
        root = Path(__file__).parents[1]
        page = root / 'OlivaDiceWebUIStandalone/web/olivadice.html'
        self.assertTrue(page.is_file(), 'standalone frontend must be built before packaging')
        self.assertIn('olivadice.html', standalone_server.WEB_ASSETS)
        # Vite fingerprints the bundle names, so they change on every rebuild; assert on
        # the shape instead of pinning the current hashes.
        self.assertTrue(any(name.startswith('assets/olivadice-') and name.endswith('.js')
                            for name in standalone_server.WEB_ASSETS), sorted(standalone_server.WEB_ASSETS))
        self.assertTrue(any(name.startswith('assets/olivadice-') and name.endswith('.css')
                            for name in standalone_server.WEB_ASSETS), sorted(standalone_server.WEB_ASSETS))
        self.assertEqual(standalone_server.plugin_version(),
                         json.loads((root / 'OlivaDiceWebUIStandalone/app.json').read_text(encoding='utf-8'))['version'])
        self.assertEqual(bridge.plugin_version(),
                         json.loads((root / 'OlivaDiceWebUI/app.json').read_text(encoding='utf-8'))['version'])

    def test_frontend_bundle_survives_removed_plugin_tmp_directory(self):
        """OlivOS deletes plugin/tmp after import; assets must be rebuilt from memory."""
        with tempfile.TemporaryDirectory() as scratch:
            removed_root = Path(scratch) / 'web'
            original = standalone_server.WEB_ROOT
            standalone_server.WEB_ROOT = removed_root
            try:
                self.assertIsNone(standalone_server.restore_web_assets())
                for name in standalone_server.WEB_ASSETS:
                    self.assertTrue((removed_root / name).is_file(), name)
                httpd = HTTPServer(('127.0.0.1', 0), standalone_server.handler_factory(FakeProc(), 'test-token'))
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port)
                    connection.request('GET', '/')
                    response = connection.getresponse()
                    body = response.read()
                    connection.close()
                    self.assertEqual(response.status, 200)
                    self.assertIn(b'id="root"', body)
                    self.assertIn('text/html', response.getheader('Content-Type'))
                finally:
                    httpd.shutdown()
                    httpd.server_close()
                    thread.join()
            finally:
                standalone_server.WEB_ROOT = original

    def test_frontend_bundle_is_served_without_any_disk_copy(self):
        """The in-memory snapshot alone must be able to answer requests."""
        with tempfile.TemporaryDirectory() as scratch:
            missing_root = Path(scratch) / 'never-written'
            original_root = standalone_server.WEB_ROOT
            original_restore = standalone_server.restore_web_assets
            standalone_server.WEB_ROOT = missing_root
            standalone_server.restore_web_assets = lambda: 'skip disk write'
            try:
                httpd = HTTPServer(('127.0.0.1', 0), standalone_server.handler_factory(FakeProc(), 'test-token'))
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    stylesheet = next(name for name in standalone_server.WEB_ASSETS
                                      if name.startswith('assets/olivadice-') and name.endswith('.css'))
                    for path, marker in (('/', b'id="root"'), ('/' + stylesheet, b'')):
                        connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port)
                        connection.request('GET', path)
                        response = connection.getresponse()
                        body = response.read()
                        connection.close()
                        self.assertEqual(response.status, 200, path)
                        self.assertTrue(body, path)
                        if marker:
                            self.assertIn(marker, body)
                finally:
                    httpd.shutdown()
                    httpd.server_close()
                    thread.join()
            finally:
                standalone_server.WEB_ROOT = original_root
                standalone_server.restore_web_assets = original_restore

    def test_standalone_reports_network_errors_as_bad_request(self):
        original = standalone_server.NETWORK_FILE
        standalone_server.NETWORK_FILE = Path(self.temp_dir.name) / 'network.json'
        try:
            httpd = HTTPServer(('127.0.0.1', 0), standalone_server.handler_factory(FakeProc(), 'test-token'))
            original_port = standalone_server.PORT
            standalone_server.PORT = httpd.server_port
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                body = json.dumps({'bind': 'localhost', 'port': 8765, 'publicOrigin': ''}).encode('utf-8')
                connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port)
                connection.request('POST', '/api/server-config', body=body, headers={
                    'Authorization': 'Bearer test-token',
                    'Content-Type': 'application/json',
                    'Host': '127.0.0.1:{}'.format(httpd.server_port),
                })
                response = connection.getresponse()
                payload = json.loads(response.read())
                connection.close()
                self.assertEqual(response.status, 400)
                self.assertIn('监听地址', payload['error'])
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join()
                standalone_server.PORT = original_port
        finally:
            standalone_server.NETWORK_FILE = original

    def test_bridge_reads_version_without_package_files(self):
        """app.json is gone once OlivOS removes plugin/tmp, so the version is cached."""
        self.assertFalse(hasattr(bridge.plugin_version, '__wrapped__'))
        original = bridge.APP_FILE
        bridge.APP_FILE = Path(self.temp_dir.name) / 'gone' / 'app.json'
        try:
            self.assertEqual(bridge.plugin_version(), bridge.APP_VERSION)
            self.assertIsInstance(bridge.plugin_version(), str)
            self.assertTrue(bridge.plugin_version())
        finally:
            bridge.APP_FILE = original

    def test_market_install_uses_selected_catalog_entry(self):
        module = types.ModuleType('OlivaDiceOdyssey')
        module.webTool = types.SimpleNamespace(gExtiverseDeck={
            'classic': [{'name': 'Example', 'download_link': [
                'https://bad.example.test/deck.json', 'https://example.test/deck.json']}],
        })
        original_module = sys.modules.get('OlivaDiceOdyssey')
        original_download = deck_management._download
        sys.modules['OlivaDiceOdyssey'] = module
        downloads = []
        def download(url, maximum):
            downloads.append(url)
            return b'<html>mirror error</html>' if 'bad.example' in url else b'{"A":["B"]}'
        deck_management._download = download
        target = Path(self.temp_dir.name) / 'bot-1/extend/deckclassic/Example.json'
        def reload_deck():
            try:
                groups = list(json.loads(target.read_text(encoding='utf-8')))
            except (OSError, ValueError):
                self.fake.drawCardData.dictDeckIndex['bot-1'].pop('Example', None)
            else:
                self.fake.drawCardData.dictDeckIndex['bot-1']['Example'] = groups
        self.fake.drawCard.reloadDeck = reload_deck
        class OdysseyProc(FakeProc):
            def get_plugin_list(self):
                return super().get_plugin_list() + ['OlivaDiceOdyssey']
        try:
            deck_management.market_install(OdysseyProc(), 'bot-1', 'classic', 'Example')
            self.assertEqual(target.read_bytes(), b'{"A":["B"]}')
            self.assertEqual(downloads, ['https://bad.example.test/deck.json', 'https://example.test/deck.json'])
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

            context = {'session': 'session-download'}
            started = bridge.download_start(
                FakeProc(), {'path': '/api/account/export?bot=bot-1'}, context)
            downloaded = bytearray()
            offset = 0
            while offset < started['size']:
                chunk = bridge.download_chunk(
                    {'transferId': started['transferId'], 'offset': offset}, context)
                decoded = base64.b64decode(chunk['data'])
                downloaded.extend(decoded)
                offset += len(decoded)
            self.assertEqual(bytes(downloaded), raw)
        finally:
            if previous is None:
                del sys.modules['OlivaDiceMaster']
            else:
                sys.modules['OlivaDiceMaster'] = previous

    def test_bridge_routes_reads_and_writes(self):
        proc = FakeProc()
        accounts = bridge.request(proc, {'method': 'GET', 'path': '/api/accounts'})
        self.assertEqual(accounts['version'], bridge.plugin_version())
        self.assertEqual(accounts['accounts'][1]['hash'], 'bot-1')
        result = bridge.request(proc, {'method': 'POST', 'path': '/api/switches',
                                      'data': {'bot': 'bot-1', 'key': 'globalEnable', 'value': 0}})
        self.assertEqual(result, {'value': 0})
        self.assertEqual(self.fake.console.dictConsoleSwitch['bot-1']['globalEnable'], 0)
        with self.assertRaises(service.InvalidInput):
            bridge.request(proc, {'method': 'GET', 'path': 'https://evil.example/api/accounts'})
        with self.assertRaises(service.InvalidInput):
            bridge.request(proc, {'method': 'GET', 'path': '/api/server-config'})

    def test_chunked_request_and_deck_upload(self):
        context = {'session': 'session-1'}
        raw_request = json.dumps({
            'method': 'POST', 'path': '/api/switches',
            'data': {'bot': 'bot-1', 'key': 'extensionMode', 'value': 9},
        }).encode()
        started = bridge.request_start({'size': len(raw_request)}, context)
        bridge.request_chunk({'transferId': started['transferId'], 'offset': 0,
                              'data': base64.b64encode(raw_request).decode()}, context)
        self.assertEqual(bridge.request_finish(FakeProc(), {'transferId': started['transferId']}, context),
                         {'value': 9})

        raw_deck = b'{"Bridge":["works"]}'
        started = bridge.upload_start({
            'path': '/api/deck-files/upload?bot=bot-1&kind=classic&name=bridge.json',
            'name': 'bridge.json', 'size': len(raw_deck),
        }, context)
        bridge.upload_chunk({'transferId': started['transferId'], 'offset': 0,
                             'data': base64.b64encode(raw_deck).decode()}, context)
        bridge.upload_finish(FakeProc(), {'transferId': started['transferId']}, context)
        self.assertEqual((Path(self.temp_dir.name) / 'bot-1/extend/deckclassic/bridge.json').read_bytes(), raw_deck)
        with self.assertRaises(service.InvalidInput):
            bridge.upload_chunk({'transferId': started['transferId'], 'offset': 0, 'data': ''}, context)

    def test_frontend_bundle_is_registered_for_olivos(self):
        app = json.loads((Path(__file__).parents[1] / 'OlivaDiceWebUI/app.json').read_text(encoding='utf-8'))
        self.assertEqual(app['webui_config'][0]['path'], 'webui/olivadice.html')
        page = Path(__file__).parents[1] / 'OlivaDiceWebUI/webui/olivadice.html'
        html = page.read_text(encoding='utf-8')
        self.assertIn('id="root"', html)
        self.assertIn('<script type="module">', html)
        self.assertIn('<style>', html)
        self.assertNotIn('src="./assets/', html)
        self.assertNotIn('href="./assets/', html)
        self.assertIn('aria-modal', html)
        frontend = Path(__file__).parents[1] / 'frontend/src/olivadice'
        self.assertFalse(any('window.confirm(' in source.read_text(encoding='utf-8')
                             for source in frontend.rglob('*.tsx')))
        self.assertEqual([path.name for path in page.parent.iterdir()], ['olivadice.html'])


if __name__ == '__main__':
    unittest.main()
