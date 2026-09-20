"""Token-protected management server with explicit remote origin support."""

import base64
import binascii
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
    from . import chance_custom, deck_management, gui_parity, service
except ImportError:  # Shared source lives in the official package before packaging.
    from OlivaDiceWebUI import chance_custom, deck_management, gui_parity, service


CONFIG_DIR = Path('./plugin/data/OlivaDiceWebUIStandalone')
TOKEN_FILE = CONFIG_DIR / 'admin-token.txt'
NETWORK_FILE = CONFIG_DIR / 'network.json'
WEB_ROOT = Path(__file__).with_name('web')
APP_FILE = Path(__file__).with_name('app.json')
# OlivOS imports OPK modules and then removes their extracted plugin/tmp directory.
# Anything the server still needs at runtime must be captured while the module is
# being imported, so it survives the host's cleanup of that temporary tree.
APP_VERSION = json.loads(APP_FILE.read_text(encoding='utf-8'))['version']
WEB_ASSETS = {}
for _asset in sorted(WEB_ROOT.rglob('*')) if WEB_ROOT.is_dir() else []:
    if _asset.is_file():
        WEB_ASSETS[_asset.relative_to(WEB_ROOT).as_posix()] = _asset.read_bytes()

DEFAULT_NETWORK = {'bind': '0.0.0.0', 'port': 8765, 'publicOrigin': ''}
ENV_NETWORK = {'bind': 'OLIVADICE_STANDALONE_WEBUI_BIND',
               'port': 'OLIVADICE_STANDALONE_WEBUI_PORT',
               'publicOrigin': 'OLIVADICE_STANDALONE_WEBUI_PUBLIC_ORIGIN'}
_network_lock = threading.RLock()


def _parse_origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or any(char.isspace() for char in value)):
        raise ValueError('远程访问地址必须是完整的 HTTP(S) 来源地址，不能包含路径')
    try:
        _ = parsed.port
    except ValueError:
        raise ValueError('远程访问地址的端口无效') from None
    if parsed.hostname in ('0.0.0.0', '::'):
        raise ValueError('远程访问地址应填写远程访问时使用的地址')
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
    # The origin stays optional: without it the listener still answers on loopback and
    # on this machine's own interfaces, which is all a plain LAN panel needs. Filling
    # it in is what additionally admits a domain or a forwarded port.
    public_origin = _parse_origin(origin) if origin else ''
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


def _startup_network():
    """Resolve the startup network settings without letting one bad value kill the host.

    A network.json left over from an older, stricter build can fail validation. In that
    case the host must still start, so the file is reported as the problem instead of
    raising out of OlivOS' plugin loader.
    """
    try:
        saved = _read_network()
        return saved, _effective_network(saved), ''
    except (OSError, ValueError) as exc:
        saved = DEFAULT_NETWORK.copy()
        return saved, saved, '配置文件不可用（{}），已使用默认设置 {}:{}'.format(
            exc, DEFAULT_NETWORK['bind'], DEFAULT_NETWORK['port'])


def _local_origin_scheme():
    """Scheme a browser uses when it reaches this server directly."""
    return 'https' if PUBLIC_ORIGIN and urlsplit(PUBLIC_ORIGIN).scheme == 'https' else 'http'


def _interface_addresses():
    try:
        import socket
        return {name for name in socket.gethostbyname_ex(socket.gethostname())[2] if name}
    except OSError:
        return set()


def _local_hosts():
    """Host names that legitimately address this listener from a browser.

    The port is deliberately not pinned: a reverse proxy or port forward in front of
    the server legitimately rewrites the Host header, and pinning the port made the
    panel reject its own frontend in that setup. The host name still has to match,
    which keeps DNS rebinding and foreign-origin writes out.
    """
    hosts = {'127.0.0.1', 'localhost', '[::1]'}
    if BIND_IS_LOOPBACK:
        hosts.add(BIND_HOST)
    else:
        hosts.update(_interface_addresses())
        hosts.add(BIND_HOST)
    if PUBLIC_ORIGIN:
        hosts.add(urlsplit(PUBLIC_ORIGIN).hostname.lower())
    hosts.discard('')
    return hosts


def _hostname_of(host_header):
    value = (host_header or '').strip().lower()
    if value.startswith('['):  # bracketed IPv6 literal
        end = value.find(']')
        return value[:end + 1] if end != -1 else value
    return value.rsplit(':', 1)[0] if ':' in value else value


