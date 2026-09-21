import React from 'react';
import { Download, Plus, RotateCcw, Save, Settings2, Sparkles, Trash2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { api, botQuery, readJsonFile, saveJsonFile, type Reply } from '../api';
import { Busy, Empty, SearchField, SectionTitle, Select, useConfirm } from '../ui';

type Props = { token: string; bot: string; notify: (message: string, error?: boolean) => void; onDirtyChange: (dirty: boolean) => void };
const PAGE_SIZE = 100;
export function RepliesPage({ token, bot, notify, onDirtyChange }: Props) {
  const confirm = useConfirm();
  const [items, setItems] = React.useState<Reply[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [query, setQuery] = React.useState('');
  const [modifiedOnly, setModifiedOnly] = React.useState(false);
  const [page, setPage] = React.useState(1);
  const [selected, setSelected] = React.useState('');
  const [creating, setCreating] = React.useState(false);
  const [newKey, setNewKey] = React.useState('');
  const [draft, setDraft] = React.useState('');
  const [modules, setModules] = React.useState<string[]>([]);
  const [modulesDraft, setModulesDraft] = React.useState('');
  const [modulesOpen, setModulesOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const listRef = React.useRef<HTMLDivElement>(null);
  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [replies, recover] = await Promise.all([
        api<{ replies: Reply[] }>(`/api/replies${botQuery(bot)}`, token),
        api<{ modules: string[] }>(`/api/recover-modules${botQuery(bot)}`, token),
      ]);
      setItems(replies.replies);
      setSelected(current => replies.replies.some(item => item.key === current) ? current : replies.replies[0]?.key || '');
      setModules(recover.modules); setModulesDraft(recover.modules.join('\n'));
      return replies.replies;
    } catch (cause) { notify((cause as Error).message, true); }
    finally { setLoading(false); }
  }, [bot, token, notify]);
  React.useEffect(() => { setSelected(''); setCreating(false); setPage(1); void load(); }, [load]);
  const active = items.find(item => item.key === selected);
  React.useEffect(() => { if (!creating) setDraft(active?.value || ''); }, [active?.key, active?.value, creating]);
  React.useEffect(() => { onDirtyChange(creating ? Boolean(newKey || draft) : Boolean(active && draft !== active.value) || (modulesOpen && modulesDraft !== modules.join('\n'))); return () => onDirtyChange(false); }, [active, creating, newKey, draft, modulesOpen, modulesDraft, modules, onDirtyChange]);
  const filtered = items.filter(item => (!modifiedOnly || item.modified) && `${item.key} ${item.note} ${item.value}`.toLowerCase().includes(query.toLowerCase()));
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const hasDraft = creating ? Boolean(newKey || draft) : Boolean(active && draft !== active.value);
  const updateFilter = (nextQuery: string, nextModifiedOnly: boolean) => {
    const next = items.filter(item => (!nextModifiedOnly || item.modified) && `${item.key} ${item.note} ${item.value}`.toLowerCase().includes(nextQuery.toLowerCase()));
    if (!creating && !hasDraft && !next.some(item => item.key === selected)) setSelected(next[0]?.key || '');
    setQuery(nextQuery);
    setModifiedOnly(nextModifiedOnly);
    setPage(1);
    if (listRef.current) listRef.current.scrollTop = 0;
  };
  const discard = async () => !hasDraft || confirm('当前回复尚未保存，确定放弃修改吗？', { confirmLabel: '放弃修改', destructive: true });
  const goToPage = async (nextPage: number) => {
    if (nextPage === currentPage || !(await discard())) return;
    setPage(nextPage);
    setCreating(false);
    setSelected(filtered[(nextPage - 1) * PAGE_SIZE]?.key || '');
    if (listRef.current) listRef.current.scrollTop = 0;
  };
  const choose = async (key: string) => { if (!(await discard())) return; setCreating(false); setSelected(key); };
  const create = async () => { if (!(await discard())) return; setCreating(true); setSelected(''); setNewKey(''); setDraft(''); };
  const manage = async (action: string, data?: unknown, key?: string, value?: string) => {
    setBusy(true);
    try { await api('/api/replies/manage', token, { bot, action, data, key, value }); const updated = await load(); if (action === 'delete') setPage(1); notify('回复词已更新'); return updated; }
    catch (cause) { notify((cause as Error).message, true); throw cause; }
    finally { setBusy(false); }
  };
  const save = async () => {
    if (creating) { if (!newKey.trim()) { notify('请输入回复键', true); return; } try { const key = newKey.trim(); const updated = await manage('add', undefined, key, draft); setQuery(''); setModifiedOnly(false); setPage(Math.floor(Math.max(0, (updated || items).findIndex(item => item.key === key)) / PAGE_SIZE) + 1); setCreating(false); setSelected(key); } catch { /* shown by manage */ } return; }
    if (!active) return;
    setBusy(true);
    try { const result = await api<{ value: string }>('/api/replies', token, { bot, key: active.key, value: draft }); setItems(current => current.map(item => item.key === active.key ? { ...item, value: result.value, modified: true } : item)); setDraft(result.value); notify('回复已保存'); }
    catch (cause) { notify((cause as Error).message, true); }
    finally { setBusy(false); }
  };
  const resetOne = async () => { if (!active) return; setBusy(true); try { const result = await api<{ value: string }>('/api/replies', token, { bot, key: active.key, action: 'reset' }); setItems(current => current.map(item => item.key === active.key ? { ...item, value: result.value, modified: false } : item)); setDraft(result.value); notify('已恢复默认回复'); } catch (cause) { notify((cause as Error).message, true); } finally { setBusy(false); } };
  const exportJson = async () => { try { const result = await api<{ replies: Record<string, string> }>(`/api/replies/export${botQuery(bot)}`, token); saveJsonFile(result.replies, `olivadice-replies-${bot}.json`); } catch (cause) { notify((cause as Error).message, true); } };
  const importJson = async (file?: File) => { if (!file) return; try { const data = await readJsonFile(file); if (await confirm(`将导入 ${Object.keys(data).length} 条回复；文件中的同名回复会覆盖当前值，继续吗？`, { confirmLabel: '导入' })) await manage('import', data); } catch (cause) { notify((cause as Error).message, true); } if (inputRef.current) inputRef.current.value = ''; };
  const saveModules = async () => { const next = modulesDraft.split('\n').map(name => name.trim()).filter(Boolean); setBusy(true); try { await api('/api/recover-modules', token, { bot, modules: next }); await load(); notify('恢复模块列表已保存'); } catch (cause) { notify((cause as Error).message, true); } finally { setBusy(false); } };
  const confirmManage = async (message: string, action: string, key?: string) => { if (await confirm(message, { confirmLabel: action === 'delete' ? '删除' : action === 'reload' ? '重新加载' : '恢复', destructive: action !== 'reload' })) await manage(action, undefined, key); };
  return <><SectionTitle eyebrow="CUSTOM REPLIES" title="回复词列表" description="按键名或内容定位回复；覆盖值与恢复模块按账号保存。" />
    <div className="mb-5 flex flex-wrap gap-2"><input ref={inputRef} type="file" accept=".json,application/json" className="hidden" onChange={event => void importJson(event.target.files?.[0])} /><Button size="sm" variant="outline" onClick={() => inputRef.current?.click()} disabled={busy}><Upload className="mr-2 h-4 w-4" />导入回复</Button><Button size="sm" variant="outline" onClick={() => void exportJson()} disabled={busy}><Download className="mr-2 h-4 w-4" />导出 JSON</Button><Button size="sm" variant="outline" onClick={() => void confirmManage('从磁盘重新加载回复词？未保存的修改将被覆盖。', 'reload')} disabled={busy}><RotateCcw className="mr-2 h-4 w-4" />从磁盘刷新</Button><Button size="sm" variant="outline" onClick={() => setModulesOpen(current => !current)}><Settings2 className="mr-2 h-4 w-4" />恢复模块</Button><Button size="sm" variant="outline" className="text-rose-600" onClick={() => void confirmManage('恢复当前账号已加载模块的默认回复？已有自定义键会保留。', 'reset')} disabled={busy}>恢复模块默认</Button><Button size="sm" onClick={() => void create()}><Plus className="mr-2 h-4 w-4" />新增回复</Button></div>
    {modulesOpen && <Card className="mb-5 border-brand-200 bg-brand-50/40"><CardContent className="p-5"><div className="font-medium">恢复模块列表</div><p className="mt-1 text-xs text-slate-500">每行一个插件命名空间；恢复默认时，从已加载模块读取默认回复。清空后保存会恢复标准列表。</p><Textarea className="mt-3 min-h-28 font-mono text-sm" value={modulesDraft} onChange={event => setModulesDraft(event.target.value)} aria-label="恢复模块列表" /><div className="mt-3 flex justify-end"><Button size="sm" onClick={() => void saveModules()} disabled={busy || modulesDraft === modules.join('\n')}>保存模块列表</Button></div></CardContent></Card>}
    {loading ? <Busy /> : <div className="grid min-h-[600px] gap-4 lg:grid-cols-[320px_minmax(0,1fr)]"><Card className="flex min-h-0 flex-col overflow-hidden border-slate-200 shadow-sm"><div className="space-y-3 border-b p-4"><SearchField value={query} onChange={value => updateFilter(value, modifiedOnly)} placeholder="搜索键名或回复内容" /><div className="flex items-center justify-between text-xs text-slate-500"><span>{filtered.length} / {items.length} 条回复</span><label className="flex cursor-pointer items-center gap-1.5"><input type="checkbox" checked={modifiedOnly} onChange={event => updateFilter(query, event.target.checked)} />仅看已修改</label></div></div><div ref={listRef} className="max-h-[620px] flex-1 overflow-y-auto p-2">{pageItems.length ? pageItems.map(item => <button key={item.key} onClick={() => void choose(item.key)} className={`mb-1 w-full rounded-lg px-3 py-3 text-left transition-colors ${selected === item.key && !creating ? 'bg-brand-50 text-brand-800 ring-1 ring-brand-200' : 'hover:bg-slate-50'}`}><div className="flex items-center justify-between gap-2"><span className="truncate text-sm font-medium">{item.key}</span>{item.modified && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />}</div><p className="mt-1 truncate text-xs text-slate-500">{item.note || item.value || '空回复'}</p></button>) : <Empty title="没有匹配的回复" />}</div><div className="flex flex-wrap items-center justify-between gap-2 border-t px-3 py-2 text-xs text-slate-500"><span>{filtered.length ? `${(currentPage - 1) * PAGE_SIZE + 1}–${Math.min(currentPage * PAGE_SIZE, filtered.length)}` : '0'} / {filtered.length}</span><div className="flex items-center gap-2"><Button size="sm" variant="outline" disabled={currentPage <= 1} onClick={() => void goToPage(currentPage - 1)}>上一页</Button><Select ariaLabel="回复词页码" size="sm" className="w-24" placement="top" value={String(currentPage)} onChange={value => void goToPage(Number(value))} options={Array.from({ length: pageCount }, (_, index) => ({ value: String(index + 1), label: `${index + 1} / ${pageCount}` }))} /><Button size="sm" variant="outline" disabled={currentPage >= pageCount} onClick={() => void goToPage(currentPage + 1)}>下一页</Button></div></div></Card>
      <Card className="border-slate-200 shadow-sm"><CardContent className="p-5 md:p-7">{creating || active ? <><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2 text-xs font-medium text-brand-600"><Sparkles className="h-4 w-4" />{creating ? '新增自定义回复' : active?.default === null ? '自定义回复' : '当前词条'}</div>{creating ? <Input className="mt-2 max-w-sm font-mono" placeholder="新回复键，例如 strMyReply" value={newKey} onChange={event => setNewKey(event.target.value)} maxLength={200} /> : <h3 className="break-all font-mono text-xl font-semibold text-slate-900">{active?.key}</h3>}<p className="mt-2 whitespace-pre-line text-xs text-slate-500">{active?.note || '保留原有模板变量写法'}</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{draft.length} / 20000 字</span></div><div className="mt-6"><label htmlFor="reply-content" className="mb-2 block text-sm font-medium">回复内容</label><Textarea id="reply-content" className="min-h-[320px] resize-y bg-white font-mono text-sm leading-6" value={draft} maxLength={20000} onChange={event => setDraft(event.target.value)} /></div><div className="mt-4 flex flex-wrap justify-between gap-2"><div>{active?.default === null && !creating && <Button variant="outline" className="text-rose-600" disabled={busy} onClick={() => void confirmManage(`删除自定义回复「${active.key}」？`, 'delete', active.key)}><Trash2 className="mr-2 h-4 w-4" />删除</Button>}</div><div className="flex gap-2">{active?.default !== null && active?.modified && !creating && <Button variant="outline" onClick={() => void resetOne()} disabled={busy}><RotateCcw className="mr-2 h-4 w-4" />恢复默认</Button>}<Button onClick={() => void save()} disabled={busy || (!creating && draft === active?.value)}><Save className="mr-2 h-4 w-4" />{creating ? '添加回复' : '保存回复'}</Button></div></div></> : <Empty title="选择左侧回复词或新增" />}</CardContent></Card></div>}
  </>;
}
