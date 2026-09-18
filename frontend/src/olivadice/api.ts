export type Account = { hash: string; label: string; platform: string; model: string; id: string };
export type Setting = { key: string; section: string; label: string; description: string; value: number; min: number; max: number; custom?: boolean };
export type Reply = { key: string; value: string; note: string; modified: boolean; default: string | null };
export type HelpDoc = { key: string; value: string; custom: boolean };
export type Deck = { name: string; groups: string[]; count: number };
export type Master = { id: string; platform: string };
export type BackupState = { available: boolean; settings: { isBackup: number | null; startDate: string | null; passDay: number | null; backupTime: string | null; maxBackupCount: number | null } };

export async function api<T>(path: string, token: string, data?: unknown): Promise<T> {
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

export const botQuery = (bot: string) => `?bot=${encodeURIComponent(bot)}`;

export async function downloadFile(path: string, token: string, filename: string): Promise<void> {
  const response = await fetch(path, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(String(result.error || `HTTP ${response.status}`));
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function uploadFile<T>(path: string, token: string, file: File): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': file.name.toLowerCase().endsWith('.zip') ? 'application/zip' : 'application/octet-stream' },
    body: file,
  });
  const result = await response.json();
  if (!response.ok) throw new Error(String(result.error || `HTTP ${response.status}`));
  return result as T;
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
