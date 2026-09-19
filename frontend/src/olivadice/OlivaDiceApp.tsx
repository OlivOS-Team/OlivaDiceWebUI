import React from 'react';
import { Archive, ArrowRight, BookOpenText, Bot, ChevronDown, Files, LayoutDashboard, Menu, MessageSquareReply, RotateCcw, Settings2, ShieldCheck, Sparkles, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { api, botQuery, type Account, type Deck, type HelpDoc, type Reply, type Setting } from './api';
import { Notice, SectionTitle } from './ui';
import { AccountsPage } from './pages/AccountsPage';
import { BackupPage } from './pages/BackupPage';
import olivaLogo from './assets/olivos.svg';
import { DecksPage } from './pages/DecksPage';
import { HelpPage } from './pages/HelpPage';
import { RepliesPage } from './pages/RepliesPage';
import { SettingsPage } from './pages/SettingsPage';

type View = 'dashboard' | 'accounts' | 'settings' | 'replies' | 'help' | 'decks' | 'backup';
const labels: Record<View, string> = { dashboard: '工作台', accounts: '账号与骰主', settings: '核心配置', replies: '回复词', help: '帮助文档', decks: '牌堆管理', backup: '自动备份' };
const nav = [
  { heading: '概览', items: [{ id: 'dashboard' as View, icon: LayoutDashboard }, { id: 'accounts' as View, icon: Bot }] },
  { heading: '内容管理', items: [{ id: 'replies' as View, icon: MessageSquareReply }, { id: 'help' as View, icon: BookOpenText }, { id: 'decks' as View, icon: Files }] },
  { heading: '系统', items: [{ id: 'settings' as View, icon: Settings2 }, { id: 'backup' as View, icon: Archive }] },
];
const needsBot = (view: View) => ['replies', 'help'].includes(view);
const initialView = (): View => { const hash = location.hash.slice(1) as View; return hash in labels ? hash : 'dashboard'; };
type Shared = { token: string; bot: string; notify: (message: string, error?: boolean) => void };

function Dashboard({ token, bot, accounts, navigate, notify }: Shared & { accounts: Account[]; navigate: (view: View) => void }) {
  const [stats, setStats] = React.useState({ settings: 0, replies: 0, docs: 0, decks: 0, enabled: false });
  const [masterCommand, setMasterCommand] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const scope = bot === 'unity' ? accounts.find(item => item.hash !== 'unity')?.hash : bot;
  React.useEffect(() => { void api<{ command: string | null }>('/api/master-command', token).then(result => setMasterCommand(result.command)).catch(() => setMasterCommand(null)); }, [token]);
  React.useEffect(() => { if (!scope) { setLoading(false); return; } let active = true; setLoading(true); Promise.allSettled([
    api<{ switches: Setting[] }>(`/api/switches${botQuery(scope)}`, token),
    api<{ replies: Reply[] }>(`/api/replies${botQuery(scope)}`, token),
    api<{ docs: HelpDoc[] }>(`/api/help${botQuery(scope)}`, token),
    api<{ decks: Deck[]; groupCount: number }>(`/api/decks${botQuery(scope)}`, token),
  ]).then(results => { if (!active) return; const [a, b, c, d] = results; setStats({ settings: a.status === 'fulfilled' ? a.value.switches.length : 0, enabled: a.status === 'fulfilled' && a.value.switches.some(item => item.key === 'globalEnable' && item.value === 1), replies: b.status === 'fulfilled' ? b.value.replies.length : 0, docs: c.status === 'fulfilled' ? c.value.docs.length : 0, decks: d.status === 'fulfilled' ? d.value.groupCount : 0 }); if (results.some(result => result.status === 'rejected')) notify('部分统计读取失败，请进入对应页面检查。', true); setLoading(false); }); return () => { active = false; }; }, [scope, token, notify]);
  const current = accounts.find(account => account.hash === scope);
  const cards = [
    { label: '机器人账号', value: accounts.length - 1, icon: Bot, action: 'accounts' as View },
    { label: '配置项', value: stats.settings, icon: Settings2, action: 'settings' as View },
    { label: '回复词', value: stats.replies, icon: MessageSquareReply, action: 'replies' as View },
    { label: '帮助词条', value: stats.docs, icon: BookOpenText, action: 'help' as View },
  ];
  return <><div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-brand-800 via-brand-700 to-brand-500 px-7 py-8 text-white shadow-lg shadow-brand-100 md:px-10 md:py-10"><div className="relative z-10 max-w-2xl"><div className="flex items-center gap-2 text-[11px] font-bold tracking-[0.22em] text-brand-200"><Sparkles className="h-4 w-4" />OLIVADICE CONTROL CENTER</div><h2 className="mt-5 text-3xl font-bold tracking-tight md:text-4xl">青果骰管理工作台</h2><p className="mt-3 max-w-xl text-sm leading-7 text-brand-100">从账号出发，管理核心配置、回复词、帮助文档与牌堆。更改作用于当前运行的 OlivOS 进程。</p><Button className="mt-6 bg-white text-brand-800 hover:bg-brand-50" onClick={() => navigate('accounts')}>查看账号 <ArrowRight className="ml-2 h-4 w-4" /></Button></div><div aria-hidden="true" className="absolute -right-24 -top-28 h-96 w-96 rotate-12 rounded-[5rem] border border-white/20 bg-white/5" /><div aria-hidden="true" className="pointer-events-none absolute -right-9 top-0 hidden h-72 w-72 rotate-12 items-center justify-center xl:flex rounded-[4rem] border border-white/20 bg-white/10"><img src={olivaLogo} alt="" className="h-44 w-44 -rotate-12 object-contain opacity-80 brightness-0 invert drop-shadow-lg" /></div></div>
    {masterCommand && <Card className="mt-5 border-brand-100 bg-brand-50/60"><CardContent className="flex flex-wrap items-center gap-3 p-4"><div className="min-w-0 flex-1"><div className="text-sm font-semibold text-brand-900">成为骰主</div><p className="mt-1 text-xs text-brand-700">复制认证指令并发送给骰子。</p></div><Button size="sm" variant="outline" onClick={() => void navigator.clipboard.writeText(masterCommand).then(() => notify('认证指令已复制')).catch(() => notify('复制失败，请检查浏览器剪贴板权限', true))}>复制认证指令</Button></CardContent></Card>}
    <div className="mt-7"><SectionTitle title="运行概况" description={scope ? `当前查看：${current?.label || scope}` : 'OlivOS 尚未加载机器人账号'} /></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map(item => <button key={item.label} onClick={() => navigate(item.action)} className="text-left"><Card className="h-full border-slate-200 shadow-sm transition-all hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-md"><CardContent className="p-5"><div className="flex items-center justify-between"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><item.icon className="h-4 w-4" /></span><ArrowRight className="h-4 w-4 text-slate-300" /></div><div className="mt-5 text-2xl font-semibold text-slate-900">{loading ? '—' : item.value}</div><div className="mt-1 text-xs text-slate-500">{item.label}</div></CardContent></Card></button>)}</div>
    <div className="mt-8 grid gap-5 lg:grid-cols-[1.5fr_1fr]"><Card className="border-slate-200 shadow-sm"><CardContent className="p-6"><div className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-brand-600" /><h3 className="font-semibold">当前账号</h3></div>{current ? <><div className="mt-5 flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-4 py-4"><div><div className="font-medium">{current.platform} · {current.id}</div><div className="mt-1 text-xs text-slate-500">{current.model || '默认模型'} · {scope}</div></div><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${stats.enabled ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'}`}>{loading ? '读取中' : stats.enabled ? '全局开关：开' : '全局开关：关'}</span></div><div className="mt-4 flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => navigate('settings')}>核心配置</Button><Button size="sm" variant="outline" onClick={() => navigate('accounts')}>骰主权限</Button></div></> : <p className="mt-5 text-sm text-slate-500">请先在 OlivOS 中配置机器人账号。</p>}</CardContent></Card><Card className="border-slate-200 shadow-sm"><CardContent className="p-6"><div className="flex items-center gap-2"><Files className="h-5 w-5 text-brand-600" /><h3 className="font-semibold">可抽取分组</h3></div><div className="mt-5 text-3xl font-semibold">{loading ? '—' : stats.decks}</div><p className="mt-1 text-sm text-slate-500">当前账号已加载的分组数量</p><Button className="mt-5" size="sm" variant="outline" onClick={() => navigate('decks')}>查看牌堆 <ArrowRight className="ml-2 h-4 w-4" /></Button></CardContent></Card></div>
  </>;
}

