import React from 'react';
import { Download, ListFilter, Plus, RotateCcw, ShieldCheck, Trash2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { api, botQuery, saveJsonFile } from '../api';
import { Busy, Empty, SearchField, SectionTitle, useConfirm } from '../ui';

/** 敏感词管理页的数据结构，与后端 service.censors 一一对应。 */
export type CensorState = {
  scope: string;
  words: string[];
  count: number;
  fromFileCount: number;
  fromFileSample: string[];
  inheritedCount: number;
};

type Props = {
  token: string;
  bot: string;
  notify: (message: string, error?: boolean) => void;
};

const PAGE_SIZE = 200;

/** 把导入内容统一成词条数组：支持数组、换行文本，以及 { censorList: [...] } 形态。 */
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

export function CensorPage({ token, bot, notify }: Props) {
  const confirm = useConfirm();
  const [state, setState] = React.useState<CensorState | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const [selected, setSelected] = React.useState('');
  const [newWord, setNewWord] = React.useState('');
  const [editing, setEditing] = React.useState('');
  const [editDraft, setEditDraft] = React.useState('');
  const [page, setPage] = React.useState(1);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const result = await api<CensorState>(`/api/censor${botQuery(bot)}`, token);
      setState(result);
      setSelected(current => (result.words.includes(current) ? current : ''));
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      setLoading(false);
    }
  }, [bot, token, notify]);

  React.useEffect(() => {
    setSelected('');
    setEditing('');
    setPage(1);
    void load();
  }, [load]);

  /** 统一提交入口：增删改都走这里，改完立刻回读，不需要手动刷新。 */
  const send = async (payload: Record<string, unknown>, message: string) => {
    setBusy(true);
    try {
      const result = await api<CensorState>('/api/censor', token, { bot, ...payload });
      setState(result);
      notify(message);
      return result;
    } catch (cause) {
      notify((cause as Error).message, true);
      return null;
    } finally {
      setBusy(false);
    }
  };

  const words = state?.words || [];
  const filtered = words.filter(word =>
    query ? word.toLowerCase().includes(query.toLowerCase()) : true,
  );
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const addWord = async () => {
    const value = newWord.trim();
    if (!value) {
      notify('请输入要添加的敏感词', true);
      return;
    }
    if (words.includes(value)) {
      notify('这个敏感词已经在列表里了', true);
      return;
    }
    if (await send({ action: 'add', word: value }, '敏感词已添加')) {
      setNewWord('');
    }
  };

  const deleteWord = async (word: string) => {
    const ok = await confirm(`确定删除敏感词「${word}」吗？`, {
      confirmLabel: '删除',
      destructive: true,
    });
    if (!ok) return;
    const result = await send({ action: 'delete', word }, '敏感词已删除');
    if (result && selected === word) setSelected('');
  };

  const beginEdit = (word: string) => {
    setSelected(word);
    setEditing(word);
    setEditDraft(word);
  };

  const saveEdit = async () => {
    const value = editDraft.trim();
    if (!value) {
      notify('敏感词不能为空', true);
      return;
    }
    if (value === editing) {
      setEditing('');
      return;
    }
    if (words.includes(value)) {
      notify('这个敏感词已经在列表里了', true);
      return;
    }
    const result = await send(
      { action: 'replace', word: editing, words: { value } },
      '敏感词已修改',
    );
    if (result) {
      setEditing('');
      setSelected(value);
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
        `将导入 ${incoming.length} 条敏感词，覆盖当前账号的敏感词表，继续吗？`,
        { confirmLabel: '导入' },
      );
      if (ok)
        await send({ action: 'import', words: incoming }, `已导入 ${incoming.length} 条敏感词`);
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const reloadFromDisk = async () => {
    const ok = await confirm('从磁盘重新加载敏感词？未保存的内存修改将被覆盖。', {
      confirmLabel: '重新加载',
    });
    if (!ok) return;
    await send({ action: 'reload' }, '已从磁盘重新加载敏感词');
  };

  const clearAll = async () => {
    const ok = await confirm('确定清空当前账号的全部自定义敏感词吗？清空后只能靠词库文件拦截。', {
      confirmLabel: '清空',
      destructive: true,
    });
    if (!ok) return;
    await send({ action: 'clear' }, '自定义敏感词已清空');
    setSelected('');
    setEditing('');
  };

  const scopeHint =
    bot === 'unity'
      ? '全局敏感词对所有账号生效，账号自己的词表会叠加在全局之上。'
      : '当前账号的敏感词会与全局词表叠加生效。';

  const itemClass = (word: string) => {
    const active = selected === word && !editing;
    return [
      'mb-1 block w-full truncate rounded-lg px-3 py-2.5 text-left text-sm transition-colors',
      active ? 'bg-brand-50 font-medium text-brand-800 ring-1 ring-brand-200' : 'hover:bg-slate-50',
    ].join(' ');
  };

  const detail = (() => {
    if (editing) {
      return (
        <>
          <div className="flex items-center gap-2 text-xs font-medium text-brand-600">
            <ShieldCheck className="h-4 w-4" />
            修改敏感词
          </div>
          <div className="mt-5">
            <label htmlFor="censor-edit" className="mb-2 block text-sm font-medium">
              敏感词
            </label>
            <Input
              id="censor-edit"
              value={editDraft}
              maxLength={64}
              autoFocus
              onChange={event => setEditDraft(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter') void saveEdit();
              }}
            />
            <p className="mt-2 text-xs leading-5 text-slate-500">
              原来的词「{editing}」会被替换成这个，位置保持不变。
            </p>
          </div>
          <div className="mt-4 flex gap-2">
            <Button variant="outline" onClick={() => setEditing('')} disabled={busy}>
              取消
            </Button>
            <Button onClick={() => void saveEdit()} disabled={busy || editDraft.trim() === editing}>
              保存修改
            </Button>
          </div>
        </>
      );
    }
    if (selected) {
      return (
        <>
          <div className="flex items-center gap-2 text-xs font-medium text-brand-600">
            <ShieldCheck className="h-4 w-4" />
            敏感词
          </div>
          <h3 className="mt-3 break-all text-xl font-semibold">{selected}</h3>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            命中这个词的消息会被替换成屏蔽标记。
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => beginEdit(selected)} disabled={busy}>
              修改
            </Button>
            <Button
              variant="outline"
              className="text-rose-600 hover:text-rose-700"
              onClick={() => void deleteWord(selected)}
              disabled={busy}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              删除
            </Button>
          </div>
        </>
      );
    }
    return <Empty title="选择左侧敏感词，或直接添加一个" detail="改完立刻生效，不需要刷新。" />;
  })();

  return (
    <>
      <SectionTitle
        eyebrow="SENSITIVE WORDS"
        title="敏感词管理"
        description={scopeHint}
        action={
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => void reloadFromDisk()}
              disabled={busy}
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              从磁盘刷新
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void clearAll()}
              disabled={busy || !words.length}
            >
              清空
            </Button>
          </div>
        }
      />
      <div className="mb-5 flex flex-wrap gap-2">
        <input
          ref={inputRef}
          type="file"
          accept=".json,.txt,application/json,text/plain"
          className="hidden"
          onChange={event => void importWords(event.target.files?.[0])}
        />
        <Button
          size="sm"
          variant="outline"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
        >
          <Upload className="mr-2 h-4 w-4" />
          导入敏感词
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void exportWords()}
          disabled={busy || !words.length}
        >
          <Download className="mr-2 h-4 w-4" />
          导出敏感词
        </Button>
        <div className="flex flex-1 gap-2 sm:justify-end">
          <Input
            className="max-w-xs"
            placeholder="输入敏感词后回车添加"
            value={newWord}
            maxLength={64}
            onChange={event => setNewWord(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter') void addWord();
            }}
          />
          <Button size="sm" onClick={() => void addWord()} disabled={busy || !newWord.trim()}>
            <Plus className="mr-2 h-4 w-4" />
            添加
          </Button>
        </div>
      </div>
      {loading ? (
        <Busy />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
          <Card className="flex min-h-0 flex-col overflow-hidden border-slate-200 shadow-sm">
            <div className="space-y-3 border-b p-4">
              <SearchField
                value={query}
                onChange={value => {
                  setQuery(value);
                  setPage(1);
                }}
                placeholder="搜索敏感词"
              />
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                <span>
                  {filtered.length} / {words.length} 条自定义词
                </span>
                <span className="inline-flex items-center gap-1">
                  <ListFilter className="h-3.5 w-3.5" />
                  词库文件 {state?.fromFileCount || 0} 条
                </span>
              </div>
            </div>
            <div className="max-h-[560px] flex-1 overflow-y-auto p-2">
              {pageItems.length ? (
                pageItems.map(word => (
                  <button
                    key={word}
                    onClick={() => {
                      setEditing('');
                      setSelected(word);
                    }}
                    className={itemClass(word)}
                  >
                    {word}
                  </button>
                ))
              ) : (
                <Empty title={words.length ? '没有匹配的敏感词' : '当前还没有自定义敏感词'} />
              )}
            </div>
            {filtered.length > PAGE_SIZE && (
              <div className="flex items-center justify-between border-t px-3 py-2 text-xs text-slate-500">
                <span>
                  {(currentPage - 1) * PAGE_SIZE + 1}–
                  {Math.min(currentPage * PAGE_SIZE, filtered.length)} / {filtered.length}
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
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="p-5 md:p-7">{detail}</CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
