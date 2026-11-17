import React from 'react';
import { Download, Plus, RotateCcw, ShieldCheck, Trash2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { api, botQuery, saveJsonFile } from '../api';
import { Busy, Empty, SearchField, SectionTitle, useConfirm } from '../ui';

export type CensorState = {
  scope: string;
  words: string[];
  count: number;
  fromFileCount: number;
  fromFileSample: string[];
  inheritedCount: number;
};

export type CensorFailure = { line: number; text: string; reason: string };

export type CensorReport = {
  total: number;
  success: number;
  failed: number;
  failures: CensorFailure[];
};

type Props = {
  token: string;
  bot: string;
  notify: (message: string, error?: boolean) => void;
};

const PAGE_SIZE = 200;

function toWordList(raw: unknown): string[] {
  if (Array.isArray(raw)) {
    return raw.filter(item => typeof item === 'string') as string[];
  }
  if (typeof raw === 'string') {
    return raw.split(/\r?\n/);
  }
  if (raw && typeof raw === 'object') {
    const list = (raw as { censorList?: unknown }).censorList;
    if (Array.isArray(list)) {
      return list.filter(item => typeof item === 'string') as string[];
    }
  }
  return [];
}

function pendingCount(text: string) {
  return text.split(/\r?\n/).filter(line => line.trim()).length;
}

export function CensorPage({ token, bot, notify }: Props) {
  const confirm = useConfirm();
  const [state, setState] = React.useState<CensorState | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const [draft, setDraft] = React.useState('');
  const [report, setReport] = React.useState<CensorReport | null>(null);
  const [editing, setEditing] = React.useState('');
  const [editDraft, setEditDraft] = React.useState('');
  const [page, setPage] = React.useState(1);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const result = await api<CensorState>(`/api/censor${botQuery(bot)}`, token);
      setState(result);
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      setLoading(false);
    }
  }, [bot, token, notify]);

  React.useEffect(() => {
    setEditing('');
    setPage(1);
    setReport(null);
    void load();
  }, [load]);

  const words = state?.words || [];
  const filtered = words.filter(word =>
    query ? word.toLowerCase().includes(query.toLowerCase()) : true,
  );
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const scopeHint =
    bot === 'unity'
      ? '全局词对所有账号生效，账号自己的词会叠加上去。'
      : '只改当前账号的自定义词，会和全局词一起生效。';

  const addWords = async () => {
    const lines = draft.split(/\r?\n/);
    if (!lines.some(line => line.trim())) {
      notify('请输入要添加的敏感词，每行一条', true);
      return;
    }
    setBusy(true);
    try {
      const result = await api<CensorState & { report: CensorReport }>('/api/censor', token, {
        bot,
        action: 'add',
        words: lines,
      });
      setState(result);
      setReport(result.report);
      if (result.report.success) setDraft('');
      notify(
        `共 ${result.report.total} 条，成功 ${result.report.success}，失败 ${result.report.failed}`,
        result.report.failed > 0 && result.report.success === 0,
      );
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      setBusy(false);
    }
  };

  const saveEdit = async () => {
    const value = editDraft.trim();
    if (!value || value === editing) {
      setEditing('');
      return;
    }
    setBusy(true);
    try {
      const result = await api<CensorState>('/api/censor', token, {
        bot,
        action: 'replace',
        word: editing,
        words: { value },
      });
      setState(result);
      setEditing('');
      notify('敏感词已修改');
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      setBusy(false);
    }
  };

  const deleteWord = async (word: string) => {
    const ok = await confirm(`确定删除敏感词「${word}」吗？`, {
      confirmLabel: '删除',
      destructive: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      const result = await api<CensorState>('/api/censor', token, {
        bot,
        action: 'delete',
        word,
      });
      setState(result);
      notify('敏感词已删除');
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      setBusy(false);
    }
  };

  const exportWords = async () => {
    try {
      const result = await api<{ words: string[] }>(`/api/censor/export${botQuery(bot)}`, token);
      saveJsonFile({ censorList: result.words }, `olivadice-censor-${bot}.json`);
    } catch (cause) {
      notify((cause as Error).message, true);
    }
  };

  const importWords = async (file?: File) => {
    if (!file) return;
    try {
      const text = await file.text();
      let parsed: unknown;
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = text;
      }
      const incoming = toWordList(parsed);
      if (!incoming.length) {
        notify('这个文件里没有读到敏感词', true);
        return;
      }
      const ok = await confirm(
        `将导入 ${incoming.length} 条，覆盖当前范围的自定义敏感词，继续吗？`,
        {
          confirmLabel: '导入',
        },
      );
      if (!ok) return;
      setBusy(true);
      const result = await api<CensorState>('/api/censor', token, {
        bot,
        action: 'import',
        words: incoming,
      });
      setState(result);
      notify(`已导入 ${incoming.length} 条敏感词`);
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const reloadFromDisk = async () => {
    const ok = await confirm('从磁盘重新加载敏感词？未保存的内存修改将被覆盖。', {
      confirmLabel: '重新加载',
    });
    if (!ok) return;
    setBusy(true);
    try {
      const result = await api<CensorState>('/api/censor', token, { bot, action: 'reload' });
      setState(result);
      notify('已从磁盘重新加载敏感词');
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      setBusy(false);
    }
  };

  const clearAll = async () => {
    const ok = await confirm('确定清空当前范围的全部自定义敏感词吗？', {
      confirmLabel: '清空',
      destructive: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      const result = await api<CensorState>('/api/censor', token, { bot, action: 'clear' });
      setState(result);
      setReport(null);
      notify('自定义敏感词已清空');
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <SectionTitle
        eyebrow="SENSITIVE WORDS"
        title="敏感词管理"
        description={scopeHint}
        action={
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => inputRef.current?.click()}
              disabled={busy}
            >
              <Upload className="mr-2 h-4 w-4" />
              导入
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void exportWords()}
              disabled={busy || !words.length}
            >
              <Download className="mr-2 h-4 w-4" />
              导出
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void reloadFromDisk()}
              disabled={busy}
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              从磁盘刷新
            </Button>
          </div>
        }
      />
      <input
        ref={inputRef}
        type="file"
        accept=".json,.txt,application/json,text/plain"
        className="hidden"
        onChange={event => void importWords(event.target.files?.[0])}
      />
      {loading ? (
        <Busy />
      ) : (
        <div
          className={'grid items-start gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)]'}
        >
          <div className="space-y-4">
            <Card className="border-brand-200 shadow-sm">
              <CardContent className="p-5 md:p-6">
                <div className="flex items-start gap-3">
                  <span
                    className={
                      'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl' +
                      ' bg-brand-50 text-brand-600'
                    }
                  >
                    <ShieldCheck className="h-5 w-5" />
                  </span>
                  <div>
                    <h2 className="text-lg font-semibold">添加敏感词</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-500">
                      每行一条，回车分隔。空行会跳过，重复和超长会在下面逐条说明。
                    </p>
                  </div>
                </div>
                <Textarea
                  className="mt-4 min-h-[220px] resize-y text-base leading-7"
                  placeholder={'敏感词一\n敏感词二\n敏感词三'}
                  value={draft}
                  onChange={event => setDraft(event.target.value)}
                />
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                  <span className="text-sm text-slate-500">待添加 {pendingCount(draft)} 条</span>
                  <Button onClick={() => void addWords()} disabled={busy || !draft.trim()}>
                    <Plus className="mr-2 h-4 w-4" />
                    添加这些词
                  </Button>
                </div>
              </CardContent>
            </Card>
            {report && (
              <Card className="border-slate-200 shadow-sm">
                <CardContent className="p-5">
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-xl bg-slate-50 px-3 py-3">
                      <div className="text-2xl font-semibold">{report.total}</div>
                      <div className="mt-1 text-xs text-slate-500">共提交</div>
                    </div>
                    <div className="rounded-xl bg-emerald-50 px-3 py-3">
                      <div className="text-2xl font-semibold text-emerald-700">
                        {report.success}
                      </div>
                      <div className="mt-1 text-xs text-emerald-700">成功</div>
                    </div>
                    <div className="rounded-xl bg-rose-50 px-3 py-3">
                      <div className="text-2xl font-semibold text-rose-700">{report.failed}</div>
                      <div className="mt-1 text-xs text-rose-700">失败</div>
                    </div>
                  </div>
                  {report.failures.length ? (
                    <ul className="mt-4 max-h-48 space-y-1.5 overflow-y-auto text-sm leading-6">
                      {report.failures.map(item => (
                        <li
                          key={`${item.line}-${item.text}-${item.reason}`}
                          className="rounded-lg bg-rose-50 px-3 py-1.5 text-rose-800"
                        >
                          第 {item.line} 行「{item.text}」：{item.reason}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-4 text-sm text-emerald-700">全部添加成功。</p>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
          <Card className="border-slate-200 shadow-sm">
            <div className="space-y-3 border-b p-4">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold">已添加</h2>
                <button
                  type="button"
                  className="text-xs text-slate-500 hover:text-rose-600 disabled:opacity-40"
                  onClick={() => void clearAll()}
                  disabled={busy || !words.length}
                >
                  清空
                </button>
              </div>
              <SearchField
                value={query}
                onChange={value => {
                  setQuery(value);
                  setPage(1);
                }}
                placeholder="搜索敏感词"
              />
              <p className="text-xs text-slate-500">
                自定义 {words.length} 条 · 词库文件 {state?.fromFileCount || 0} 条
              </p>
            </div>
            <div className="max-h-[520px] overflow-y-auto p-2">
              {pageItems.length ? (
                pageItems.map(word => (
                  <div
                    key={word}
                    className={
                      'mb-1 flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-50'
                    }
                  >
                    <span className="min-w-0 flex-1 truncate text-sm">{word}</span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setEditing(word);
                        setEditDraft(word);
                      }}
                      disabled={busy}
                    >
                      修改
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-rose-600 hover:text-rose-700"
                      onClick={() => void deleteWord(word)}
                      disabled={busy}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))
              ) : (
                <Empty title={words.length ? '没有匹配的敏感词' : '还没有自定义敏感词'} />
              )}
            </div>
            {filtered.length > PAGE_SIZE && (
              <div
                className={
                  'flex items-center justify-between border-t px-3 py-2 text-xs text-slate-500'
                }
              >
                <span>
                  {(currentPage - 1) * PAGE_SIZE + 1}–
                  {Math.min(currentPage * PAGE_SIZE, filtered.length)}
                </span>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={currentPage <= 1}
                    onClick={() => setPage(currentPage - 1)}
                  >
                    上一页
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={currentPage >= pageCount}
                    onClick={() => setPage(currentPage + 1)}
                  >
                    下一页
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </div>
      )}
      {editing && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/50 p-4">
          <div className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-2xl">
            <h2 className="text-lg font-semibold">修改敏感词</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">把「{editing}」改成下面的内容。</p>
            <Textarea
              className="mt-4 min-h-[120px]"
              value={editDraft}
              maxLength={64}
              autoFocus
              onChange={event => setEditDraft(event.target.value)}
            />
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setEditing('')} disabled={busy}>
                取消
              </Button>
              <Button onClick={() => void saveEdit()} disabled={busy || !editDraft.trim()}>
                保存
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
