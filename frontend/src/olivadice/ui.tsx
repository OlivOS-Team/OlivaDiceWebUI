import React from 'react';
import { AlertCircle, CheckCircle2, Check, ChevronDown, LoaderCircle, Search } from 'lucide-react';
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

export type SelectOption = { value: string; label: string; disabled?: boolean };

/**
 * A dropdown drawn by the page instead of the operating system.
 *
 * A native <select> renders its popup with the platform's own theme and colours, which
 * looks foreign inside this panel. This keeps the trigger and the option list in the
 * same visual language as the rest of the UI while still supporting keyboard use.
 */
export function Select({ value, options, onChange, ariaLabel, size = 'md', className = '', placeholder }: {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  ariaLabel?: string;
  size?: 'sm' | 'md';
  className?: string;
  placeholder?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [active, setActive] = React.useState(-1);
  const rootRef = React.useRef<HTMLDivElement>(null);
  const current = options.find(option => option.value === value);
  const height = size === 'sm' ? 'h-8 text-xs' : 'h-9 text-sm';

  React.useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  const commit = (next: string) => {
    setOpen(false);
    if (next !== value) onChange(next);
  };
  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') { setOpen(false); return; }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (!open) { setActive(options.findIndex(option => option.value === value)); setOpen(true); return; }
      const option = options[active];
      if (option && !option.disabled) commit(option.value);
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!open) { setActive(options.findIndex(option => option.value === value)); setOpen(true); return; }
      const step = event.key === 'ArrowDown' ? 1 : -1;
      let index = active;
      for (let hop = 0; hop < options.length; hop += 1) {
        index = (index + step + options.length) % options.length;
        if (!options[index]?.disabled) break;
      }
      setActive(index);
    }
  };

  return <div ref={rootRef} className={`relative ${className}`}>
    <button type="button" aria-haspopup="listbox" aria-expanded={open} aria-label={ariaLabel}
      onClick={() => { setActive(options.findIndex(option => option.value === value)); setOpen(current => !current); }}
      onKeyDown={onKeyDown}
      className={`flex w-full items-center justify-between gap-2 rounded-lg border bg-card px-3 ${height} text-left font-medium text-foreground outline-none transition-colors hover:bg-accent focus:ring-2 focus:ring-brand-300`}>
      <span className={`truncate ${current ? '' : 'text-muted-foreground'}`}>{current?.label ?? placeholder ?? ''}</span>
      <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
    </button>
    {open && <div role="listbox" aria-label={ariaLabel} className="absolute z-50 mt-1 max-h-64 w-full min-w-max overflow-y-auto rounded-lg border bg-popover p-1 text-popover-foreground shadow-lg">
      {options.map((option, index) => <div key={option.value} role="option" aria-selected={option.value === value}
        onMouseEnter={() => setActive(index)}
        onMouseDown={event => { event.preventDefault(); if (!option.disabled) commit(option.value); }}
        className={`flex cursor-pointer items-center justify-between gap-3 rounded-md px-3 py-2 text-sm ${option.disabled ? 'cursor-not-allowed opacity-50' : index === active ? 'bg-accent text-accent-foreground' : ''}`}>
        <span className="truncate">{option.label}</span>
        {option.value === value && <Check className="h-4 w-4 shrink-0 text-brand-600" />}
      </div>)}
    </div>}
  </div>;
}