export function OlivaDiceApp() {
  const preview = window.parent === window;
  const token = '';
  const [connected, setConnected] = React.useState(false);
  const [version, setVersion] = React.useState('');
  const [accounts, setAccounts] = React.useState<Account[]>([]);
  const [bot, setBot] = React.useState('unity');
  const [view, setView] = React.useState<View>(initialView);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [notice, setNotice] = React.useState({ message: '', error: false });
  const dirty = React.useRef(false);
  const viewRef = React.useRef(view);
  const onDirtyChange = React.useCallback((value: boolean) => { dirty.current = value; }, []);
  const notify = React.useCallback((message: string, error = false) => setNotice({ message, error }), []);
  const connect = React.useCallback(async () => { setLoading(true); try { const result = await api<{ accounts: Account[]; version: string }>('/api/accounts', token); setAccounts(result.accounts); setVersion(result.version); const next = result.accounts.find(item => item.hash !== 'unity')?.hash || 'unity'; setBot(current => result.accounts.some(item => item.hash === current) ? current : next); setConnected(true); notify(''); } catch (cause) { setConnected(false); notify((cause as Error).message, true); } finally { setLoading(false); } }, [notify]);
  React.useEffect(() => { if (!preview) void connect(); else notify('请从 OlivOS WebUI 的「插件页面」打开青果骰管理。', true); }, [connect, notify, preview]);
  React.useEffect(() => { viewRef.current = view; }, [view]);
  React.useEffect(() => { const onHash = () => { const next = initialView(); if (next !== viewRef.current && dirty.current) { if (!window.confirm('当前修改尚未保存，确定离开吗？')) { location.hash = viewRef.current; return; } dirty.current = false; } setView(next); }; window.addEventListener('hashchange', onHash); return () => window.removeEventListener('hashchange', onHash); }, []);
  React.useEffect(() => { const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty.current) event.preventDefault(); }; window.addEventListener('beforeunload', beforeUnload); return () => window.removeEventListener('beforeunload', beforeUnload); }, []);
  const selectBot = (next: string) => { if (next !== bot && dirty.current) { if (!window.confirm('当前修改尚未保存，确定切换账号吗？')) return; dirty.current = false; } setBot(next); notify(''); };
  const navigate = (next: View) => { if (next !== view && dirty.current) { if (!window.confirm('当前修改尚未保存，确定离开吗？')) return; dirty.current = false; } if (needsBot(next) && bot === 'unity') { const first = accounts.find(item => item.hash !== 'unity'); if (first) selectBot(first.hash); } setView(next); location.hash = next; setMenuOpen(false); notify(''); };
  const current = accounts.find(account => account.hash === bot);
  if (!connected) return <div className="min-h-screen bg-[#f5faff] text-slate-900">
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-4 py-10 md:px-8">
      <Notice message={notice.message} error={notice.error} onClose={() => notify('')} />
      {preview && <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">当前页面没有 OlivOS 宿主消息桥。请先登录 OlivOS WebUI，再从侧栏的「插件页面」打开。</div>}
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="relative flex min-h-[360px] items-center overflow-hidden rounded-2xl bg-gradient-to-br from-brand-800 via-brand-700 to-brand-500 p-8 text-white md:p-10">
          <div className="relative z-10 max-w-sm">
            <div className="flex items-center gap-2 text-xs font-semibold tracking-[0.2em] text-brand-200"><Sparkles className="h-4 w-4" />OLIVADICE CONTROL CENTER</div>
            <h1 className="mt-7 text-3xl font-bold md:text-4xl">连接青果骰</h1>
            <p className="mt-4 text-sm leading-7 text-brand-100">通过 OlivOS WebUI 的安全消息桥读取并管理当前运行的青果骰。</p>
          </div>
          <div aria-hidden="true" className="pointer-events-none absolute -right-24 -top-28 h-96 w-96 rotate-12 rounded-[5rem] border border-white/20 bg-white/5" />
          <div aria-hidden="true" className="pointer-events-none absolute -right-9 top-0 hidden h-72 w-72 rotate-12 items-center justify-center rounded-[4rem] border border-white/20 bg-white/10 xl:flex"><img src={olivaLogo} alt="" className="h-44 w-44 -rotate-12 object-contain opacity-80 brightness-0 invert drop-shadow-lg" /></div>
        </section>
        <Card className="flex items-center border-slate-200 shadow-sm"><CardContent className="w-full p-7 md:p-9">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><ShieldCheck className="h-5 w-5" /></div>
          <h2 className="mt-5 text-xl font-semibold">{loading ? '正在连接插件…' : '未连接到宿主'}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">{notice.message || 'OlivOS WebUI 负责登录认证，插件页面不会接触宿主令牌。'}</p>
          <Button className="mt-6 w-full" disabled={loading || preview} onClick={() => void connect()}>{loading ? '正在连接…' : '重新连接'} <ArrowRight className="ml-2 h-4 w-4" /></Button>
          <p className="mt-4 text-xs leading-5 text-slate-500">需要 OlivOS 0.11.90-alpha.2 或更新版本，并从宿主侧栏打开此页面。</p>
        </CardContent></Card>
      </div>
    </main>
  </div>;
  return <div className="min-h-screen bg-[#f5faff] text-slate-900">
    {menuOpen && <button className="fixed inset-0 z-30 bg-slate-950/40 lg:hidden" aria-label="关闭菜单" onClick={() => setMenuOpen(false)} />}
    <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform lg:translate-x-0 ${menuOpen ? 'translate-x-0' : '-translate-x-full'}`}><div className="flex h-16 items-center gap-3 border-b px-5"><img src={olivaLogo} alt="青果骰 OlivaDice" className="h-10 w-10 shrink-0 object-contain" /><div className="min-w-0"><div className="text-base font-bold tracking-tight text-brand-700">青果骰</div><div className="text-[10px] font-medium uppercase tracking-wider text-slate-400">OlivaDice WebUI</div></div><button className="ml-auto lg:hidden" aria-label="关闭菜单" onClick={() => setMenuOpen(false)}><X className="h-5 w-5" /></button></div><nav className="flex-1 space-y-6 overflow-y-auto px-3 py-6">{nav.map(group => <div key={group.heading}><div className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.15em] text-slate-400">{group.heading}</div><div className="space-y-1">{group.items.map(({ id, icon: Icon }) => <button key={id} onClick={() => navigate(id)} className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors ${view === id ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'}`}><Icon className="h-[18px] w-[18px]" /><span>{labels[id]}</span>{view === id && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-brand-500" />}</button>)}</div></div>)}</nav><div className="border-t p-4"><div className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2.5 text-xs text-slate-600"><span className={`h-2 w-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-slate-300'}`} />{connected ? '管理服务已连接' : '等待连接'}<span className="ml-auto text-slate-400">{version && `v${version}`}</span></div></div></aside>
    <div className="min-w-0 lg:pl-64"><header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:px-8"><div className="flex min-w-0 items-center gap-3"><Button size="icon" variant="ghost" className="lg:hidden" onClick={() => setMenuOpen(true)}><Menu className="h-5 w-5" /></Button><div className="truncate text-xs text-slate-500">青果骰 <span className="mx-1 text-slate-300">/</span> <span className="font-medium text-slate-800">{labels[view]}</span></div></div><div className="flex items-center gap-2">{connected && <><div className="relative hidden sm:block"><select aria-label="当前账号" value={bot} onChange={event => selectBot(event.target.value)} className="h-9 max-w-56 appearance-none truncate rounded-lg border bg-white py-1 pl-3 pr-8 text-xs font-medium text-slate-700 outline-none focus:ring-2 focus:ring-brand-300">{accounts.map(account => <option key={account.hash} value={account.hash}>{account.label}</option>)}</select><ChevronDown className="pointer-events-none absolute right-2 top-2.5 h-4 w-4 text-slate-400" /></div><Button size="sm" variant="ghost" onClick={() => void connect()} title="刷新账号列表"><RotateCcw className="h-4 w-4" /><span className="ml-2 hidden md:inline">刷新账号</span></Button></>}</div></header>
      <main className="mx-auto max-w-[1440px] px-4 py-6 md:px-8 md:py-8"><div className="mb-6 flex flex-wrap items-end justify-between gap-3"><div><div className="mb-1 text-[11px] font-bold uppercase tracking-[0.18em] text-brand-600">管理面板</div><h1 className="text-2xl font-bold tracking-tight md:text-3xl">{labels[view]}</h1><p className="mt-1 text-sm text-slate-500">{view === 'backup' ? '当前范围：全局配置' : `当前范围：${current?.label || '全局配置'}`}</p></div>{connected && <select aria-label="移动端账号选择" value={bot} onChange={event => selectBot(event.target.value)} className="h-9 max-w-full rounded-lg border bg-white px-3 text-xs text-slate-700 sm:hidden">{accounts.map(account => <option key={account.hash} value={account.hash}>{account.label}</option>)}</select>}</div>
      <Notice message={notice.message} error={notice.error} onClose={() => notify('')} />
        {view === 'dashboard' && <Dashboard token={token} bot={bot} accounts={accounts} navigate={navigate} notify={notify} />}
        {view === 'accounts' && <AccountsPage token={token} bot={bot} accounts={accounts} selectBot={selectBot} notify={notify} />}
        {view === 'settings' && <SettingsPage token={token} bot={bot} notify={notify} />}
        {view === 'replies' && (bot === 'unity' ? <SelectAccount /> : <RepliesPage token={token} bot={bot} notify={notify} onDirtyChange={onDirtyChange} />)}
        {view === 'help' && (bot === 'unity' ? <SelectAccount /> : <HelpPage token={token} bot={bot} notify={notify} onDirtyChange={onDirtyChange} />)}
        {view === 'decks' && <DecksPage token={token} bot={bot} notify={notify} />}
        {view === 'backup' && <BackupPage token={token} notify={notify} />}
      </main></div></div>;
}
function SelectAccount() { return <Card className="max-w-xl"><CardContent className="p-7 text-sm text-slate-600">请在页面右上角选择一个机器人账号。</CardContent></Card>; }
