"""Token-protected management server with explicit remote origin support."""

import hmac
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

try:
    from . import deck_management, gui_parity, service
except ImportError:  # Shared source lives in the official package before packaging.
    from OlivaDiceWebUI import deck_management, gui_parity, service


CONFIG_DIR = Path('./plugin/data/OlivaDiceWebUIStandalone')
TOKEN_FILE = CONFIG_DIR / 'admin-token.txt'
NETWORK_FILE = CONFIG_DIR / 'network.json'
WEB_ROOT = Path(__file__).with_name('web')
APP_FILE = Path(__file__).with_name('app.json')
DEFAULT_NETWORK = {'bind': '127.0.0.1', 'port': 8765, 'publicOrigin': ''}
ENV_NETWORK = {'bind': 'OLIVADICE_STANDALONE_WEBUI_BIND',
               'port': 'OLIVADICE_STANDALONE_WEBUI_PORT',
               'publicOrigin': 'OLIVADICE_STANDALONE_WEBUI_PUBLIC_ORIGIN'}
_network_lock = threading.RLock()


def _parse_origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or any(char.isspace() for char in value)):
        raise ValueError('OLIVADICE_STANDALONE_WEBUI_PUBLIC_ORIGIN 必须是完整的 HTTP(S) 来源地址，不能包含路径')
    try:
        _ = parsed.port
    except ValueError:
        raise ValueError('OLIVADICE_STANDALONE_WEBUI_PUBLIC_ORIGIN 的端口无效') from None
    if parsed.hostname in ('0.0.0.0', '127.0.0.1', 'localhost'):
        raise ValueError('OLIVADICE_STANDALONE_WEBUI_PUBLIC_ORIGIN 应填写远程访问时使用的地址')
    return '{}://{}'.format(parsed.scheme, parsed.netloc.lower())


def _validate_network(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_NETWORK):
        raise ValueError('服务设置格式无效')
    bind = value['bind']
    port = value['port']
    origin = value['publicOrigin']
    if not isinstance(bind, str):
        raise ValueError('监听地址必须是 IPv4 地址')
    try:
        bind_address = ipaddress.IPv4Address(bind.strip())
    except ipaddress.AddressValueError:
        raise ValueError('监听地址必须是 IPv4 地址') from None
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('端口必须是 1–65535 的整数')
    if not isinstance(origin, str):
        raise ValueError('远程访问地址必须是 HTTP(S) 来源地址')
    origin = origin.strip()
    public_origin = _parse_origin(origin) if origin else ''
    if not bind_address.is_loopback and not public_origin:
        raise ValueError('监听非本机地址时，必须填写远程访问地址')
    return {'bind': str(bind_address), 'port': port, 'publicOrigin': public_origin}


def _read_network():
    if not NETWORK_FILE.is_file():
        return DEFAULT_NETWORK.copy()
    return _validate_network(json.loads(NETWORK_FILE.read_text(encoding='utf-8')))


def _effective_network(saved):
    value = saved.copy()
    for key, name in ENV_NETWORK.items():
        if name in os.environ:
            raw = os.environ[name].strip()
            if key == 'port':
                try:
                    value[key] = int(raw)
                except ValueError:
                    raise ValueError('{} 必须是 1–65535 的端口'.format(name)) from None
            else:
                value[key] = raw
    return _validate_network(value)


def network_state():
    with _network_lock:
        saved = _read_network()
        after_restart = _effective_network(saved)
        active = {'bind': BIND_HOST, 'port': PORT, 'publicOrigin': PUBLIC_ORIGIN or ''}
        return {'active': active, 'saved': saved, 'afterRestart': after_restart,
                'environmentOverrides': {key: name in os.environ for key, name in ENV_NETWORK.items()},
                'restartRequired': after_restart != active}