def _is_trusted_host(host_header):
    if not host_header:
        return False
    name = _hostname_of(host_header)
    if not name:
        return False
    try:
        address = ipaddress.ip_address(name.strip('[]'))
    except ValueError:
        return name in _local_hosts()
    return address.is_loopback or address.is_unspecified or str(address) in _local_hosts()


def _normalize_origin(origin):
    parsed = urlsplit(origin)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        return None
    port = parsed.port
    if port in (None, 443 if parsed.scheme == 'https' else 80):
        netloc = parsed.hostname.lower()
    else:
        netloc = '{}:{}'.format(parsed.hostname.lower(), port)
    return '{}://{}'.format(parsed.scheme, netloc)


def _origin_matches(origin, host_header):
    """A write is same-origin when the browser's Origin agrees with the request Host."""
    if not origin:
        return True
    supplied = _normalize_origin(origin)
    if supplied is None:
        return False
    expected = _normalize_origin('{}://{}'.format(_local_origin_scheme(), host_header))
    return expected is not None and supplied == expected


def _trusted_origins():
    """Convenience view of accepted origins, for diagnostics and the bundled tests."""
    scheme = _local_origin_scheme()
    origins = {}
    for host in sorted(_local_hosts()):
        origins['{}:{}'.format(host, PORT)] = '{}://{}:{}'.format(scheme, host, PORT)
    if PUBLIC_ORIGIN:
        origins[urlsplit(PUBLIC_ORIGIN).netloc.lower()] = PUBLIC_ORIGIN
    return origins


def restore_web_assets():
    """Re-materialise the frontend bundle where OlivOS registered the plugin page.

    The OPK ships the built page inside the archive, but OlivOS extracts the module to
    plugin/tmp and deletes that tree right after import. Without this the packaged
    plugin looks like it is missing its frontend build.
    """
    root = WEB_ROOT
    if not WEB_ASSETS:
        raise RuntimeError('插件包内缺少前端构建产物，请先在 frontend 目录运行 npm run build 后重新打包')
    needs_restore = any(not (root / name).is_file() for name in WEB_ASSETS)
    if not needs_restore:
        return None
    restored = 0
    for name, data in WEB_ASSETS.items():
        target = root / name
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            current = target.read_bytes() if target.is_file() else None
            if current != data:
                target.write_bytes(data)
            restored += 1
        except OSError as exc:
            return '写出 {} 失败：{}'.format(name, exc)
    return None if restored else '前端构建产物为空'


def _snapshot_network():
    with _network_lock:
        saved = _read_network()
        after_restart = _effective_network(saved)
        active = {'bind': BIND_HOST, 'port': PORT, 'publicOrigin': PUBLIC_ORIGIN or ''}
        return {'active': active, 'saved': saved, 'afterRestart': after_restart,
                'environmentOverrides': {key: name in os.environ for key, name in ENV_NETWORK.items()},
                'restartRequired': after_restart != active,
                'startupWarning': STARTUP_NETWORK_WARNING,
                'recoveryWarning': RECOVERY_WARNING}


def network_state():
    try:
        return _snapshot_network()
    except (OSError, ValueError) as exc:
        return {'active': {'bind': BIND_HOST, 'port': PORT, 'publicOrigin': PUBLIC_ORIGIN or ''},
                'saved': DEFAULT_NETWORK.copy(), 'afterRestart': None,
                'environmentOverrides': {key: name in os.environ for key, name in ENV_NETWORK.items()},
                'restartRequired': True, 'startupWarning': '配置文件不可用：{}'.format(exc),
                'recoveryWarning': RECOVERY_WARNING}


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
        return _snapshot_network()


STARTUP_SAVED, STARTUP_NETWORK, STARTUP_NETWORK_WARNING = _startup_network()
RECOVERY_WARNING = restore_web_assets()
BIND_HOST = STARTUP_NETWORK['bind']
PORT = STARTUP_NETWORK['port']
PUBLIC_ORIGIN = STARTUP_NETWORK['publicOrigin'] or None
BIND_IS_LOOPBACK = ipaddress.IPv4Address(BIND_HOST).is_loopback
_server = None
_thread = None


