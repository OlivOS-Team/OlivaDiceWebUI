import React from 'react';
import { Download, Link2Off, Package, Plus, RotateCcw, Save, Trash2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { api, botQuery, downloadFile, uploadFile, type ChanceCustomState, type ChanceRule } from '../api';
import { Busy, Empty, SearchField, SectionTitle, Select, useConfirm } from '../ui';

type Props = { token: string; bot: string; notify: (message: string, error?: boolean) => void; onDirtyChange: (dirty: boolean) => void };
type Tab = 'rules' | 'packages' | 'defaults';
const PAGE_SIZE = 100;
const emptyRule = (): ChanceRule => ({ key: '', division: '1', matchType: 'full', matchPlace: '3', priority: 0, value: '' });
const matchTypeLabels: Record<ChanceRule['matchType'], string> = { full: '完全匹配', contain: '模糊匹配', perfix: '前缀匹配', reg: '正则匹配' };
const matchPlaceLabels: Record<ChanceRule['matchPlace'], string> = { '1': '群聊触发', '2': '私聊触发', '3': '群聊和私聊' };

export function ChanceCustomPage({ token, bot, notify, onDirtyChange }: Props) {
  const confirm = useConfirm();
  const [state, setState] = React.useState<ChanceCustomState | null>(null);
  const [tab, setTab] = React.useState<Tab>('rules');
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const [page, setPage] = React.useState(1);
  const [selected, setSelected] = React.useState('');
  const [creating, setCreating] = React.useState(false);
  const [draft, setDraft] = React.useState<ChanceRule>(emptyRule);
  const [defaultDraft, setDefaultDraft] = React.useState<Record<string, string>>({});
  const [packageQuery, setPackageQuery] = React.useState('');
  const [exportInfo, setExportInfo] = React.useState({ name: '', author: '', version: '1.0', info: '' });
  const [exportKeys, setExportKeys] = React.useState<string[]>([]);
  const fileRef = React.useRef<HTMLInputElement>(null);
  const listRef = React.useRef<HTMLDivElement>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const next = await api<ChanceCustomState>(`/api/chance-custom${botQuery(bot)}`, token);
      setState(next);
      setSelected(current => next.rules.some(item => item.key === current) ? current : next.rules[0]?.key || '');
      setDefaultDraft(Object.fromEntries(next.defaults.map(item => [item.key, item.value])));
      setExportKeys(current => current.filter(key => next.rules.some(item => item.key === key)));
      return next;
    } catch (cause) { notify((cause as Error).message, true); }
    finally { setLoading(false); }
  }, [bot, token, notify]);

  React.useEffect(() => { setSelected(''); setCreating(false); setPage(1); setQuery(''); void load(); }, [load]);
  const active = state?.rules.find(item => item.key === selected);
  React.useEffect(() => { if (!creating) setDraft(active ? { ...active } : emptyRule()); }, [active?.key, active?.division, active?.matchType, active?.matchPlace, active?.priority, active?.value, creating]);
  const ruleDirty = creating ? Object.values(draft).some(value => value !== '' && value !== 0 && value !== '1' && value !== '3' && value !== 'full') : Boolean(active && JSON.stringify(active) !== JSON.stringify(draft));
  const defaultsDirty = Boolean(state && state.defaults.some(item => (defaultDraft[item.key] ?? '') !== item.value));
  React.useEffect(() => { onDirtyChange(ruleDirty || defaultsDirty); return () => onDirtyChange(false); }, [ruleDirty, defaultsDirty, onDirtyChange]);

  const discardRule = async () => !ruleDirty || confirm('当前回复规则尚未保存，确定放弃修改吗？', { confirmLabel: '放弃修改', destructive: true });
  const choose = async (key: string) => { if (!(await discardRule())) return; setCreating(false); setSelected(key); };
  const create = async () => { if (!(await discardRule())) return; setCreating(true); setSelected(''); setDraft(emptyRule()); };
  const changeTab = async (next: Tab) => {
    if (next === tab) return;
    if ((ruleDirty || defaultsDirty) && !(await confirm('当前修改尚未保存，确定切换页面吗？', { confirmLabel: '放弃修改', destructive: true }))) return;
    if (defaultsDirty && state) setDefaultDraft(Object.fromEntries(state.defaults.map(item => [item.key, item.value])));
    if (ruleDirty) { setCreating(false); setDraft(active ? { ...active } : emptyRule()); }
    setTab(next); setQuery('');
  };
  const refresh = async () => {
    if ((ruleDirty || defaultsDirty) && !(await confirm('从 ChanceCustom 重新读取配置？未保存的修改会丢失。', { confirmLabel: '重新读取', destructive: true }))) return;
    setCreating(false); await load(); notify('已重新读取 ChanceCustom 配置');
  };
  const mutate = async (path: string, data: Record<string, unknown>, message: string) => {
    if (!state) return;
    setBusy(true);
    try { await api(path, token, { bot, revision: state.revision, ...data }); await load(); notify(message); }
    catch (cause) { notify((cause as Error).message, true); }
    finally { setBusy(false); }
  };
  const saveRule = async () => {
    if (!draft.key.trim()) { notify('请输入关键词', true); return; }
    if (creating && draft.value.length < 2) { notify('新增规则的回复内容至少需要 2 个字符', true); return; }
    if (!Number.isInteger(draft.priority)) { notify('优先级必须是整数', true); return; }
    const key = draft.key.trim();
    await mutate('/api/chance-custom/rules', { action: creating ? 'create' : 'update', originalKey: active?.key, rule: { ...draft, key } }, creating ? '回复规则已添加' : '回复规则已保存');
    setCreating(false); setSelected(key);
  };
  const deleteRule = async () => {
    if (!active || !state || !(await confirm(`删除回复规则「${active.key}」？`, { confirmLabel: '删除', destructive: true }))) return;
    await mutate('/api/chance-custom/rules', { action: 'delete', originalKey: active.key }, '回复规则已删除');
    setCreating(false); setPage(1);
  };
  const saveDefaults = async () => { await mutate('/api/chance-custom/defaults', { values: defaultDraft }, '默认回复已保存'); };
  const uploadPackage = async (file?: File) => {
    if (!file || !state) return;
    if (!file.name.toLowerCase().endsWith('.ccpk')) { notify('请选择 .ccpk 回复包', true); return; }
    if (!(await confirm(`将回复包「${file.name}」安装到${bot === 'unity' ? '全局' : '当前账号'}？包内同名规则会覆盖现有规则。`, { confirmLabel: '安装' }))) return;
    setBusy(true);
    try {
      const path = `/api/chance-custom/packages/upload?bot=${encodeURIComponent(bot)}&revision=${encodeURIComponent(state.revision)}&name=${encodeURIComponent(file.name)}`;
      await uploadFile(path, token, file); await load(); notify('CCPK 回复包已安装');
    } catch (cause) { notify((cause as Error).message, true); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ''; }
  };
  const packageAction = async (name: string, action: 'uninstall' | 'unbind' | 'reinstall') => {
    const messages = { uninstall: `卸载回复包「${name}」并删除仍与包内原值一致的规则？已修改的规则会保留。`, unbind: `解绑回复包「${name}」？现有规则会全部保留。`, reinstall: `重新安装回复包「${name}」中当前缺失的规则？现有同名规则不会覆盖。` };
    if (!(await confirm(messages[action], { confirmLabel: action === 'reinstall' ? '重新安装' : action === 'unbind' ? '解绑' : '卸载', destructive: action === 'uninstall' }))) return;
    await mutate('/api/chance-custom/packages/manage', { action, name }, action === 'reinstall' ? '缺失规则已重新安装' : action === 'unbind' ? '回复包已解绑' : '回复包已卸载');
  };
  const exportPackage = async () => {
    if (!exportInfo.name.trim()) { notify('请输入导出包名称', true); return; }
    if (!exportKeys.length) { notify('请至少选择一条回复规则', true); return; }
    setBusy(true);
    try {
      const filename = `${exportInfo.name.trim().replace(/[\\/:*?"<>|]/g, '_')}.ccpk`;
      await downloadFile(`/api/chance-custom/packages/export${botQuery(bot)}`, token, filename,
        { bot, info: { ...exportInfo, name: exportInfo.name.trim() }, keys: exportKeys });
      notify(`已下载 ${exportKeys.length} 条规则`);
    } catch (cause) { notify((cause as Error).message, true); }
    finally { setBusy(false); }
  };

  if (loading && !state) return <Busy />;
  if (!state?.available) return <><SectionTitle eyebrow="CHANCE CUSTOM" title="程心自定义" description="远程管理 ChanceCustom 的回复规则、默认回复和 CCPK。" /><Empty title="ChanceCustom 未加载" detail={state?.reason || '请安装并启用 ChanceCustom，然后重启 OlivOS。'} /></>;
  if (!state.writable) return <><SectionTitle eyebrow="CHANCE CUSTOM" title="程心自定义" description={`已检测到 ChanceCustom ${state.version || ''}`} /><Empty title="当前配置只能读取" detail={state.reason} /></>;

  const filtered = state.rules.filter(item => `${item.key} ${item.value} ${item.division}`.toLowerCase().includes(query.toLowerCase()));
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const goToPage = async (next: number) => { if (!(await discardRule())) return; setCreating(false); setPage(next); setSelected(filtered[(next - 1) * PAGE_SIZE]?.key || ''); listRef.current?.scrollTo({ top: 0 }); };
  const packageRuleMatches = state.rules.filter(item => `${item.key} ${item.value}`.toLowerCase().includes(packageQuery.toLowerCase()));
  const toggleExport = (key: string) => setExportKeys(current => current.includes(key) ? current.filter(item => item !== key) : [...current, key]);

  return <><SectionTitle eyebrow="CHANCE CUSTOM" title="程心自定义" description={`ChanceCustom ${state.version || '未知版本'} · 数据版本 ${state.dataVersion} · 当前范围 ${bot === 'unity' ? '全局' : '账号'}`} action={<Button size="sm" variant="outline" onClick={() => void refresh()} disabled={busy}><RotateCcw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />重新读取</Button>} />
    <div className="mb-5 flex flex-wrap gap-2 border-b pb-3">{([['rules', `回复规则 ${state.rules.length}`], ['packages', `回复包 ${state.packages.length}`], ['defaults', '默认回复']] as const).map(([id, label]) => <button key={id} onClick={() => void changeTab(id)} className={`rounded-lg px-4 py-2 text-sm font-medium ${tab === id ? 'bg-brand-50 text-brand-700' : 'text-muted-foreground hover:bg-muted'}`}>{label}</button>)}</div>

    {tab === 'rules' && <><div className="mb-4 flex justify-end"><Button size="sm" onClick={() => void create()} disabled={busy}><Plus className="mr-2 h-4 w-4" />新增规则</Button></div><div className="grid min-h-[620px] gap-4 lg:grid-cols-[340px_minmax(0,1fr)]"><Card className="flex min-h-0 flex-col overflow-hidden border-slate-200 shadow-sm"><div className="space-y-3 border-b p-4"><SearchField value={query} onChange={value => { setQuery(value); setPage(1); }} placeholder="搜索关键词、回复或分群" /><div className="text-xs text-muted-foreground">{filtered.length} / {state.rules.length} 条规则</div></div><div ref={listRef} className="max-h-[650px] flex-1 overflow-y-auto p-2">{pageItems.length ? pageItems.map(item => <button key={item.key} onClick={() => void choose(item.key)} className={`mb-1 w-full rounded-lg px-3 py-3 text-left ${selected === item.key && !creating ? 'bg-brand-50 text-brand-800 ring-1 ring-brand-200' : 'hover:bg-muted'}`}><div className="flex items-center gap-2"><span className="min-w-0 flex-1 truncate text-sm font-medium">{item.key}</span><span className="text-[10px] text-muted-foreground">P{item.priority}</span></div><p className="mt-1 truncate text-xs text-muted-foreground">{matchTypeLabels[item.matchType]} · {matchPlaceLabels[item.matchPlace]} · {item.value || '空回复'}</p></button>) : <Empty title="没有匹配的规则" />}</div><div className="flex flex-wrap items-center justify-between gap-2 border-t px-3 py-2 text-xs text-muted-foreground"><span>{filtered.length ? `${(currentPage - 1) * PAGE_SIZE + 1}–${Math.min(currentPage * PAGE_SIZE, filtered.length)}` : '0'} / {filtered.length}</span><div className="flex items-center gap-2"><Button size="sm" variant="outline" disabled={currentPage <= 1} onClick={() => void goToPage(currentPage - 1)}>上一页</Button><Select ariaLabel="程心规则页码" size="sm" className="w-24" placement="top" value={String(currentPage)} onChange={value => void goToPage(Number(value))} options={Array.from({ length: pageCount }, (_, index) => ({ value: String(index + 1), label: `${index + 1} / ${pageCount}` }))} /><Button size="sm" variant="outline" disabled={currentPage >= pageCount} onClick={() => void goToPage(currentPage + 1)}>下一页</Button></div></div></Card>
      <Card className="border-slate-200 shadow-sm"><CardContent className="p-5 md:p-7">{creating || active ? <><div className="flex items-center justify-between gap-3"><div><div className="text-xs font-semibold text-brand-600">{creating ? '新增回复规则' : '编辑回复规则'}</div><h3 className="mt-1 text-lg font-semibold">{creating ? '设置触发条件和回复' : active?.key}</h3></div><span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">回复 {draft.value.length} 字</span></div><div className="mt-6 grid gap-4 md:grid-cols-2"><label className="text-sm font-medium">关键词<Input className="mt-2 font-mono" value={draft.key} maxLength={500} onChange={event => setDraft(value => ({ ...value, key: event.target.value }))} /></label><label className="text-sm font-medium">优先级<Input className="mt-2" type="number" value={draft.priority} onChange={event => setDraft(value => ({ ...value, priority: Number(event.target.value) }))} /></label><label className="text-sm font-medium">匹配方式<Select className="mt-2" value={draft.matchType} onChange={value => setDraft(item => ({ ...item, matchType: value as ChanceRule['matchType'] }))} options={Object.entries(matchTypeLabels).map(([value, label]) => ({ value, label }))} /></label><label className="text-sm font-medium">触发场景<Select className="mt-2" value={draft.matchPlace} onChange={value => setDraft(item => ({ ...item, matchPlace: value as ChanceRule['matchPlace'] }))} options={Object.entries(matchPlaceLabels).map(([value, label]) => ({ value, label }))} /></label></div><label className="mt-4 block text-sm font-medium">分群 / 分人<Input className="mt-2 font-mono" value={draft.division} maxLength={4000} onChange={event => setDraft(value => ({ ...value, division: event.target.value }))} /><span className="mt-1 block text-xs font-normal text-muted-foreground">填写 1 表示不限；多个群号或用户 ID 使用 * 分隔。</span></label><label className="mt-4 block text-sm font-medium">回复内容<Textarea className="mt-2 min-h-[260px] resize-y font-mono text-sm leading-6" value={draft.value} maxLength={20000} onChange={event => setDraft(value => ({ ...value, value: event.target.value }))} /></label><div className="mt-5 flex flex-wrap justify-between gap-2"><div>{!creating && active && <Button variant="outline" className="text-rose-600" disabled={busy} onClick={() => void deleteRule()}><Trash2 className="mr-2 h-4 w-4" />删除规则</Button>}</div><Button onClick={() => void saveRule()} disabled={busy || !ruleDirty}><Save className="mr-2 h-4 w-4" />保存规则</Button></div></> : <Empty title="选择左侧规则或新增" />}</CardContent></Card></div></>}

    {tab === 'defaults' && <Card className="border-slate-200 shadow-sm"><CardContent className="p-5 md:p-7"><div className="grid gap-5 lg:grid-cols-2">{state.defaults.map(item => <label key={item.key} className="text-sm font-medium">{item.label}<Textarea className="mt-2 min-h-24 font-mono text-sm" value={defaultDraft[item.key] ?? ''} maxLength={20000} onChange={event => setDefaultDraft(value => ({ ...value, [item.key]: event.target.value }))} />{bot !== 'unity' && <span className="mt-1 block text-xs font-normal text-muted-foreground">{item.inherited ? `当前为空，实际使用全局值：${item.effective || '空'}` : '当前账号已覆盖全局值'}</span>}</label>)}</div><div className="mt-6 flex justify-end"><Button disabled={busy || !defaultsDirty} onClick={() => void saveDefaults()}><Save className="mr-2 h-4 w-4" />保存默认回复</Button></div></CardContent></Card>}

    {tab === 'packages' && <div className="space-y-5"><div className="flex flex-wrap gap-2"><input ref={fileRef} type="file" accept=".ccpk,application/octet-stream" className="hidden" onChange={event => void uploadPackage(event.target.files?.[0])} /><Button size="sm" onClick={() => fileRef.current?.click()} disabled={busy}><Upload className="mr-2 h-4 w-4" />安装 CCPK</Button></div>{state.packages.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{state.packages.map(item => <Card key={item.name} className="border-slate-200 shadow-sm"><CardContent className="p-5"><div className="flex items-start gap-3"><Package className="mt-0.5 h-5 w-5 text-brand-600" /><div className="min-w-0"><div className="break-all font-semibold">{item.name}</div><div className="mt-1 text-xs text-muted-foreground">{item.author || '未知作者'} · {item.version || '无版本'} · {item.ruleCount} 条规则</div></div></div><p className="mt-3 min-h-10 text-sm text-muted-foreground">{item.description || '没有说明'}</p><div className="mt-4 flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => void packageAction(item.name, 'reinstall')} disabled={busy}><RotateCcw className="mr-1 h-3.5 w-3.5" />补回缺失规则</Button><Button size="sm" variant="outline" onClick={() => void packageAction(item.name, 'unbind')} disabled={busy}><Link2Off className="mr-1 h-3.5 w-3.5" />解绑</Button><Button size="sm" variant="outline" className="text-rose-600" onClick={() => void packageAction(item.name, 'uninstall')} disabled={busy}><Trash2 className="mr-1 h-3.5 w-3.5" />卸载</Button></div></CardContent></Card>)}</div> : <Empty title="当前范围没有已安装的回复包" detail="可以上传数据版本 2 的 CCPK。" />}
      <Card className="border-slate-200 shadow-sm"><CardContent className="p-5 md:p-7"><h3 className="font-semibold">制作并导出 CCPK</h3><p className="mt-1 text-sm text-muted-foreground">从当前范围选择规则，生成可由 ChanceCustom 导入的回复包。</p><div className="mt-5 grid gap-4 md:grid-cols-3"><label className="text-sm font-medium">包名称<Input className="mt-2" value={exportInfo.name} maxLength={200} onChange={event => setExportInfo(value => ({ ...value, name: event.target.value }))} /></label><label className="text-sm font-medium">作者<Input className="mt-2" value={exportInfo.author} maxLength={200} onChange={event => setExportInfo(value => ({ ...value, author: event.target.value }))} /></label><label className="text-sm font-medium">版本<Input className="mt-2" value={exportInfo.version} maxLength={100} onChange={event => setExportInfo(value => ({ ...value, version: event.target.value }))} /></label></div><label className="mt-4 block text-sm font-medium">说明<Textarea className="mt-2 min-h-20" value={exportInfo.info} maxLength={10000} onChange={event => setExportInfo(value => ({ ...value, info: event.target.value }))} /></label><div className="mt-5 flex flex-wrap items-center gap-2"><div className="min-w-[240px] flex-1"><SearchField value={packageQuery} onChange={setPackageQuery} placeholder="筛选要打包的规则" /></div><Button size="sm" variant="outline" onClick={() => setExportKeys(current => Array.from(new Set([...current, ...packageRuleMatches.map(item => item.key)])))}>全选筛选结果</Button><Button size="sm" variant="outline" onClick={() => setExportKeys([])}>清空</Button></div><div className="mt-3 max-h-64 overflow-y-auto rounded-lg border p-2">{packageRuleMatches.length ? packageRuleMatches.map(item => <label key={item.key} className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-muted"><input type="checkbox" checked={exportKeys.includes(item.key)} onChange={() => toggleExport(item.key)} /><span className="min-w-0 flex-1 truncate">{item.key}</span><span className="text-xs text-muted-foreground">{matchTypeLabels[item.matchType]}</span></label>) : <Empty title="没有匹配的规则" />}</div><div className="mt-4 flex items-center justify-between gap-3"><span className="text-sm text-muted-foreground">已选择 {exportKeys.length} 条规则</span><Button disabled={busy || !exportKeys.length || !exportInfo.name.trim()} onClick={() => void exportPackage()}><Download className="mr-2 h-4 w-4" />导出 CCPK</Button></div></CardContent></Card></div>}
  </>;
}
