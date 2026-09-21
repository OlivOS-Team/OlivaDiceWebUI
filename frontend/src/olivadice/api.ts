export type Account = { hash: string; label: string; platform: string; model: string; id: string };
export type Setting = { key: string; section: string; label: string; description: string; value: number; min: number; max: number; custom?: boolean };
export type Reply = { key: string; value: string; note: string; modified: boolean; default: string | null };
export type HelpDoc = { key: string; value: string; custom: boolean };
export type Deck = { name: string; groups: string[]; count: number };
export type Master = { id: string; platform: string };
export type BackupState = { available: boolean; settings: { isBackup: number | null; startDate: string | null; passDay: number | null; backupTime: string | null; maxBackupCount: number | null } };
export type ChanceRule = { key: string; division: string; matchType: 'full' | 'contain' | 'perfix' | 'reg'; matchPlace: '1' | '2' | '3'; priority: number; value: string };
export type ChanceDefault = { key: string; label: string; value: string; effective: string; inherited: boolean };
export type ChancePackage = { name: string; author: string; version: string; description: string; ruleCount: number };
export type ChanceCustomState = { available: boolean; writable?: boolean; version: string; dataVersion: number | null; revision: string; rules: ChanceRule[]; defaults: ChanceDefault[]; packages: ChancePackage[]; reason: string };

export const standalone = import.meta.env.VITE_WEBUI_MODE === 'standalone';

const events = {
  request: 'OlivaDiceWebUI_WebUI_Request',
  requestStart: 'OlivaDiceWebUI_WebUI_RequestStart',
  requestChunk: 'OlivaDiceWebUI_WebUI_RequestChunk',
  requestFinish: 'OlivaDiceWebUI_WebUI_RequestFinish',
  uploadStart: 'OlivaDiceWebUI_WebUI_UploadStart',
  uploadChunk: 'OlivaDiceWebUI_WebUI_UploadChunk',
  uploadFinish: 'OlivaDiceWebUI_WebUI_UploadFinish',
  downloadStart: 'OlivaDiceWebUI_WebUI_DownloadStart',
  downloadChunk: 'OlivaDiceWebUI_WebUI_DownloadChunk',
  cancel: 'OlivaDiceWebUI_WebUI_TransferCancel',
} as const;

type Pending = { resolve: (value: unknown) => void; reject: (reason: Error) => void; timer: number };
const pending = new Map<string, Pending>();
let sequence = 0;

window.addEventListener('message', event => {
  if (event.source !== window.parent) return;
  const data = event.data as { type?: unknown; request_id?: unknown; error?: unknown; payload?: unknown } | null;
  if (!data || data.type !== 'olivos:plugin_reply' || typeof data.request_id !== 'string') return;
  const task = pending.get(data.request_id);
  if (!task) return;
  pending.delete(data.request_id);
  window.clearTimeout(task.timer);
  if (typeof data.error === 'string') {
    task.reject(new Error(data.error));
    return;
  }
  const envelope = data.payload as { ok?: unknown; result?: unknown; error?: unknown } | null;
  if (!envelope || envelope.ok !== true) {
    task.reject(new Error(typeof envelope?.error === 'string' ? envelope.error : '插件返回了无效的数据'));
    return;
  }
  task.resolve(envelope.result);
});

function bridge<T>(event: string, payload: unknown, timeout = 30_000): Promise<T> {
  if (window.parent === window) return Promise.reject(new Error('请从 OlivOS WebUI 的「插件页面」打开青果骰管理。'));
  const requestId = `${Date.now()}-${++sequence}`;
  return new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => {
      pending.delete(requestId);
      reject(new Error('请求超时；操作结果可能已经生效，请刷新后确认。'));
    }, timeout);
    pending.set(requestId, { resolve: resolve as (value: unknown) => void, reject, timer });
    window.parent.postMessage({ type: 'olivos:plugin_event', event, request_id: requestId, payload }, '*');
  });
}