def _token():
    """Return the admin token, generating it once and never rotating it again.

    The file is the single source of truth: as long as it holds a usable token that
    value is reused across restarts, so a browser that saved it keeps working. Only a
    missing or unreadable file triggers a new one, and a malformed file is rewritten
    rather than left in place to fail every future start.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        existing = TOKEN_FILE.read_text(encoding='ascii').strip()
    except (OSError, UnicodeDecodeError):
        existing = ''
    if len(existing) == 64 and all(c in '0123456789abcdef' for c in existing):
        return existing
    token = secrets.token_hex(32)
    data = (token + '\n').encode('ascii')
    temporary = TOKEN_FILE.with_name(TOKEN_FILE.name + '.tmp')
    with open(temporary, 'wb') as stream:
        stream.write(data)
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, TOKEN_FILE)
    return token


def plugin_version():
    return APP_VERSION


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
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status, message):
            self._send(status, {'error': message})

        def _send_asset(self, name):
            """Serve the embedded frontend bundle, rebuilding it on disk when needed.

            Reading from the in-memory snapshot keeps the page available even if OlivOS
            has already removed plugin/tmp, while restore_web_assets() re-creates the
            copy that the host registered on disk.
            """
            body = WEB_ASSETS.get(name)
            if body is None:
                self._error(404, '资源不存在')
                return
            target = WEB_ROOT / name
            if not target.is_file():
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(body)
                except OSError:
                    pass
            content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            self._send(200, body, content_type)

        def _allowed_host(self):
            return _is_trusted_host(self.headers.get('Host'))

        def _authorized(self):
            supplied = self.headers.get('Authorization', '')
            return supplied.startswith('Bearer ') and hmac.compare_digest(supplied[7:], token)

        def _request_ok(self, write=False):
            if not self._allowed_host():
                self._error(400, 'Host 不受支持')
                return False
            if write and not _origin_matches(self.headers.get('Origin'), self.headers.get('Host')):
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
                self._send_asset('olivadice.html' if path.path == '/' else path.path.lstrip('/'))
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
                elif path.path == '/api/chance-custom':
                    self._send(200, chance_custom.snapshot(proc, bot_hash))
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
            if path.path in ('/api/account/import', '/api/deck-files/upload',
                              '/api/chance-custom/packages/upload'):
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
                    try:
                        self._send(200, save_network(data))
                    except ValueError as exc:
                        self._error(400, str(exc))
                    return
                bot_hash = data.get('bot')
                if not isinstance(bot_hash, str):
                    raise service.InvalidInput('请选择账号')
                path = urlsplit(self.path).path
                if path == '/api/chance-custom/packages/export':
                    raw, filename = chance_custom.export_package(proc, bot_hash, data)
                    self._send(200, raw, 'application/zip', filename)
                    return
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
                elif path == '/api/chance-custom/rules':
                    result = chance_custom.change_rule(
                        proc, bot_hash, data.get('action'), data.get('rule'),
                        data.get('originalKey'), data.get('revision', ''))
                elif path == '/api/chance-custom/defaults':
                    result = chance_custom.set_defaults(
                        proc, bot_hash, data.get('values'), data.get('revision', ''))
                elif path == '/api/chance-custom/packages/manage':
                    result = chance_custom.manage_package(
                        proc, bot_hash, data.get('action'), data.get('name'),
                        data.get('revision', ''))
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
            maximum = 8 * 1024 * 1024 if path.path == '/api/chance-custom/packages/upload' else 100 * 1024 * 1024
            if not length.isdecimal() or int(length) > maximum:
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
                elif path.path == '/api/deck-files/upload':
                    result = deck_management.install_file(proc, bot_hash, query.get('kind', [''])[0], query.get('name', [''])[0], raw)
                else:
                    result = chance_custom.import_package(
                        proc, bot_hash, query.get('name', ['package.ccpk'])[0], raw,
                        query.get('revision', [''])[0])
                self._send(200, {'value': result})
            except service.InvalidInput as exc:
                self._error(400, str(exc))
            except Exception:
                self._error(500, '文件处理失败，请查看 OlivOS 日志')

    return Handler


def start(proc):
    global _server, _thread, RECOVERY_WARNING
    if _server is not None:
        return
    if RECOVERY_WARNING is None:
        RECOVERY_WARNING = restore_web_assets()
    if RECOVERY_WARNING is not None:
        raise RuntimeError('前端构建产物不可用：{}；请先在 frontend 目录运行 npm run build 后重新打包'.format(RECOVERY_WARNING))
    if STARTUP_NETWORK_WARNING:
        proc.log(4, 'OlivaDiceWebUIStandalone: {}'.format(STARTUP_NETWORK_WARNING))
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
