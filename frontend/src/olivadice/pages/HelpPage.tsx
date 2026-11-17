import React from 'react';
import { BookOpenText, Download, Plus, RotateCcw, Save, Trash2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { api, botQuery, readJsonFile, saveJsonFile, type HelpDoc } from '../api';
import { Busy, Empty, SearchField, SectionTitle, useConfirm } from '../ui';

type Props = {
  token: string;
  bot: string;
  notify: (message: string, error?: boolean) => void;
  onDirtyChange: (dirty: boolean) => void;
  masterHash?: string;
  pageOnlyMaster?: boolean;
  returnAccountLabel?: string;
};
export function HelpPage({
  token,
  bot,
  notify,
  onDirtyChange,
  masterHash = '',
  pageOnlyMaster = false,
  returnAccountLabel = '',
}: Props) {
  const confirm = useConfirm();
  const [docs, setDocs] = React.useState<HelpDoc[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [query, setQuery] = React.useState('');
  const [statusFilter, setStatusFilter] = React.useState<'all' | 'modified' | 'unmodified'>('all');
  const [selected, setSelected] = React.useState('');
  const [newKey, setNewKey] = React.useState('');
  const [creating, setCreating] = React.useState(false);
  const [draft, setDraft] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const listRef = React.useRef<HTMLDivElement>(null);
  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const next = (await api<{ docs: HelpDoc[] }>(`/api/help${botQuery(bot)}`, token)).docs;
      setDocs(next);
      setSelected(current =>
        next.some(item => item.key === current) ? current : next[0]?.key || '',
      );
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      setLoading(false);
    }
  }, [bot, token, notify]);
  React.useEffect(() => {
    setSelected('');
    setCreating(false);
    setStatusFilter('all');
    void load();
  }, [load]);
  const active = docs.find(doc => doc.key === selected);
  React.useEffect(() => {
    if (!creating) setDraft(active?.value || '');
  }, [active?.key, active?.value, creating]);
  React.useEffect(() => {
    onDirtyChange(creating ? Boolean(newKey || draft) : Boolean(active && draft !== active.value));
    return () => onDirtyChange(false);
  }, [active, creating, newKey, draft, onDirtyChange]);
  const hasDraft = creating ? Boolean(newKey || draft) : Boolean(active && draft !== active.value);
  const filtered = docs.filter(
    doc =>
      (statusFilter === 'all' || doc.modified === (statusFilter === 'modified')) &&
      `${doc.key} ${doc.value}`.toLowerCase().includes(query.toLowerCase()),
  );
  const updateFilter = (nextQuery: string, nextStatusFilter: 'all' | 'modified' | 'unmodified') => {
    const next = docs.filter(
      doc =>
        (nextStatusFilter === 'all' || doc.modified === (nextStatusFilter === 'modified')) &&
        `${doc.key} ${doc.value}`.toLowerCase().includes(nextQuery.toLowerCase()),
    );
    if (!creating && !hasDraft && !next.some(doc => doc.key === selected))
      setSelected(next[0]?.key || '');
    setQuery(nextQuery);
    setStatusFilter(nextStatusFilter);
    if (listRef.current) listRef.current.scrollTop = 0;
  };
  const choose = async (key: string) => {
    if (
      (creating || draft !== active?.value) &&
      !(await confirm('当前词条尚未保存，确定放弃修改吗？', {
        confirmLabel: '放弃修改',
        destructive: true,
      }))
    )
      return;
    setCreating(false);
    setSelected(key);
  };
  const create = async () => {
    if (
      active &&
      draft !== active.value &&
      !(await confirm('当前词条尚未保存，确定放弃修改吗？', {
        confirmLabel: '放弃修改',
        destructive: true,
      }))
    )
      return;
    setSelected('');
    setNewKey('');
    setDraft('');
    setCreating(true);
  };
  const save = async () => {
    const key = creating ? newKey.trim() : active?.key;
    if (!key) {
      notify('请输入词条名称', true);
      return;
    }
    if (creating && docs.some(doc => doc.key === key)) {
      notify('词条已存在，请在列表中编辑', true);
      return;
    }
    setBusy(true);
    try {
      await api('/api/help', token, { bot, key, value: draft });
      await load();
      setCreating(false);
      setSelected(key);
      notify('帮助词条已保存');
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (
      !active?.custom ||
      !(await confirm(`确定删除自定义词条「${active.key}」吗？`, {
        confirmLabel: '删除',
        destructive: true,
      }))
    )
      return;
    setBusy(true);
    try {
      await api('/api/help', token, { bot, key: active.key, action: 'delete' });
      setSelected('');
      await load();
      notify('词条已删除');
    } catch (cause) {
      notify((cause as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  const exportJson = async () => {
    try {
      const result = await api<{ docs: Record<string, string> }>(
        `/api/help/export${botQuery(bot)}`,
        token,
      );
      saveJsonFile({ helpdoc: result.docs }, `olivadice-help-${bot}.json`);
    } catch (cause) {
      notify((cause as Error).message, true);
    }
  };
  const importJson = async (file?: File) => {
    if (!file) return;
    try {
      const data = await readJsonFile(file);
      const incoming =
        data.helpdoc && typeof data.helpdoc === 'object' && !Array.isArray(data.helpdoc)
          ? (data.helpdoc as Record<string, unknown>)
          : data;
      if (
        await confirm(
          `将导入 ${Object.keys(incoming).length} 条帮助词条到当前账号；文件中的同名词条会覆盖当前自定义值，继续吗？`,
          { confirmLabel: '导入' },
        )
      ) {
        setBusy(true);
        try {
          await api('/api/help/manage', token, { bot, action: 'import', data });
          await load();
          notify('帮助词条已导入当前账号');
        } catch (cause) {
          notify((cause as Error).message, true);
        } finally {
          setBusy(false);
        }
      }
    } catch (cause) {
      notify((cause as Error).message, true);
    }
    if (inputRef.current) inputRef.current.value = '';
  };
  return (
    <>
      <SectionTitle
        eyebrow="HELP LIBRARY"
        title="词条列表"
        description="维护 .help 可查询的词条；内置词条可覆盖，自定义词条可删除。导入导出只作用于当前账号。"
        action={
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => void load()}>
              <RotateCcw className="mr-2 h-4 w-4" />
              刷新
            </Button>
            <Button size="sm" onClick={() => void create()}>
              <Plus className="mr-2 h-4 w-4" />
              新增词条
            </Button>
          </div>
        }
      />
      {pageOnlyMaster && (
        <div
          className={
            `mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm ` +
            `leading-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 ` +
            `dark:text-amber-100`
          }
        >
          当前主账号未启用，仅本页可见。离开后返回【{returnAccountLabel || '对应账号'}】。
        </div>
      )}
      {!pageOnlyMaster && masterHash && (
        <div
          className={
            `mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm ` +
            `leading-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 ` +
            `dark:text-amber-100`
          }
        >
          本页面遵循主从连接，若不设定在全局内，从账号读取主账号的帮助文档，但仍可独立设定以便于断开主从连接后使用。当前账号为从账号，若要修改当前生效内容，请改主账号。
        </div>
      )}
      <div className="mb-5 flex flex-wrap gap-2">
        <input
          ref={inputRef}
          type="file"
          accept=".json,application/json"
          className="hidden"
          onChange={event => void importJson(event.target.files?.[0])}
        />
        <Button
          size="sm"
          variant="outline"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
        >
          <Upload className="mr-2 h-4 w-4" />
          导入词条
        </Button>
        <Button size="sm" variant="outline" onClick={() => void exportJson()} disabled={busy}>
          <Download className="mr-2 h-4 w-4" />
          导出词条
        </Button>
      </div>
      {loading ? (
        <Busy />
      ) : (
        <div className="grid min-h-[600px] gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
          <Card className="overflow-hidden border-slate-200 shadow-sm">
            <div className="space-y-3 border-b p-4">
              <SearchField
                value={query}
                onChange={value => updateFilter(value, statusFilter)}
                placeholder="搜索词条或内容"
              />
              <div
                className={
                  'flex flex-wrap items-center justify-between gap-2 text-xs ' + 'text-slate-500'
                }
              >
                <span>
                  {filtered.length} / {docs.length} 条词条
                </span>
                <div className="flex flex-wrap gap-3">
                  <label className="flex cursor-pointer items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={statusFilter === 'modified'}
                      onChange={event =>
                        updateFilter(query, event.target.checked ? 'modified' : 'all')
                      }
                    />
                    仅看已修改
                  </label>
                  <label className="flex cursor-pointer items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={statusFilter === 'unmodified'}
                      onChange={event =>
                        updateFilter(query, event.target.checked ? 'unmodified' : 'all')
                      }
                    />
                    仅看未修改
                  </label>
                </div>
              </div>
            </div>
            <div ref={listRef} className="max-h-[620px] overflow-y-auto p-2">
              {filtered.length ? (
                filtered.slice(0, 200).map(doc => (
                  <button
                    key={doc.key}
                    onClick={() => void choose(doc.key)}
                    className={
                      `mb-1 flex w-full items-center justify-between gap-2 rounded-lg px-3 ` +
                      `py-2.5 text-left text-sm` +
                      `${
                        selected === doc.key && !creating
                          ? 'bg-brand-50 font-medium text-brand-800 ring-1 ring-brand-200'
                          : 'hover:bg-slate-50'
                      }`
                    }
                  >
                    <span className="truncate">{doc.key}</span>
                    {doc.modified && (
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                    )}
                  </button>
                ))
              ) : (
                <Empty title="没有匹配的词条" />
              )}
              {filtered.length > 200 && (
                <div className="p-3 text-center text-xs text-slate-500">
                  只显示前 200 条，请输入关键词缩小范围
                </div>
              )}
            </div>
          </Card>
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="p-5 md:p-7">
              {creating || active ? (
                <>
                  <div className="flex items-center gap-2 text-xs font-medium text-brand-600">
                    <BookOpenText className="h-4 w-4" />
                    {creating ? '新建词条' : active?.default === null ? '自定义词条' : '内置词条'}
                  </div>
                  {creating ? (
                    <div className="mt-5">
                      <label htmlFor="help-key" className="mb-2 block text-sm font-medium">
                        词条名称
                      </label>
                      <Input
                        id="help-key"
                        maxLength={100}
                        value={newKey}
                        onChange={event => setNewKey(event.target.value)}
                        placeholder="例如：跑团规则"
                      />
                    </div>
                  ) : (
                    <h3 className="mt-3 break-all text-xl font-semibold">{active?.key}</h3>
                  )}
                  <div className="mt-6">
                    <label htmlFor="help-content" className="mb-2 block text-sm font-medium">
                      帮助内容
                    </label>
                    <Textarea
                      id="help-content"
                      className="min-h-[350px] resize-y bg-white text-sm leading-6"
                      value={draft}
                      maxLength={20000}
                      onChange={event => setDraft(event.target.value)}
                    />
                  </div>
                  <div className="mt-4 flex flex-wrap justify-between gap-2">
                    <div>
                      {active?.custom && !creating && (
                        <Button
                          variant="outline"
                          className="text-rose-600 hover:text-rose-700"
                          onClick={() => void remove()}
                          disabled={busy}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          删除
                        </Button>
                      )}
                    </div>
                    <Button
                      onClick={() => void save()}
                      disabled={busy || (!creating && draft === active?.value)}
                    >
                      <Save className="mr-2 h-4 w-4" />
                      保存词条
                    </Button>
                  </div>
                </>
              ) : (
                <Empty title="选择或新增帮助词条" />
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