export async function api<T>(path: string, token: string, data?: unknown): Promise<T> {
  if (standalone) {
    const response = await fetch(path, {
      method: data === undefined ? 'GET' : 'POST',
      headers: { Authorization: `Bearer ${token}`, ...(data === undefined ? {} : { 'Content-Type': 'application/json' }) },
      ...(data === undefined ? {} : { body: JSON.stringify(data) }),
    });
    let result: Record<string, unknown>;
    try { result = await response.json(); } catch { throw new Error(`服务响应错误（HTTP ${response.status}）`); }
    if (!response.ok) throw new Error(String(result.error || `HTTP ${response.status}`));
    return result as T;
  }
  const request = { method: data === undefined ? 'GET' : 'POST', path, ...(data === undefined ? {} : { data }) };
  const encoded = new TextEncoder().encode(JSON.stringify(request));
  if (encoded.length <= 512 * 1024) return bridge<T>(events.request, request);
  const start = await bridge<{ transferId: string; chunkBytes: number }>(events.requestStart, { size: encoded.length });
  let offset = 0;
  try {
    while (offset < encoded.length) {
      const raw = encoded.subarray(offset, offset + start.chunkBytes);
      const chunk = await bridge<{ received: number }>(events.requestChunk, {
        transferId: start.transferId, offset, data: bytesToBase64(raw),
      });
      offset += raw.length;
      if (chunk.received !== offset) throw new Error('请求分块顺序错误');
    }
    return await bridge<T>(events.requestFinish, { transferId: start.transferId }, 120_000);
  } catch (cause) {
    await cancelTransfer(start.transferId);
    throw cause;
  }
}

export const botQuery = (bot: string) => `?bot=${encodeURIComponent(bot)}`;

function bytesToBase64(bytes: Uint8Array): string {
  const parts: string[] = [];
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    parts.push(String.fromCharCode(...bytes.subarray(offset, offset + 0x8000)));
  }
  return btoa(parts.join(''));
}

function base64ToBytes(value: string): Uint8Array {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

async function cancelTransfer(transferId: string): Promise<void> {
  try { await bridge(events.cancel, { transferId }, 5_000); } catch { /* Transfer may already be gone. */ }
}

export async function downloadFile(path: string, token: string, filename: string, data?: unknown): Promise<void> {
  if (standalone) {
    const response = await fetch(path, {
      method: data === undefined ? 'GET' : 'POST',
      headers: { Authorization: `Bearer ${token}`, ...(data === undefined ? {} : { 'Content-Type': 'application/json' }) },
      ...(data === undefined ? {} : { body: JSON.stringify(data) }),
    });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(String(result.error || `HTTP ${response.status}`));
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url; link.download = filename; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return;
  }
  const start = await bridge<{ transferId: string; size: number; chunkBytes: number }>(events.downloadStart, { path, ...(data === undefined ? {} : { data }) }, 120_000);
  const bytes = new Uint8Array(start.size);
  let offset = 0;
  try {
    while (offset < start.size) {
      const chunk = await bridge<{ offset: number; data: string; done: boolean }>(events.downloadChunk, { transferId: start.transferId, offset });
      if (chunk.offset !== offset) throw new Error('下载分块顺序错误');
      const decoded = base64ToBytes(chunk.data);
      bytes.set(decoded, offset);
      offset += decoded.length;
      if (chunk.done && offset !== start.size) throw new Error('下载文件不完整');
    }
  } catch (cause) {
    await cancelTransfer(start.transferId);
    throw cause;
  }
  const url = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }));
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function uploadFile<T>(path: string, token: string, file: File): Promise<T> {
  if (standalone) {
    const response = await fetch(path, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': file.name.toLowerCase().endsWith('.zip') ? 'application/zip' : 'application/octet-stream' },
      body: file,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(String(result.error || `HTTP ${response.status}`));
    return result as T;
  }
  const start = await bridge<{ transferId: string; chunkBytes: number }>(events.uploadStart, { path, name: file.name, size: file.size });
  let offset = 0;
  try {
    while (offset < file.size) {
      const raw = new Uint8Array(await file.slice(offset, offset + start.chunkBytes).arrayBuffer());
      const chunk = await bridge<{ received: number }>(events.uploadChunk, {
        transferId: start.transferId, offset, data: bytesToBase64(raw),
      });
      offset += raw.length;
      if (chunk.received !== offset) throw new Error('上传分块顺序错误');
    }
    return await bridge<T>(events.uploadFinish, { transferId: start.transferId }, 120_000);
  } catch (cause) {
    await cancelTransfer(start.transferId);
    throw cause;
  }
}

export async function readJsonFile(file: File, maxBytes = 4 * 1024 * 1024): Promise<Record<string, unknown>> {
  if (file.size > maxBytes) throw new Error('JSON 文件超过 4 MiB');
  const value: unknown = JSON.parse(await file.text());
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('文件顶层必须是 JSON 对象');
  return value as Record<string, unknown>;
}

export function saveJsonFile(data: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
