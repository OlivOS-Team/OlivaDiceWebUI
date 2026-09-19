import React from 'react';
import { Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { api } from '../api';
import { Busy, SectionTitle } from '../ui';

type Network = { bind: string; port: number; publicOrigin: string };
type NetworkState = {
  active: Network;
  saved: Network;
  afterRestart: Network;
  environmentOverrides: Record<keyof Network, boolean>;
  restartRequired: boolean;
};
type Draft = { bind: string; port: string; publicOrigin: string };
type Props = { token: string; notify: (message: string, error?: boolean) => void; onDirtyChange: (dirty: boolean) => void };
const toDraft = (value: Network): Draft => ({ ...value, port: String(value.port) });
const address = (value: Network) => value.publicOrigin || `http://${value.bind === '0.0.0.0' ? '127.0.0.1' : value.bind}:${value.port}`;

export function ServerPage({ token, notify, onDirtyChange }: Props) {
  const [state, setState] = React.useState<NetworkState | null>(null);
  const [draft, setDraft] = React.useState<Draft>({ bind: '127.0.0.1', port: '8765', publicOrigin: '' });
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const changed = Boolean(state && JSON.stringify(draft) !== JSON.stringify(toDraft(state.saved)));
  React.useEffect(() => { onDirtyChange(changed); return () => onDirtyChange(false); }, [changed, onDirtyChange]);
  React.useEffect(() => {
    void api<NetworkState>('/api/server-config', token)
      .then(value => { setState(value); setDraft(toDraft(value.saved)); })
      .catch(cause => notify((cause as Error).message, true))
      .finally(() => setLoading(false));
  }, [token, notify]);
  const save = async () => {
    if (!/^\d+$/.test(draft.port)) { notify('端口必须是 1–65535 的整数', true); return; }
    setBusy(true);
    try {
      const value = await api<NetworkState>('/api/server-config', token, {
        bind: draft.bind.trim(), port: Number(draft.port), publicOrigin: draft.publicOrigin.trim(),
      });
      setState(value);
      setDraft(toDraft(value.saved));
      notify(value.restartRequired ? '服务设置已保存，重启 OlivOS 后生效' : '服务设置已保存');
    } catch (cause) { notify((cause as Error).message, true); }
    finally { setBusy(false); }
  };
  const field = (key: keyof Network, title: string, hint: string, control: React.ReactNode) => <div>
    <div className="mb-2 flex flex-wrap items-center gap-2"><label htmlFor={`server-${key}`} className="text-sm font-medium">{title}</label>{state?.environmentOverrides[key] && <span className="rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-700">环境变量覆盖</span>}</div>
    {control}<p className="mt-1.5 text-xs leading-5 text-slate-500">{hint}</p>
  </div>;
  return <><SectionTitle eyebrow="WEBUI SERVER" title="服务设置" description="配置 WebUI 的监听地址、端口和远程访问入口。设置保存在 OlivOS 运行目录中。" />
    {loading ? <Busy /> : state && <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
      <Card className="border-slate-200 shadow-sm"><CardContent className="space-y-6 p-6">
        {field('bind', '监听地址', '仅本机访问填 127.0.0.1；允许局域网或 VPN 访问可填 0.0.0.0，或本机的指定 IPv4 地址。', <Input id="server-bind" value={draft.bind} onChange={event => setDraft(current => ({ ...current, bind: event.target.value }))} placeholder="127.0.0.1" className="font-mono" />)}
        {field('port', '监听端口', '可用端口范围为 1–65535；更改后需使用新端口重新打开页面。', <Input id="server-port" type="number" min={1} max={65535} value={draft.port} onChange={event => setDraft(current => ({ ...current, port: event.target.value }))} className="font-mono" />)}
        {field('publicOrigin', '远程访问地址', '非本机监听时必填，例如 http://192.168.1.10:8765；使用反向代理时填浏览器实际访问的 HTTPS 来源地址，不含路径。', <Input id="server-publicOrigin" type="url" value={draft.publicOrigin} onChange={event => setDraft(current => ({ ...current, publicOrigin: event.target.value }))} placeholder="https://dice.example.com" className="font-mono" />)}
        <div className="flex justify-end border-t pt-5"><Button disabled={busy || !changed} onClick={() => void save()}><Save className="mr-2 h-4 w-4" />保存服务设置</Button></div>
      </CardContent></Card>
      <div className="space-y-4"><Card className="border-slate-200 shadow-sm"><CardContent className="space-y-3 p-5 text-sm"><h3 className="font-semibold">当前运行</h3><div className="text-slate-500">监听 <code className="break-all text-slate-700">{state.active.bind}:{state.active.port}</code></div><div className="text-slate-500">访问 <code className="break-all text-slate-700">{address(state.active)}</code></div></CardContent></Card>
        <Card className={state.restartRequired ? 'border-amber-200 bg-amber-50' : 'border-slate-200'}><CardContent className="space-y-3 p-5 text-sm"><h3 className="font-semibold">重启后生效</h3><div className="text-slate-600">监听 <code className="break-all">{state.afterRestart.bind}:{state.afterRestart.port}</code></div><div className="text-slate-600">访问 <code className="break-all">{address(state.afterRestart)}</code></div><p className="text-xs leading-5 text-slate-600">{state.restartRequired ? '设置已保存；重启 OlivOS 后，再用新地址打开 WebUI。' : '当前运行的服务已使用这组设置。'}{Object.values(state.environmentOverrides).some(Boolean) && ' 已设置的环境变量优先于页面保存值。'}</p></CardContent></Card></div>
    </div>}
  </>;
}
