"""OlivOS WebUI message-bridge adapter for the management service."""

import base64
import binascii
import json
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import chance_custom, deck_management, gui_parity, service


APP_FILE = Path(__file__).with_name('app.json')
# OlivOS imports OPK modules and then removes their extracted plugin/tmp directory, so
# neither app.json nor any other package file can be read after startup. Capture the
# version while the module is still importable, and keep this as the only source of it.
APP_VERSION = json.loads(APP_FILE.read_text(encoding='utf-8'))['version']
CHUNK_BYTES = 256 * 1024
TRANSFER_TTL = 10 * 60
MAX_TRANSFERS = 8
EVENT_REQUEST = 'OlivaDiceWebUI_WebUI_Request'
EVENT_REQUEST_START = 'OlivaDiceWebUI_WebUI_RequestStart'
EVENT_REQUEST_CHUNK = 'OlivaDiceWebUI_WebUI_RequestChunk'
EVENT_REQUEST_FINISH = 'OlivaDiceWebUI_WebUI_RequestFinish'
EVENT_UPLOAD_START = 'OlivaDiceWebUI_WebUI_UploadStart'
EVENT_UPLOAD_CHUNK = 'OlivaDiceWebUI_WebUI_UploadChunk'
EVENT_UPLOAD_FINISH = 'OlivaDiceWebUI_WebUI_UploadFinish'
EVENT_DOWNLOAD_START = 'OlivaDiceWebUI_WebUI_DownloadStart'
EVENT_DOWNLOAD_CHUNK = 'OlivaDiceWebUI_WebUI_DownloadChunk'
EVENT_TRANSFER_CANCEL = 'OlivaDiceWebUI_WebUI_TransferCancel'

_transfers = {}
_transfer_lock = threading.RLock()


def clear_transfers():
    with _transfer_lock:
        _transfers.clear()


def plugin_version():
    return APP_VERSION


def _path(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise service.InvalidInput('接口路径无效')
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith('/api/'):
        raise service.InvalidInput('接口路径无效')
    return parsed, parse_qs(parsed.query)


def request(proc, payload):
    """Dispatch the former HTTP API shape without exposing a network server."""
    if not isinstance(payload, dict):
        raise service.InvalidInput('请求格式错误')
    method = payload.get('method')
    parsed, query = _path(payload.get('path'))
    if method == 'GET':
        return _get(proc, parsed.path, query)
    if method == 'POST':
        data = payload.get('data')
        if not isinstance(data, dict):
            raise service.InvalidInput('请求数据必须是对象')
        return _post(proc, parsed.path, data)
    raise service.InvalidInput('请求方法无效')


def _get(proc, path, query):
    bot_hash = query.get('bot', ['unity'])[0]
    if path == '/api/accounts':
        return {'accounts': service.accounts(proc), 'version': plugin_version()}
    if path == '/api/switches':
        return {'switches': service.switches(proc, bot_hash)}
    if path == '/api/replies':
        return {'replies': service.replies(proc, bot_hash)}
    if path == '/api/masters':
        return {'masters': service.masters(proc, bot_hash)}
    if path == '/api/relations':
        return service.relations(proc)
    if path == '/api/help':
        return {'docs': service.help_docs(proc, bot_hash)}
    if path == '/api/decks':
        return {'decks': service.decks(proc, bot_hash),
                'groupCount': service.deck_group_count(proc, bot_hash)}
    if path == '/api/backup':
        return service.backup(proc)
    if path == '/api/config':
        return {'config': gui_parity.config_snapshot(proc, bot_hash)}
    if path == '/api/replies/export':
        return {'replies': gui_parity.replies_snapshot(proc, bot_hash)}
    if path == '/api/recover-modules':
        return {'modules': gui_parity.recover_modules(proc, bot_hash)}
    if path == '/api/master-command':
        return {'command': gui_parity.master_command()}
    if path == '/api/deck-files':
        return {'files': deck_management.deck_files(proc, bot_hash)}
    if path == '/api/deck-folder':
        return {'path': deck_management.deck_folder(proc, bot_hash)}
    if path == '/api/deck-market':
        return deck_management.market(proc, query.get('refresh', ['0'])[0] == '1')
    if path == '/api/chance-custom':
        return chance_custom.snapshot(proc, bot_hash)
    raise service.InvalidInput('接口不存在')


def _post(proc, path, data):
    bot_hash = data.get('bot')
    if not isinstance(bot_hash, str):
        raise service.InvalidInput('请选择账号')
    if path == '/api/switches':
        result = service.set_switch(proc, bot_hash, data.get('key'), data.get('value'))
    elif path == '/api/replies':
        result = service.set_reply(proc, bot_hash, data.get('key'), data.get('value'),
                                   data.get('action') == 'reset')
    elif path == '/api/masters':
        result = service.change_master(proc, bot_hash, data.get('action'), data.get('id'))
    elif path == '/api/relations':
        result = service.change_relation(proc, data.get('action'), data.get('slave'), data.get('master'))
    elif path == '/api/help':
        result = service.set_help_doc(proc, bot_hash, data.get('key'), data.get('value'),
                                      data.get('action') == 'delete')
    elif path == '/api/decks/reload':
        result = service.reload_decks(proc)
    elif path == '/api/backup':
        result = service.set_backup(proc, data.get('settings'))
    elif path == '/api/config':
        result = gui_parity.config_apply(proc, bot_hash, data.get('action'), data.get('data'),
                                         data.get('key'))
    elif path == '/api/replies/manage':
        result = gui_parity.replies_apply(proc, bot_hash, data.get('action'), data.get('data'),
                                          data.get('key'), data.get('value'))
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
            proc, bot_hash, data.get('action'), data.get('rule'), data.get('originalKey'),
            data.get('revision', ''))
    elif path == '/api/chance-custom/defaults':
        result = chance_custom.set_defaults(
            proc, bot_hash, data.get('values'), data.get('revision', ''))
    elif path == '/api/chance-custom/packages/manage':
        result = chance_custom.manage_package(
            proc, bot_hash, data.get('action'), data.get('name'), data.get('revision', ''))
    else:
        raise service.InvalidInput('接口不存在')
    return {'value': result}


