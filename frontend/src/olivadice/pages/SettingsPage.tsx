import React from 'react';
import { Download, RotateCcw, SlidersHorizontal, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { api, botQuery, readJsonFile, saveJsonFile, type Setting } from '../api';
import { Busy, Empty, SearchField, SectionTitle } from '../ui';

type Props = { token: string; bot: string; notify: (message: string, error?: boolean) => void };
const listLabels: Record<string, string> = { noticeGroupList: '通知群列表', pulseUrlList: '心跳推送地址' };

function SettingRow({ item, save, reset }: { item: Setting; save: (key: string, value: number) => Promise<void>; reset: (key: string) => Promise<void> }) {
  const [draft, setDraft] = React.useState(String(item.value));
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => setDraft(String(item.value)), [item.value]);
  const valid = draft.trim() !== '' && Number.isInteger(Number(draft)) && Number(draft) >= item.min && Number(draft) <= item.max;
  const apply = async (value: number) => { setBusy(true); try { await save(item.key, value); } catch { setDraft(String(item.value)); } finally { setBusy(false); } };
  return <div className="flex flex-col gap-3 border-b border-slate-100 py-4 last:border-0 sm:flex-row sm:items-center sm:justify-between">
    <div className="min-w-0 flex-1 pr-4"><div className="text-sm font-medium text-slate-900">{item.label}</div><div className="mt-0.5 text-xs text-slate-500">{item.description || <code>{item.key}</code>}</div></div>
    <div className="flex items-center gap-2"><Button size="sm" variant="ghost" title={item.custom ? `删除 ${item.label}` : `恢复 ${item.label} 的默认值`} disabled={busy} onClick={() => { if (window.confirm(item.custom ? `删除扩展配置「${item.label}」？` : `恢复「${item.label}」的默认值？`)) void reset(item.key); }}><RotateCcw className="h-3.5 w-3.5" /><span className="sr-only">{item.custom ? '删除' : '恢复'} {item.label}</span></Button>
      {item.min === 0 && item.max === 1 ? <Switch aria-label={item.label} checked={item.value === 1} disabled={busy} onCheckedChange={checked => void apply(checked ? 1 : 0)} /> :
      <form className="flex items-center gap-2" onSubmit={event => { event.preventDefault(); if (valid) void apply(Number(draft)); }}><Input aria-label={item.label} type="number" min={item.min} max={item.max} step="1" className="w-28 bg-white text-right" value={draft} onChange={event => setDraft(event.target.value)} /><Button type="submit" size="sm" variant={Number(draft) === item.value ? 'outline' : 'default'} disabled={busy || !valid || Number(draft) === item.value}>保存</Button></form>}</div>
  </div>;
}

