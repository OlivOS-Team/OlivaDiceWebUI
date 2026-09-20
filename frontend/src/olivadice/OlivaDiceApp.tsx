import React from 'react';
import { Archive, ArrowRight, Blocks, BookOpenText, Bot, Files, Globe2, LayoutDashboard, LogOut, Menu, MessageSquareReply, Moon, PanelLeft, PanelTop, RotateCcw, Settings2, ShieldCheck, Sparkles, Sun, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { api, botQuery, standalone, type Account, type Deck, type HelpDoc, type Reply, type Setting } from './api';
import { Notice, SectionTitle, Select, useConfirm } from './ui';
import { AccountsPage } from './pages/AccountsPage';
import { BackupPage } from './pages/BackupPage';
import { ChanceCustomPage } from './pages/ChanceCustomPage';
import olivaLogo from './assets/olivos.svg?raw';
import { DecksPage } from './pages/DecksPage';
import { HelpPage } from './pages/HelpPage';
import { RepliesPage } from './pages/RepliesPage';
import { ServerPage } from './pages/ServerPage';
import { SettingsPage } from './pages/SettingsPage';

type View = 'dashboard' | 'accounts' | 'settings' | 'replies' | 'chance-custom' | 'help' | 'decks' | 'backup' | 'server';
type NavLayout = 'top' | 'side';
type Theme = 'light' | 'dark';
const labels: Record<View, string> = { dashboard: '工作台', accounts: '账号与骰主', settings: '核心配置', replies: '回复词', 'chance-custom': '程心自定义', help: '帮助文档', decks: '牌堆管理', backup: '自动备份', server: '服务设置' };
const nav = [
  { heading: '概览', items: [{ id: 'dashboard' as View, icon: LayoutDashboard }, { id: 'accounts' as View, icon: Bot }] },
  { heading: '内容管理', items: [{ id: 'replies' as View, icon: MessageSquareReply }, { id: 'chance-custom' as View, icon: Blocks }, { id: 'help' as View, icon: BookOpenText }, { id: 'decks' as View, icon: Files }] },
  { heading: '系统', items: [{ id: 'settings' as View, icon: Settings2 }, { id: 'backup' as View, icon: Archive }, ...(standalone ? [{ id: 'server' as View, icon: Globe2 }] : [])] },
];
const needsBot = (view: View) => ['replies', 'help'].includes(view);
const initialView = (): View => { const hash = location.hash.slice(1) as View; return hash in labels && (standalone || hash !== 'server') ? hash : 'dashboard'; };
const preferenceKey = (name: string) => `olivadice-${standalone ? 'standalone' : 'official'}-${name}`;
const readPreference = <T extends string>(name: string, allowed: readonly T[], fallback: T): T => { try { const value = localStorage.getItem(preferenceKey(name)) as T | null; return value && allowed.includes(value) ? value : fallback; } catch { return fallback; } };
const writePreference = (name: string, value: string) => { try { localStorage.setItem(preferenceKey(name), value); } catch { /* Official plugin frames may have an opaque origin. */ } };
type Shared = { token: string; bot: string; notify: (message: string, error?: boolean) => void };
const LogoMark = ({ large = false }: { large?: boolean }) => <span aria-hidden="true" className={`block shrink-0 [&_svg]:h-full [&_svg]:w-full ${large ? 'h-44 w-44 brightness-0 invert' : 'h-10 w-10'}`} dangerouslySetInnerHTML={{ __html: olivaLogo }} />;

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
  return <><div className="banner-shadow relative overflow-hidden rounded-2xl bg-gradient-to-r from-brand-800 via-brand-700 to-brand-500 px-7 py-8 text-white md:px-10 md:py-10"><div className="relative z-10 max-w-2xl"><div className="flex items-center gap-2 text-[11px] font-bold tracking-[0.22em] text-brand-200"><Sparkles className="h-4 w-4" />OLIVADICE CONTROL CENTER</div><h2 className="mt-5 text-3xl font-bold tracking-tight md:text-4xl">青果骰管理工作台</h2><p className="mt-3 max-w-xl text-sm leading-7 text-brand-100">从账号出发，管理核心配置、回复词、帮助文档与牌堆。更改作用于当前运行的 OlivOS 进程。</p><Button className="mt-6 bg-sky-50 text-brand-800 hover:bg-sky-100 dark:bg-sky-200 dark:text-sky-950 dark:hover:bg-sky-100" onClick={() => navigate('accounts')}>查看账号 <ArrowRight className="ml-2 h-4 w-4" /></Button></div><div aria-hidden="true" className="absolute -right-24 -top-28 h-96 w-96 rotate-12 rounded-[5rem] border border-white/20 bg-white/5" /><div aria-hidden="true" className="pointer-events-none absolute -right-9 top-0 hidden h-72 w-72 rotate-12 items-center justify-center xl:flex rounded-[4rem] border border-white/20 bg-white/10"><div className="-rotate-12 opacity-80"><LogoMark large /></div></div></div>
    {masterCommand && <Card className="mt-5 border-brand-100 bg-brand-50/60"><CardContent className="flex flex-wrap items-center gap-3 p-4"><div className="min-w-0 flex-1"><div className="text-sm font-semibold text-brand-900">成为骰主</div><p className="mt-1 text-xs text-brand-700">复制认证指令并发送给骰子。</p></div><Button size="sm" variant="outline" onClick={() => void navigator.clipboard.writeText(masterCommand).then(() => notify('认证指令已复制')).catch(() => notify('复制失败，请检查浏览器剪贴板权限', true))}>复制认证指令</Button></CardContent></Card>}
    <div className="mt-7"><SectionTitle title="运行概况" description={scope ? `当前查看：${current?.label || scope}` : 'OlivOS 尚未加载机器人账号'} /></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map(item => <button key={item.label} onClick={() => navigate(item.action)} className="text-left"><Card className="h-full border-slate-200 shadow-sm transition-all hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-md"><CardContent className="p-5"><div className="flex items-center justify-between"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><item.icon className="h-4 w-4" /></span><ArrowRight className="h-4 w-4 text-slate-300" /></div><div className="mt-5 text-2xl font-semibold text-slate-900">{loading ? '—' : item.value}</div><div className="mt-1 text-xs text-slate-500">{item.label}</div></CardContent></Card></button>)}</div>
    <div className="mt-8 grid gap-5 lg:grid-cols-[1.5fr_1fr]"><Card className="border-slate-200 shadow-sm"><CardContent className="p-6"><div className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-brand-600" /><h3 className="font-semibold">当前账号</h3></div>{current ? <><div className="mt-5 flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-4 py-4"><div><div className="font-medium">{current.platform} · {current.id}</div><div className="mt-1 text-xs text-slate-500">{current.model || '默认模型'} · {scope}</div></div><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${stats.enabled ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'}`}>{loading ? '读取中' : stats.enabled ? '全局开关：开' : '全局开关：关'}</span></div><div className="mt-4 flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => navigate('settings')}>核心配置</Button><Button size="sm" variant="outline" onClick={() => navigate('accounts')}>骰主权限</Button></div></> : <p className="mt-5 text-sm text-slate-500">请先在 OlivOS 中配置机器人账号。</p>}</CardContent></Card><Card className="border-slate-200 shadow-sm"><CardContent className="p-6"><div className="flex items-center gap-2"><Files className="h-5 w-5 text-brand-600" /><h3 className="font-semibold">可抽取分组</h3></div><div className="mt-5 text-3xl font-semibold">{loading ? '—' : stats.decks}</div><p className="mt-1 text-sm text-slate-500">当前账号已加载的分组数量</p><Button className="mt-5" size="sm" variant="outline" onClick={() => navigate('decks')}>查看牌堆 <ArrowRight className="ml-2 h-4 w-4" /></Button></CardContent></Card></div>
  </>;
}

