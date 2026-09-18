import React from 'react';
import { BookOpenText, Plus, RotateCcw, Save, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { api, botQuery, type HelpDoc } from '../api';
import { Busy, Empty, SearchField, SectionTitle } from '../ui';

type Props = { token: string; bot: string; notify: (message: string, error?: boolean) => void; onDirtyChange: (dirty: boolean) => void };
export function HelpPage({ token, bot, notify, onDirtyChange }: Props) {
  const [docs, setDocs] = React.useState<HelpDoc[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [query, setQuery] = React.useState('');
  const [selected, setSelected] = React.useState('');
  const [newKey, setNewKey] = React.useState('');
  const [creating, setCreating] = React.useState(false);
  const [draft, setDraft] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const load = React.useCallback(async () => { setLoading(true); try { const next = (await api<{ docs: HelpDoc[] }>(`/api/help${botQuery(bot)}`, token)).docs; setDocs(next); setSelected(current => next.some(item => item.key === current) ? current : next[0]?.key || ''); } catch (cause) { notify((cause as Error).message, true); } finally { setLoading(false); } }, [bot, token, notify]);
  React.useEffect(() => { setSelected(''); setCreating(false); void load(); }, [load]);
  const active = docs.find(doc => doc.key === selected);
  React.useEffect(() => { if (!creating) setDraft(active?.value || ''); }, [active?.key, active?.value, creating]);
  React.useEffect(() => { onDirtyChange(creating ? Boolean(newKey || draft) : Boolean(active && draft !== active.value)); return () => onDirtyChange(false); }, [active, creating, newKey, draft, onDirtyChange]);
  const filtered = docs.filter(doc => `${doc.key} ${doc.value}`.toLowerCase().includes(query.toLowerCase()));
  const choose = (key: string) => { if ((creating || draft !== active?.value) && !window.confirm('当前词条尚未保存，确定放弃修改吗？')) return; setCreating(false); setSelected(key); };
  const create = () => { if (active && draft !== active.value && !window.confirm('当前词条尚未保存，确定放弃修改吗？')) return; setSelected(''); setNewKey(''); setDraft(''); setCreating(true); };
  const save = async () => { const key = creating ? newKey.trim() : active?.key; if (!key) { notify('请输入词条名称', true); return; } if (creating && docs.some(doc => doc.key === key)) { notify('词条已存在，请在列表中编辑', true); return; } setBusy(true); try { await api('/api/help', token, { bot, key, value: draft }); await load(); setCreating(false); setSelected(key); notify('帮助词条已保存'); } catch (cause) { notify((cause as Error).message, true); } finally { setBusy(false); } };
  const remove = async () => { if (!active?.custom || !window.confirm(`确定删除自定义词条「${active.key}」吗？`)) return; setBusy(true); try { await api('/api/help', token, { bot, key: active.key, action: 'delete' }); setSelected(''); await load(); notify('词条已删除'); } catch (cause) { notify((cause as Error).message, true); } finally { setBusy(false); } };
  return <><SectionTitle eyebrow="HELP LIBRARY" title="词条列表" description="维护 .help 可查询的词条；内置词条可覆盖，自定义词条可删除。" action={<div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => void load()}><RotateCcw className="mr-2 h-4 w-4" />刷新</Button><Button size="sm" onClick={create}><Plus className="mr-2 h-4 w-4" />新增词条</Button></div>} />
    {loading ? <Busy /> : <div className="grid min-h-[600px] gap-4 lg:grid-cols-[320px_minmax(0,1fr)]"><Card className="overflow-hidden border-slate-200 shadow-sm"><div className="space-y-3 border-b p-4"><SearchField value={query} onChange={setQuery} placeholder="搜索词条或内容" /><div className="text-xs text-slate-500">{filtered.length} / {docs.length} 条词条</div></div><div className="max-h-[620px] overflow-y-auto p-2">{filtered.length ? filtered.slice(0, 200).map(doc => <button key={doc.key} onClick={() => choose(doc.key)} className={`mb-1 flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2.5 text-left text-sm ${selected === doc.key && !creating ? 'bg-brand-50 font-medium text-brand-800 ring-1 ring-brand-200' : 'hover:bg-slate-50'}`}><span className="truncate">{doc.key}</span>{doc.custom && <span className="shrink-0 rounded bg-brand-50 px-1.5 py-0.5 text-[10px] text-brand-600">自定义</span>}</button>) : <Empty title="没有匹配的词条" />}{filtered.length > 200 && <div className="p-3 text-center text-xs text-slate-500">只显示前 200 条，请输入关键词缩小范围</div>}</div></Card>
      <Card className="border-slate-200 shadow-sm"><CardContent className="p-5 md:p-7">{creating || active ? <><div className="flex items-center gap-2 text-xs font-medium text-brand-600"><BookOpenText className="h-4 w-4" />{creating ? '新建词条' : active?.custom ? '自定义词条' : '内置词条'}</div>{creating ? <div className="mt-5"><label htmlFor="help-key" className="mb-2 block text-sm font-medium">词条名称</label><Input id="help-key" maxLength={100} value={newKey} onChange={event => setNewKey(event.target.value)} placeholder="例如：跑团规则" /></div> : <h3 className="mt-3 break-all text-xl font-semibold">{active?.key}</h3>}<div className="mt-6"><label htmlFor="help-content" className="mb-2 block text-sm font-medium">帮助内容</label><Textarea id="help-content" className="min-h-[350px] resize-y bg-white text-sm leading-6" value={draft} maxLength={20000} onChange={event => setDraft(event.target.value)} /></div><div className="mt-4 flex flex-wrap justify-between gap-2"><div>{active?.custom && !creating && <Button variant="outline" className="text-rose-600 hover:text-rose-700" onClick={() => void remove()} disabled={busy}><Trash2 className="mr-2 h-4 w-4" />删除</Button>}</div><Button onClick={() => void save()} disabled={busy || (!creating && draft === active?.value)}><Save className="mr-2 h-4 w-4" />保存词条</Button></div></> : <Empty title="选择或新增帮助词条" />}</CardContent></Card></div>}
  </>;
}