def _session(context):
    session = context.get('session') if isinstance(context, dict) else None
    if not isinstance(session, str) or not session:
        raise service.InvalidInput('WebUI 会话无效')
    return session


def _cleanup(now=None):
    now = time.monotonic() if now is None else now
    for transfer_id, state in list(_transfers.items()):
        if now - state['updated'] > TRANSFER_TTL:
            _transfers.pop(transfer_id, None)


def _new_transfer(session, state):
    with _transfer_lock:
        _cleanup()
        if len(_transfers) >= MAX_TRANSFERS:
            raise service.InvalidInput('正在处理的文件过多，请稍后重试')
        transfer_id = secrets.token_hex(16)
        state.update(session=session, updated=time.monotonic())
        _transfers[transfer_id] = state
        return transfer_id


def _transfer(payload, context, mode):
    if not isinstance(payload, dict) or not isinstance(payload.get('transferId'), str):
        raise service.InvalidInput('文件传输参数无效')
    transfer_id = payload['transferId']
    with _transfer_lock:
        _cleanup()
        state = _transfers.get(transfer_id)
        if state is None or state.get('mode') != mode or state.get('session') != _session(context):
            raise service.InvalidInput('文件传输已失效，请重新操作')
        state['updated'] = time.monotonic()
        return transfer_id, state


def upload_start(payload, context):
    if not isinstance(payload, dict):
        raise service.InvalidInput('文件传输参数无效')
    parsed, query = _path(payload.get('path'))
    size = payload.get('size')
    name = payload.get('name')
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise service.InvalidInput('文件大小无效')
    if not isinstance(name, str) or not name or len(name) > 255:
        raise service.InvalidInput('文件名无效')
    limits = {'/api/account/import': 100 * 1024 * 1024,
              '/api/deck-files/upload': 12 * 1024 * 1024,
              '/api/chance-custom/packages/upload': 8 * 1024 * 1024}
    if parsed.path not in limits:
        raise service.InvalidInput('文件接口不存在')
    if size > limits[parsed.path]:
        raise service.InvalidInput('文件过大')
    transfer_id = _new_transfer(_session(context), {
        'mode': 'upload', 'path': parsed.path, 'query': query, 'name': name,
        'size': size, 'data': bytearray(),
    })
    return {'transferId': transfer_id, 'chunkBytes': CHUNK_BYTES}


def upload_chunk(payload, context):
    return _append_chunk(payload, context, 'upload')