export function SettingsPage({ token, bot, notify }: Props) {
  const [items, setItems] = React.useState<Setting[]>([]);
  const [config, setConfig] = React.useState<Record<string, unknown>>({});
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const [section, setSection] = React.useState('全部');
  const [draftLists, setDraftLists] = React.useState<Record<string, string>>({});
  const inputRef = React.useRef<HTMLInputElement>(null);
  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [settings, data] = await Promise.all([
        api<{ switches: Setting[] }>(`/api/switches${botQuery(bot)}`, token),
        api<{ config: Record<string, unknown> }>(`/api/config${botQuery(bot)}`, token),
      ]);
      setItems(settings.switches); setConfig(data.config);
      setDraftLists(Object.fromEntries(Object.keys(listLabels).map(key => [key, JSON.stringify(data.config[key] || [], null, 2)])));
    } catch (cause) { notify((cause as Error).message, true); } finally { setLoading(false); }
  }, [bot, token, notify]);
  React.useEffect(() => { void load(); }, [load]);
  const apply = async (action: string, data?: unknown, key?: string) => {
    setBusy(true);
    try { await api('/api/config', token, { bot, action, data, key }); await load(); notify('配置已更新'); }
    catch (cause) { notify((cause as Error).message, true); throw cause; }
    finally { setBusy(false); }
  };
  const save = async (key: string, value: number) => { try { await api('/api/switches', token, { bot, key, value }); setItems(current => current.map(item => item.key === key ? { ...item, value } : item)); setConfig(current => ({ ...current, [key]: value })); notify('设置已保存'); } catch (cause) { notify((cause as Error).message, true); throw cause; } };
  const importFile = async (file?: File) => { if (!file) return; try { const data = await readJsonFile(file); if (window.confirm(`将导入 ${Object.keys(data).length} 项配置到当前账号，继续吗？`)) await apply('import', data); } catch (cause) { notify((cause as Error).message, true); } if (inputRef.current) inputRef.current.value = ''; };
  const exportFile = () => saveJsonFile(config, `olivadice-config-${bot}.json`);
  const sections = ['全部', ...new Set(items.map(item => item.section))];
  const filtered = items.filter(item => (section === '全部' || item.section === section) && `${item.label} ${item.key} ${item.description}`.toLowerCase().includes(query.toLowerCase()));
  const visibleSections = [...new Set(filtered.map(item => item.section))];
  const saveList = async (key: string) => { try { await apply('set-list', JSON.parse(draftLists[key]), key); } catch (cause) { notify((cause as Error).message, true); } };
  return <><SectionTitle eyebrow="CORE CONFIG" title="配置列表" description="修改运行中的配置；单项保存立即写入青果骰配置文件。" />
    <div className="mb-5 flex flex-wrap gap-2"><input ref={inputRef} type="file" accept=".json,application/json" className="hidden" onChange={event => void importFile(event.target.files?.[0])} /><Button size="sm" variant="outline" disabled={busy} onClick={() => inputRef.current?.click()}><Upload className="mr-2 h-4 w-4" />导入配置</Button><Button size="sm" variant="outline" disabled={busy} onClick={exportFile}><Download className="mr-2 h-4 w-4" />导出配置</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => { if (window.confirm('从磁盘重新加载当前账号配置？未保存的内存修改将被覆盖。')) void apply('reload'); }}><RotateCcw className="mr-2 h-4 w-4" />从磁盘刷新</Button><Button size="sm" variant="outline" className="text-rose-600" disabled={busy} onClick={() => { if (window.confirm('确定将当前账号配置恢复默认值？骰主列表会保留。')) void apply('reset'); }}>恢复全部默认值</Button></div>
    <div className="mb-5 grid gap-3 md:grid-cols-[1fr_auto]"><SearchField value={query} onChange={setQuery} placeholder="搜索设置名称或配置键" /><div className="flex max-w-full gap-1 overflow-x-auto rounded-lg border bg-white p-1">{sections.map(name => <button key={name} onClick={() => setSection(name)} className={`shrink-0 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${section === name ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>{name}</button>)}</div></div>
    {loading ? <Busy /> : !filtered.length ? <Empty title="没有匹配的配置项" detail="试试其他关键词或切换分类。" /> : <div className="space-y-4">{visibleSections.map(name => <Card key={name} className="border-slate-200 shadow-sm"><CardContent className="p-5"><div className="mb-1 flex items-center gap-2 border-b border-slate-100 pb-3"><SlidersHorizontal className="h-4 w-4 text-brand-600" /><h3 className="text-sm font-semibold">{name}</h3><span className="ml-auto text-xs text-slate-400">{filtered.filter(item => item.section === name).length} 项</span></div>{filtered.filter(item => item.section === name).map(item => <SettingRow key={`${bot}:${item.key}`} item={item} save={save} reset={key => apply('reset-key', undefined, key)} />)}</CardContent></Card>)}</div>}
    {!loading && <div className="mt-6 space-y-4"><SectionTitle title="列表型配置" description="每项填写 JSON 数组；通知群和心跳地址各项由两个文本值组成。骰主列表在“账号与骰主”页面维护。" />{Object.entries(listLabels).map(([key, label]) => <Card key={key} className="border-slate-200 shadow-sm"><CardContent className="p-5"><div className="flex items-center justify-between"><div><div className="text-sm font-semibold">{label}</div><code className="text-xs text-slate-500">{key}</code></div><Button size="sm" disabled={busy || draftLists[key] === JSON.stringify(config[key] || [], null, 2)} onClick={() => void saveList(key)}>保存列表</Button></div><Textarea className="mt-3 min-h-28 font-mono text-xs" value={draftLists[key] || '[]'} onChange={event => setDraftLists(current => ({ ...current, [key]: event.target.value }))} aria-label={label} /></CardContent></Card>)}</div>}
  </>;
}
