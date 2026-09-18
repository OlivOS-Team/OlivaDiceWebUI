import React from 'react';
import { AlertCircle, CheckCircle2, LoaderCircle, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';

export function SearchField({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder: string }) {
  return <div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input className="bg-white pl-9" value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} /></div>;
}
export function Empty({ title, detail }: { title: string; detail?: string }) {
  return <div className="flex min-h-44 flex-col items-center justify-center rounded-xl border border-dashed bg-slate-50/60 px-6 text-center"><p className="font-medium text-slate-700">{title}</p>{detail && <p className="mt-1 max-w-sm text-sm text-slate-500">{detail}</p>}</div>;
}
export function Busy() { return <div className="flex min-h-44 items-center justify-center gap-2 text-sm text-slate-500"><LoaderCircle className="h-4 w-4 animate-spin" />正在读取数据…</div>; }
export function Notice({ message, error, onClose }: { message: string; error: boolean; onClose: () => void }) {
  if (!message) return null;
  return <div role={error ? 'alert' : 'status'} className={`mb-5 flex items-start gap-2 rounded-lg border px-4 py-3 text-sm ${error ? 'border-rose-200 bg-rose-50 text-rose-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}>{error ? <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />}<span className="flex-1">{message}</span><button onClick={onClose} className="text-xs underline">关闭</button></div>;
}
export function SectionTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: React.ReactNode }) {
  return <div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div>{eyebrow && <div className="mb-1 text-[11px] font-bold uppercase tracking-[0.16em] text-brand-600">{eyebrow}</div>}<h2 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h2>{description && <p className="mt-1 text-sm text-slate-500">{description}</p>}</div>{action}</div>;
}
