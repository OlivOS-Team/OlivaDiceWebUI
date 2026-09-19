import React from 'react';
import { AlertCircle, CheckCircle2, LoaderCircle, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

type ConfirmOptions = { title?: string; confirmLabel?: string; destructive?: boolean };
type ConfirmRequest = ConfirmOptions & { message: string; resolve: (confirmed: boolean) => void };
type ConfirmFunction = (message: string, options?: ConfirmOptions) => Promise<boolean>;
const ConfirmContext = React.createContext<ConfirmFunction | null>(null);

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [request, setRequest] = React.useState<ConfirmRequest | null>(null);
  const confirm = React.useCallback<ConfirmFunction>((message, options = {}) => new Promise(resolve => {
    setRequest(current => {
      current?.resolve(false);
      return { message, resolve, ...options };
    });
  }), []);
  const close = React.useCallback((confirmed: boolean) => {
    setRequest(current => {
      current?.resolve(confirmed);
      return null;
    });
  }, []);
  React.useEffect(() => {
    if (!request) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [request, close]);
  return <ConfirmContext.Provider value={confirm}>{children}{request && <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/50 p-4" onMouseDown={event => { if (event.target === event.currentTarget) close(false); }}>
    <div role="dialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-message" className="w-full max-w-md rounded-2xl border bg-card p-6 text-card-foreground shadow-2xl">
      <h2 id="confirm-title" className="text-lg font-semibold">{request.title || '确认操作'}</h2>
      <p id="confirm-message" className="mt-3 whitespace-pre-line text-sm leading-6 text-muted-foreground">{request.message}</p>
      <div className="mt-6 flex justify-end gap-2"><Button variant="outline" onClick={() => close(false)}>取消</Button><Button className={request.destructive ? 'bg-rose-600 hover:bg-rose-700' : ''} autoFocus onClick={() => close(true)}>{request.confirmLabel || '确认'}</Button></div>
    </div>
  </div>}</ConfirmContext.Provider>;
}

export function useConfirm(): ConfirmFunction {
  const confirm = React.useContext(ConfirmContext);
  if (!confirm) throw new Error('useConfirm must be used within ConfirmProvider');
  return confirm;
}

export function SearchField({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder: string }) {
  return <div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><Input className="bg-card pl-9" value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} /></div>;
}
export function Empty({ title, detail }: { title: string; detail?: string }) {
  return <div className="flex min-h-44 flex-col items-center justify-center rounded-xl border border-dashed bg-muted/40 px-6 text-center"><p className="font-medium">{title}</p>{detail && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{detail}</p>}</div>;
}
export function Busy() { return <div className="flex min-h-44 items-center justify-center gap-2 text-sm text-muted-foreground"><LoaderCircle className="h-4 w-4 animate-spin" />正在读取数据…</div>; }
export function Notice({ message, error, onClose }: { message: string; error: boolean; onClose: () => void }) {
  if (!message) return null;
  return <div role={error ? 'alert' : 'status'} className={`mb-5 flex items-start gap-2 rounded-lg border px-4 py-3 text-sm ${error ? 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-200' : 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200'}`}>{error ? <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />}<span className="flex-1">{message}</span><button onClick={onClose} className="text-xs underline">关闭</button></div>;
}
export function SectionTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: React.ReactNode }) {
  return <div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div>{eyebrow && <div className="mb-1 text-[11px] font-bold uppercase tracking-[0.16em] text-brand-600">{eyebrow}</div>}<h2 className="text-xl font-semibold tracking-tight">{title}</h2>{description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}</div>{action}</div>;
}