export function OlivaDiceApp() {
  const confirm = useConfirm();
  const preview = standalone ? location.protocol === 'file:' : window.parent === window;
  const [token, setToken] = React.useState(() => standalone ? sessionStorage.getItem('olivadice-token') || '' : '');
  const [inputToken, setInputToken] = React.useState('');
  const [connected, setConnected] = React.useState(false);
  const [version, setVersion] = React.useState('');
  const [accounts, setAccounts] = React.useState<Account[]>([]);
  const [bot, setBot] = React.useState(() => standalone ? sessionStorage.getItem('olivadice-bot') || 'unity' : 'unity');
  const [view, setView] = React.useState<View>(initialView);
  const [navLayout, setNavLayout] = React.useState<NavLayout>(() => readPreference('layout', ['top', 'side'], standalone ? 'side' : 'top'));
  const [theme, setTheme] = React.useState<Theme>(() => readPreference('theme', ['light', 'dark'], matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [notice, setNotice] = React.useState({ message: '', error: false });
  const dirty = React.useRef(false);
  const connectedOnce = React.useRef(false);
  const viewRef = React.useRef(view);
  const onDirtyChange = React.useCallback((value: boolean) => { dirty.current = value; }, []);
  const notify = React.useCallback((message: string, error = false) => setNotice({ message, error }), []);
  const connect = React.useCallback(async (key: string) => { setLoading(true); try { const result = await api<{ accounts: Account[]; version: string }>('/api/accounts', key); setAccounts(result.accounts); setVersion(result.version); const stored = standalone ? sessionStorage.getItem('olivadice-bot') : null; const next = stored && result.accounts.some(item => item.hash === stored) ? stored : result.accounts.find(item => item.hash !== 'unity')?.hash || 'unity'; setBot(current => connectedOnce.current && result.accounts.some(item => item.hash === current) ? current : next); connectedOnce.current = true; if (standalone) { sessionStorage.setItem('olivadice-bot', next); sessionStorage.setItem('olivadice-token', key); setToken(key); } setConnected(true); notify(''); } catch (cause) { if (standalone) sessionStorage.removeItem('olivadice-token'); setConnected(false); notify((cause as Error).message, true); } finally { setLoading(false); } }, [notify]);
  React.useEffect(() => { if (!preview && (!standalone || token)) void connect(token); else if (!standalone) notify('请从 OlivOS WebUI 的「插件页面」打开青果骰管理。', true); }, []);
  React.useEffect(() => { viewRef.current = view; }, [view]);
  React.useEffect(() => { document.documentElement.classList.toggle('dark', theme === 'dark'); document.documentElement.style.colorScheme = theme; writePreference('theme', theme); }, [theme]);
  React.useEffect(() => { writePreference('layout', navLayout); setMenuOpen(false); }, [navLayout]);
  React.useEffect(() => { const onHash = () => { void (async () => { const next = initialView(); if (next !== viewRef.current && dirty.current) { if (!(await confirm('当前修改尚未保存，确定离开吗？', { confirmLabel: '放弃修改', destructive: true }))) { location.hash = viewRef.current; return; } dirty.current = false; } setView(next); })(); }; window.addEventListener('hashchange', onHash); return () => window.removeEventListener('hashchange', onHash); }, [confirm]);
  React.useEffect(() => { const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty.current) event.preventDefault(); }; window.addEventListener('beforeunload', beforeUnload); return () => window.removeEventListener('beforeunload', beforeUnload); }, []);
  const selectBot = async (next: string) => { if (next !== bot && dirty.current) { if (!(await confirm('当前修改尚未保存，确定切换账号吗？', { confirmLabel: '放弃修改', destructive: true }))) return false; dirty.current = false; } setBot(next); if (standalone) sessionStorage.setItem('olivadice-bot', next); notify(''); return true; };
  const navigate = async (next: View) => { if (next !== view && dirty.current) { if (!(await confirm('当前修改尚未保存，确定离开吗？', { confirmLabel: '放弃修改', destructive: true }))) return; dirty.current = false; } if (needsBot(next) && bot === 'unity') { const first = accounts.find(item => item.hash !== 'unity'); if (first) await selectBot(first.hash); } setView(next); location.hash = next; setMenuOpen(false); notify(''); };
  const logout = async () => { if (dirty.current) { if (!(await confirm('当前修改尚未保存，确定退出吗？', { confirmLabel: '放弃修改', destructive: true }))) return; dirty.current = false; } sessionStorage.removeItem('olivadice-token'); connectedOnce.current = false; setToken(''); setConnected(false); setAccounts([]); setVersion(''); setInputToken(''); notify(''); };
  const current = accounts.find(account => account.hash === bot);
  if (!connected) return <div className="min-h-screen bg-background text-foreground">
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-4 py-10 md:px-8">
      <Notice message={notice.message} error={notice.error} onClose={() => notify('')} />
      {preview && <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{standalone ? '当前打开的是静态页面预览。请使用独立服务地址打开页面，才能读取和保存数据。' : '当前页面没有 OlivOS 宿主消息桥。请先登录 OlivOS WebUI，再从侧栏的「插件页面」打开。'}</div>}
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="relative flex min-h-[360px] items-center overflow-hidden rounded-2xl bg-gradient-to-br from-brand-800 via-brand-700 to-brand-500 p-8 text-white md:p-10">
          <div className="relative z-10 max-w-sm">
            <div className="flex items-center gap-2 text-xs font-semibold tracking-[0.2em] text-brand-200"><Sparkles className="h-4 w-4" />OLIVADICE CONTROL CENTER</div>
            <h1 className="mt-7 text-3xl font-bold md:text-4xl">连接青果骰</h1>
            <p className="mt-4 text-sm leading-7 text-brand-100">{standalone ? '从电脑或手机打开管理地址，使用令牌配置运行中的 OlivOS 与青果骰。' : '通过 OlivOS WebUI 的安全消息桥读取并管理当前运行的青果骰。'}</p>
          </div>
          <div aria-hidden="true" className="pointer-events-none absolute -right-24 -top-28 h-96 w-96 rotate-12 rounded-[5rem] border border-white/20 bg-white/5" />
          <div aria-hidden="true" className="pointer-events-none absolute -right-9 top-0 hidden h-72 w-72 rotate-12 items-center justify-center rounded-[4rem] border border-white/20 bg-white/10 xl:flex"><div className="-rotate-12 opacity-80"><LogoMark large /></div></div>
        </section>
        <Card className="flex items-center border-slate-200 shadow-sm"><CardContent className="w-full p-7 md:p-9">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><ShieldCheck className="h-5 w-5" /></div>
          {standalone ? <>
            <h2 className="mt-5 text-xl font-semibold">输入管理令牌</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">令牌位于 OlivOS 运行目录的 <code className="rounded bg-slate-100 px-1">plugin/data/OlivaDiceWebUIStandalone/admin-token.txt</code>。</p>
            <form className="mt-6 space-y-3" onSubmit={event => { event.preventDefault(); void connect(inputToken.trim()); }}><Input type="password" autoComplete="off" value={inputToken} onChange={event => setInputToken(event.target.value)} placeholder="粘贴管理令牌" disabled={preview} required /><Button className="w-full" disabled={loading || preview}>{loading ? '正在连接…' : '连接管理服务'} <ArrowRight className="ml-2 h-4 w-4" /></Button></form>
            <p className="mt-4 text-xs leading-5 text-slate-500">首次远程访问：先在 OlivOS 主机上登录，在「服务设置」填写监听地址、端口和远程访问地址；保存并重启 OlivOS 后，再从其他设备打开。</p>
          </> : <>
            <h2 className="mt-5 text-xl font-semibold">{loading ? '正在连接插件…' : '未连接到宿主'}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">{notice.message || 'OlivOS WebUI 负责登录认证，插件页面不会接触宿主令牌。'}</p>
            <Button className="mt-6 w-full" disabled={loading || preview} onClick={() => void connect('')}>{loading ? '正在连接…' : '重新连接'} <ArrowRight className="ml-2 h-4 w-4" /></Button>
            <p className="mt-4 text-xs leading-5 text-slate-500">需要 OlivOS 0.11.90-alpha.2 或更新版本，并从宿主侧栏打开此页面。</p>
          </>}
        </CardContent></Card>
      </div>
    </main>
  </div>;
  const accountSelect = (mobile = false) => <div className={mobile ? 'sm:hidden' : 'hidden sm:block'}><Select ariaLabel={mobile ? '移动端账号选择' : '当前账号'} size="sm" className="w-56" value={bot} onChange={value => void selectBot(value)} options={accounts.map(account => ({ value: account.hash, label: account.label }))} /></div>;
  const controls = () => <div className="flex items-center gap-1">{accountSelect()}<Button size="icon" variant="ghost" onClick={() => setTheme(value => value === 'dark' ? 'light' : 'dark')} title={theme === 'dark' ? '切换为浅色模式' : '切换为深色模式'}>{theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</Button><Button size="icon" variant="ghost" onClick={() => setNavLayout(value => value === 'side' ? 'top' : 'side')} title={navLayout === 'side' ? '切换为顶部导航' : '切换为左侧导航'}>{navLayout === 'side' ? <PanelTop className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}</Button><Button size="icon" variant="ghost" onClick={() => void connect(token)} title="刷新账号列表"><RotateCcw className="h-4 w-4" /></Button>{standalone && <Button size="icon" variant="ghost" onClick={() => void logout()} title="退出管理"><LogOut className="h-4 w-4" /></Button>}</div>;
  const globalScope = view === 'backup' || view === 'server' || !current || bot === 'unity';
  const scopeLabel = globalScope ? '全局设置' : (current?.label || '全局设置');
  const scopeBadge = <span className="inline-flex items-center gap-1.5"><span>当前范围：</span><span className={globalScope ? 'font-semibold text-rose-600 dark:text-rose-400' : 'font-semibold text-emerald-600 dark:text-amber-300'}>{scopeLabel}</span></span>;
  const page = <main className="mx-auto max-w-[1440px] px-4 py-6 md:px-8 md:py-8"><div className="mb-4 flex min-h-9 items-center justify-between gap-3 text-xs text-muted-foreground">{scopeBadge}{connected && accountSelect(true)}</div>
    <Notice message={notice.message} error={notice.error} onClose={() => notify('')} />
    {view === 'dashboard' && <Dashboard token={token} bot={bot} accounts={accounts} navigate={navigate} notify={notify} />}
    {view === 'accounts' && <AccountsPage token={token} bot={bot} accounts={accounts} selectBot={selectBot} notify={notify} />}
    {view === 'settings' && <SettingsPage token={token} bot={bot} notify={notify} />}
    {view === 'replies' && (bot === 'unity' ? <SelectAccount accounts={accounts} selectBot={selectBot} /> : <RepliesPage token={token} bot={bot} notify={notify} onDirtyChange={onDirtyChange} />)}
    {view === 'chance-custom' && <ChanceCustomPage token={token} bot={bot} notify={notify} onDirtyChange={onDirtyChange} />}
    {view === 'help' && (bot === 'unity' ? <SelectAccount accounts={accounts} selectBot={selectBot} /> : <HelpPage token={token} bot={bot} notify={notify} onDirtyChange={onDirtyChange} />)}
    {view === 'decks' && <DecksPage token={token} bot={bot} notify={notify} />}
    {view === 'backup' && <BackupPage token={token} notify={notify} />}
    {standalone && view === 'server' && <ServerPage token={token} notify={notify} onDirtyChange={onDirtyChange} />}
  </main>;
  return <div className="min-h-screen bg-background text-foreground">
    {navLayout === 'side' ? <>
      {menuOpen && <button className="fixed inset-0 z-30 bg-slate-950/40 lg:hidden" aria-label="关闭菜单" onClick={() => setMenuOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-card transition-transform lg:translate-x-0 ${menuOpen ? 'translate-x-0' : '-translate-x-full'}`}><div className="flex h-16 items-center gap-3 border-b px-5"><LogoMark /><div className="min-w-0"><div className="text-base font-bold tracking-tight text-brand-600">青果骰</div><div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">OlivaDice WebUI</div></div><button className="ml-auto lg:hidden" aria-label="关闭菜单" onClick={() => setMenuOpen(false)}><X className="h-5 w-5" /></button></div><nav className="flex-1 space-y-6 overflow-y-auto px-3 py-6">{nav.map(group => <div key={group.heading}><div className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">{group.heading}</div><div className="space-y-1">{group.items.map(({ id, icon: Icon }) => <button key={id} onClick={() => void navigate(id)} className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors ${view === id ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-200' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}><Icon className="h-[18px] w-[18px]" /><span>{labels[id]}</span>{view === id && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-brand-500" />}</button>)}</div></div>)}</nav><div className="border-t p-4"><div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2.5 text-xs text-muted-foreground"><span className="h-2 w-2 rounded-full bg-emerald-500" />管理服务已连接<span className="ml-auto">{version && `v${version}`}</span></div></div></aside>
      <div className="min-w-0 lg:pl-64"><header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b bg-card/95 px-4 backdrop-blur md:px-8"><div className="flex min-w-0 items-center gap-3"><Button size="icon" variant="ghost" className="lg:hidden" onClick={() => setMenuOpen(true)}><Menu className="h-5 w-5" /></Button><div className="truncate text-xs text-muted-foreground">青果骰 <span className="mx-1">/</span> <span className="font-medium text-foreground">{labels[view]}</span></div></div>{controls()}</header>{page}</div>
    </> : <>
      <header className="sticky top-0 z-20 border-b bg-card/95 backdrop-blur"><div className="flex h-16 items-center justify-between gap-3 px-4 md:px-8"><div className="flex min-w-0 items-center gap-3"><LogoMark /><div className="min-w-0"><div className="text-sm font-bold text-brand-600">青果骰</div><div className="hidden text-[10px] uppercase tracking-wider text-muted-foreground sm:block">OlivaDice WebUI</div></div></div>{controls()}</div><nav className="flex gap-1 overflow-x-auto border-t px-3 py-2 md:px-8">{nav.flatMap(group => group.items).map(({ id, icon: Icon }) => <button key={id} onClick={() => void navigate(id)} className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${view === id ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-200' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}><Icon className="h-4 w-4" />{labels[id]}</button>)}</nav></header>{page}
    </>}
  </div>;
}
function SelectAccount({ accounts, selectBot }: { accounts: Account[]; selectBot: (bot: string) => Promise<boolean> }) { const bots = accounts.filter(item => item.hash !== 'unity'); return <Card className="max-w-xl"><CardContent className="p-7"><h2 className="font-semibold">请选择机器人账号</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">回复词和帮助文档由 OlivaDiceCore 按账号保存，不属于可直接编辑的全局设置。</p>{bots.length ? <div className="mt-5 flex flex-wrap gap-2">{bots.map(item => <Button key={item.hash} variant="outline" onClick={() => void selectBot(item.hash)}>{item.label}</Button>)}</div> : <p className="mt-4 text-sm text-amber-700 dark:text-amber-300">当前 OlivOS 尚未加载机器人账号。</p>}</CardContent></Card>; }