def _append_chunk(payload, context, mode):
    with _transfer_lock:
        transfer_id, state = _transfer(payload, context, mode)
        offset, encoded = payload.get('offset'), payload.get('data')
        if isinstance(offset, bool) or not isinstance(offset, int) or offset != len(state['data']):
            raise service.InvalidInput('文件分块顺序无效')
        if not isinstance(encoded, str) or len(encoded) > (CHUNK_BYTES * 4 // 3 + 16):
            raise service.InvalidInput('文件分块无效')
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise service.InvalidInput('文件分块编码无效') from None
        if len(raw) > CHUNK_BYTES or len(state['data']) + len(raw) > state['size']:
            raise service.InvalidInput('文件分块大小无效')
        state['data'].extend(raw)
        return {'transferId': transfer_id, 'received': len(state['data'])}


def request_start(payload, context):
    size = payload.get('size') if isinstance(payload, dict) else None
    if isinstance(size, bool) or not isinstance(size, int) or not 0 <= size <= 4 * 1024 * 1024:
        raise service.InvalidInput('请求数据大小无效')
    transfer_id = _new_transfer(_session(context), {
        'mode': 'request', 'size': size, 'data': bytearray(),
    })
    return {'transferId': transfer_id, 'chunkBytes': CHUNK_BYTES}


def request_chunk(payload, context):
    return _append_chunk(payload, context, 'request')


def request_finish(proc, payload, context):
    transfer_id, state = _transfer(payload, context, 'request')
    with _transfer_lock:
        if len(state['data']) != state['size']:
            raise service.InvalidInput('请求数据尚未上传完整')
        _transfers.pop(transfer_id, None)
    try:
        value = json.loads(bytes(state['data']).decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise service.InvalidInput('请求数据不是有效的 JSON') from None
    return request(proc, value)


def upload_finish(proc, payload, context):
    transfer_id, state = _transfer(payload, context, 'upload')
    with _transfer_lock:
        if len(state['data']) != state['size']:
            raise service.InvalidInput('文件尚未上传完整')
        _transfers.pop(transfer_id, None)
    query, raw = state['query'], bytes(state['data'])
    bot_hash = query.get('bot', [''])[0]
    if state['path'] == '/api/account/import':
        result = gui_parity.account_import(proc, bot_hash, query.get('source', [''])[0], raw)
    elif state['path'] == '/api/deck-files/upload':
        result = deck_management.install_file(proc, bot_hash, query.get('kind', [''])[0],
                                              query.get('name', [''])[0], raw)
    else:
        result = chance_custom.import_package(
            proc, bot_hash, state['name'], raw, query.get('revision', [''])[0])
    return {'value': result}


def download_start(proc, payload, context):
    if not isinstance(payload, dict):
        raise service.InvalidInput('文件传输参数无效')
    parsed, query = _path(payload.get('path'))
    if parsed.path not in ('/api/account/export', '/api/chance-custom/packages/export'):
        raise service.InvalidInput('文件接口不存在')
    bot_hash = query.get('bot', [''])[0]
    if parsed.path == '/api/account/export':
        raw = gui_parity.account_export(proc, bot_hash)
        filename = state_filename('account_export_{}.zip'.format(bot_hash))
        maximum = 100 * 1024 * 1024
    else:
        raw, filename = chance_custom.export_package(proc, bot_hash, payload.get('data'))
        filename = state_filename(filename)
        maximum = 8 * 1024 * 1024
    if not isinstance(raw, bytes) or len(raw) > maximum:
        raise service.InvalidInput('导出文件无效或过大')
    transfer_id = _new_transfer(_session(context), {
        'mode': 'download', 'data': raw,
        'name': filename,
    })
    return {'transferId': transfer_id, 'size': len(raw), 'chunkBytes': CHUNK_BYTES,
            'filename': filename}


def state_filename(value):
    return ''.join(char if char.isalnum() or char in '._-' else '_' for char in value)[:180]


def download_chunk(payload, context):
    transfer_id, state = _transfer(payload, context, 'download')
    offset = payload.get('offset')
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= len(state['data']):
        raise service.InvalidInput('下载位置无效')
    raw = state['data'][offset:offset + CHUNK_BYTES]
    done = offset + len(raw) >= len(state['data'])
    if done:
        with _transfer_lock:
            _transfers.pop(transfer_id, None)
    return {'transferId': transfer_id, 'offset': offset,
            'data': base64.b64encode(raw).decode('ascii'), 'done': done}


def transfer_cancel(payload, context):
    if not isinstance(payload, dict) or not isinstance(payload.get('transferId'), str):
        raise service.InvalidInput('文件传输参数无效')
    transfer_id = payload['transferId']
    with _transfer_lock:
        state = _transfers.get(transfer_id)
        if state is not None and state.get('session') == _session(context):
            _transfers.pop(transfer_id, None)
    return {'cancelled': True}


def dispatch(proc, event, payload, context):
    if event == EVENT_REQUEST:
        return request(proc, payload)
    if event == EVENT_REQUEST_START:
        return request_start(payload, context)
    if event == EVENT_REQUEST_CHUNK:
        return request_chunk(payload, context)
    if event == EVENT_REQUEST_FINISH:
        return request_finish(proc, payload, context)
    if event == EVENT_UPLOAD_START:
        return upload_start(payload, context)
    if event == EVENT_UPLOAD_CHUNK:
        return upload_chunk(payload, context)
    if event == EVENT_UPLOAD_FINISH:
        return upload_finish(proc, payload, context)
    if event == EVENT_DOWNLOAD_START:
        return download_start(proc, payload, context)
    if event == EVENT_DOWNLOAD_CHUNK:
        return download_chunk(payload, context)
    if event == EVENT_TRANSFER_CANCEL:
        return transfer_cancel(payload, context)
    raise service.InvalidInput('未知的 WebUI 事件')