def save_network(value):
    validated = _validate_network(value)
    _effective_network(validated)
    with _network_lock:
        NETWORK_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='network-', suffix='.tmp', dir=NETWORK_FILE.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(validated, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            os.replace(temporary, NETWORK_FILE)
        finally:
            temporary.unlink(missing_ok=True)
        return network_state()


_startup_network = _effective_network(_read_network())
BIND_HOST = _startup_network['bind']
PORT = _startup_network['port']
PUBLIC_ORIGIN = _startup_network['publicOrigin'] or None
_server = None
_thread = None


def _trusted_origins():
    origins = {'127.0.0.1:{}'.format(PORT): 'http://127.0.0.1:{}'.format(PORT),
               'localhost:{}'.format(PORT): 'http://localhost:{}'.format(PORT)}
    if PUBLIC_ORIGIN:
        origins[urlsplit(PUBLIC_ORIGIN).netloc.lower()] = PUBLIC_ORIGIN
    return origins


def _token():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding='ascii').strip()
        if len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
            raise RuntimeError('admin-token.txt 内容无效')
        return token
    token = secrets.token_hex(32)
    fd = os.open(str(TOKEN_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='ascii') as stream:
        stream.write(token + '\n')
    return token


def plugin_version():
    return json.loads(APP_FILE.read_text(encoding='utf-8'))['version']


def handler_factory(proc, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'OlivaDiceWebUIStandalone/{}'.format(plugin_version())

        def log_message(self, format, *args):
            # Avoid logging authorization headers or reply contents.
            pass

        def _send(self, status, data, content_type='application/json; charset=utf-8', filename=None):
            body = (json.dumps(data, ensure_ascii=False).encode('utf-8')
                    if content_type.startswith('application/json') else data)
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            if filename:
                safe_name = re.sub(r'[^A-Za-z0-9_.-]', '_', filename)[:180]
                self.send_header('Content-Disposition', 'attachment; filename="{}"'.format(safe_name))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status, message):
            self._send(status, {'error': message})

        def _allowed_host(self):
            return self.headers.get('Host', '').lower() in _trusted_origins()

        def _authorized(self):
            supplied = self.headers.get('Authorization', '')
            return supplied.startswith('Bearer ') and hmac.compare_digest(supplied[7:], token)

        def _request_ok(self, write=False):
            if not self._allowed_host():
                self._error(400, 'Host 不受支持')
                return False
            if write:
                origin = self.headers.get('Origin')
                expected_origin = _trusted_origins().get(self.headers.get('Host', '').lower())
                if origin and origin != expected_origin:
                    self._error(403, '请求来源不受支持')
                    return False
            if not self._authorized():
                self._error(401, '需要管理令牌')
                return False
            return True

        def do_GET(self):
            path = urlsplit(self.path)
            if not self._allowed_host():
                self._error(400, 'Host 不受支持')
                return
            if path.path == '/' or path.path.startswith('/assets/'):
                name = 'olivadice.html' if path.path == '/' else path.path.lstrip('/')
                target = (WEB_ROOT / name).resolve()
                try:
                    target.relative_to(WEB_ROOT.resolve())
                except ValueError:
                    self._error(404, '资源不存在')
                    return
                if not target.is_file():
                    self._error(404, '资源不存在')
                    return
                content_type = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
                self._send(200, target.read_bytes(), content_type)
                return
            if not self._request_ok():
                return
            query = parse_qs(path.query)
            bot_hash = query.get('bot', ['unity'])[0]
            try:
                if path.path == '/api/accounts':
                    self._send(200, {'accounts': service.accounts(proc), 'version': plugin_version()})
                elif path.path == '/api/server-config':
                    self._send(200, network_state())
                elif path.path == '/api/switches':
                    self._send(200, {'switches': service.switches(proc, bot_hash)})
                elif path.path == '/api/replies':
                    self._send(200, {'replies': service.replies(proc, bot_hash)})
                elif path.path == '/api/masters':
                    self._send(200, {'masters': service.masters(proc, bot_hash)})
                elif path.path == '/api/relations':
                    self._send(200, service.relations(proc))
                elif path.path == '/api/help':
                    self._send(200, {'docs': service.help_docs(proc, bot_hash)})
                elif path.path == '/api/decks':
                    self._send(200, {'decks': service.decks(proc, bot_hash),
                                     'groupCount': service.deck_group_count(proc, bot_hash)})
                elif path.path == '/api/backup':
                    self._send(200, service.backup(proc))
                elif path.path == '/api/config':
                    self._send(200, {'config': gui_parity.config_snapshot(proc, bot_hash)})
                elif path.path == '/api/replies/export':
                    self._send(200, {'replies': gui_parity.replies_snapshot(proc, bot_hash)})
                elif path.path == '/api/recover-modules':
                    self._send(200, {'modules': gui_parity.recover_modules(proc, bot_hash)})
                elif path.path == '/api/master-command':
                    self._send(200, {'command': gui_parity.master_command()})
                elif path.path == '/api/deck-files':
                    self._send(200, {'files': deck_management.deck_files(proc, bot_hash)})
                elif path.path == '/api/deck-folder':
                    self._send(200, {'path': deck_management.deck_folder(proc, bot_hash)})
                elif path.path == '/api/deck-market':
                    self._send(200, deck_management.market(proc, query.get('refresh', ['0'])[0] == '1'))
                elif path.path == '/api/account/export':
                    self._send(200, gui_parity.account_export(proc, bot_hash), 'application/zip', 'account_export_{}.zip'.format(bot_hash))
                else:
                    self._error(404, '接口不存在')
            except service.InvalidInput as exc:
                self._error(400, str(exc))
            except Exception:
                self._error(500, '读取失败，请查看 OlivOS 日志')

        def do_POST(self):
            if not self._request_ok(write=True):
                return
            path = urlsplit(self.path)
            if path.path in ('/api/account/import', '/api/deck-files/upload'):
                self._binary_post(path)
                return
            length = self.headers.get('Content-Length', '')
            if not length.isdecimal() or int(length) > 4 * 1024 * 1024:
                self._error(413, '请求体过大或长度无效')
                return
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self._error(415, '只接受 JSON')
                return
            try:
                data = json.loads(self.rfile.read(int(length)))
                if not isinstance(data, dict):
                    raise service.InvalidInput('请求格式错误')
                if path.path == '/api/server-config':
                    self._send(200, save_network(data))
                    return
                bot_hash = data.get('bot')
                if not isinstance(bot_hash, str):
                    raise service.InvalidInput('请选择账号')
                path = urlsplit(self.path).path
                if path == '/api/switches':
                    result = service.set_switch(proc, bot_hash, data.get('key'), data.get('value'))
                elif path == '/api/replies':
                    result = service.set_reply(proc, bot_hash, data.get('key'), data.get('value'), data.get('action') == 'reset')
                elif path == '/api/masters':
                    result = service.change_master(proc, bot_hash, data.get('action'), data.get('id'))
                elif path == '/api/relations':
                    result = service.change_relation(proc, data.get('action'), data.get('slave'), data.get('master'))
                elif path == '/api/help':
                    result = service.set_help_doc(proc, bot_hash, data.get('key'), data.get('value'), data.get('action') == 'delete')
                elif path == '/api/decks/reload':
                    result = service.reload_decks(proc)
                elif path == '/api/backup':
                    result = service.set_backup(proc, data.get('settings'))
                elif path == '/api/config':
                    result = gui_parity.config_apply(proc, bot_hash, data.get('action'), data.get('data'), data.get('key'))
                elif path == '/api/replies/manage':
                    result = gui_parity.replies_apply(proc, bot_hash, data.get('action'), data.get('data'), data.get('key'), data.get('value'))
                elif path == '/api/recover-modules':
                    result = gui_parity.recover_modules(proc, bot_hash, data.get('modules'))
                elif path == '/api/backup/manage':
                    result = gui_parity.backup_apply(proc, data.get('action'), data.get('data'), data.get('key'))
                elif path == '/api/account/copy':
                    result = gui_parity.account_copy(proc, data.get('source'), data.get('target'))
                elif path == '/api/deck-files/delete':
                    result = deck_management.remove_file(proc, bot_hash, data.get('kind'), data.get('name'))
                elif path == '/api/deck-market/install':
                    result = deck_management.market_install(proc, bot_hash, data.get('kind'), data.get('name'))
                else:
                    self._error(404, '接口不存在')
                    return
                self._send(200, {'value': result})
            except (ValueError, UnicodeDecodeError) as exc:
                self._error(400, str(exc))
            except Exception:
                self._error(500, '保存失败，请查看 OlivOS 日志')

        def _binary_post(self, path):
            length = self.headers.get('Content-Length', '')
            if not length.isdecimal() or int(length) > 100 * 1024 * 1024:
                self._error(413, '文件过大或长度无效')
                return
            if self.headers.get('Content-Type', '').split(';')[0] not in ('application/zip', 'application/octet-stream'):
                self._error(415, '文件类型不受支持')
                return
            query = parse_qs(path.query)
            bot_hash = query.get('bot', [''])[0]
            raw = self.rfile.read(int(length))
            try:
                if path.path == '/api/account/import':
                    result = gui_parity.account_import(proc, bot_hash, query.get('source', [''])[0], raw)
                else:
                    result = deck_management.install_file(proc, bot_hash, query.get('kind', [''])[0], query.get('name', [''])[0], raw)
                self._send(200, {'value': result})
            except service.InvalidInput as exc:
                self._error(400, str(exc))
            except Exception:
                self._error(500, '文件处理失败，请查看 OlivOS 日志')

    return Handler


def start(proc):
    global _server, _thread
    if _server is not None:
        return
    if not (WEB_ROOT / 'olivadice.html').is_file():
        raise RuntimeError('缺少前端构建产物，请先在 frontend 目录运行 npm run build')
    token = _token()
    _server = ThreadingHTTPServer((BIND_HOST, PORT), handler_factory(proc, token))
    _server.daemon_threads = True
    _thread = threading.Thread(target=_server.serve_forever, name='OlivaDiceWebUIStandalone', daemon=True)
    _thread.start()
    proc.log(2, 'OlivaDiceWebUIStandalone: {}:{} 已启动；远程地址 {}；令牌文件 {}'.format(
        BIND_HOST, PORT, PUBLIC_ORIGIN or '未配置', TOKEN_FILE))


def stop():
    global _server, _thread
    if _server is not None:
        _server.shutdown()
        _server.server_close()
        _server = None
    if _thread is not None:
        _thread.join(timeout=2)
        _thread = None
