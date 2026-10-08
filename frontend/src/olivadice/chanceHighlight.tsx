import React from 'react';
import { SyntaxEditor } from './syntaxEditor';

/**
 * ChanceCustom reply highlighter.
 *
 * Tokens follow ChanceCustom's own scanner: nested 【】 blocks, >=< argument
 * separators, top-level * reply splits, escape codes, and CQ/OP codes.
 * Nesting depth only changes the colour of brackets and function names.
 */

export type TokenKind = 'text' | 'bracket' | 'func' | 'sep' | 'split' | 'escape' | 'code' | 'open';
export type Token = { k: TokenKind; v: string; d: number };

const ESCAPES = ['#zzk', '#yzk', '#fgf', '#xh', '#hz', '#jh'];

// Names from ChanceCustom.replyReg / replyFilter, longest match first.
const FUNCS = [
  'Json写-插列表-自动', 'Json写-插列表-文本', '写Json-插列表-自动', '写Json-插列表-文本',
  'Json删-过滤列表', '删Json-过滤列表', 'Json写-插列表', '写Json-插列表',
  '文本-中间替换', '文本-取出中间', '文本-倒取中间', '文本-取出左边', '文本-取出右边',
  '文本-取出长度', '文本-寻找文本', '文本-倒找文本', '文本-反转文本', '文本-替换文本',
  '文本-转为大写', '文本-转为小写', '文本-取文本左', '文本-取文本右', '文本-删首尾空',
  '行操作-删空白行', '行操作-删重复行', '行操作-删首尾空', '行操作-删指定行',
  '行操作-替换指定', '行操作-插入文本', '行操作-按字拆行', '行操作-每行相连',
  '行操作-每行排序', '行操作-每行反转', '行操作-前后反转', '行操作-按行分页',
  '行操作-取出指定', '行操作-添加文本', '行操作-替换文本',
  '人物卡-读技能', '人物卡-写技能', '人物卡-切换', '人物卡-锁定', '人物卡-解锁',
  '人物卡-名称', 'DICE-指令注册', 'DICE-前缀注册', '时间戳转文本',
  '赋值局部常量', '更新局部常量', 'Json写-自动', 'Json写-文本', '写Json-自动', '写Json-文本',
  '发送者专属头衔', '发送者名片', '发送者昵称', '发送者QQ', '发送者ID',
  '当前群人数', '当前群上限', '当前频道号', '当前群号', '当前群名',
  '机器人名字', '机器人QQ', '机器人ID', '补位随机数', '随机字符', '随机排序',
  '分割排序', '分割取出', '范围取整', '正则重构', '访问-UTF', '访问-GBK',
  '13位时间', '10位时间', '现行日期', '现行时间', '时间间隔', '局部常量',
  '更新变量', '赋值变量', '更新常量', '赋值常量', '函数全局',
  'Json读', 'Json写', 'Json删', 'Json取', '读Json', '写Json', '删Json', '取Json',
  '读配置', '写配置', '取配置', '取配节', '读入', '写出',
  '一天上限', '一周上限', '一月上限', '一次间隔', '回复间隔',
  '今日人品', '昨日人品', '明日人品', '人物卡名', '读人物卡', '写人物卡',
  '切人物卡', '锁定人物卡', '解锁人物卡', '随机数', '运行目录', '应用目录',
  '输入流', '输出流', '反转义', '换行', '间隔', '内容', '艾特', '权限', '转义',
  '延时', '延迟', '变量', '常量', '随取', '访问', '循环', 'Fori', '跳出', '继续',
  '分页', '判空', '判断', '比较', '判含', '判真', '禁言', '牌堆', 'RD', '计算',
  '排序', '统计', '取MD5', '进制', '补位', '隐藏', '取整', '取中间', '正则',
  '子正则', '删除', '选择', '替换', '逻辑', '函数', '主人', '群管', '管理',
].sort((a, b) => b.length - a.length || a.localeCompare(b));

function emit(tokens: Token[], k: TokenKind, v: string, d: number) {
  if (!v) return;
  const last = tokens[tokens.length - 1];
  if (last && last.k === k && last.d === d && k === 'text') last.v += v;
  else tokens.push({ k, v, d });
}

function matchingEnd(src: string, from: number, end: number): number {
  let depth = 0;
  for (let index = from; index < end; index += 1) {
    if (src[index] === '【') depth += 1;
    else if (src[index] === '】') {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  return -1;
}

function matchFunc(src: string, from: number, bound: number): string {
  for (const name of FUNCS) {
    if (from + name.length <= bound && src.startsWith(name, from)) return name;
  }
  return '';
}

function takeEscape(src: string, i: number): string {
  for (const code of ESCAPES) {
    if (src.startsWith(code, i)) return code;
  }
  return '';
}

function codeEnd(src: string, i: number, end: number): number {
  if (!src.startsWith('[CQ:', i) && !src.startsWith('[OP:', i)) return -1;
  const close = src.indexOf(']', i + 4);
  return close === -1 ? end : Math.min(close + 1, end);
}

function parsePlain(src: string, tokens: Token[], from: number, end: number, depth: number, inFunc: boolean): number {
  let i = from;
  while (i < end) {
    const escape = takeEscape(src, i);
    if (escape) {
      emit(tokens, 'escape', escape, depth);
      i += escape.length;
      continue;
    }
    const cq = codeEnd(src, i, end);
    if (cq !== -1) {
      emit(tokens, 'code', src.slice(i, cq), depth);
      i = cq;
      continue;
    }
    if (!inFunc && src[i] === '*') {
      emit(tokens, 'split', '*', depth);
      i += 1;
      continue;
    }
    if (src[i] === '【') {
      i = parseFunc(src, tokens, i, end, depth);
      continue;
    }
    if (inFunc && src.startsWith('>=<', i)) {
      emit(tokens, 'sep', '>=<', depth);
      i += 3;
      continue;
    }
    emit(tokens, 'text', src[i], depth);
    i += 1;
  }
  return i;
}

function parseFunc(src: string, tokens: Token[], from: number, end: number, depth: number): number {
  const close = matchingEnd(src, from, end);
  emit(tokens, close === -1 ? 'open' : 'bracket', '【', depth);
  let i = from + 1;
  const bound = close === -1 ? end : close;
  const name = matchFunc(src, i, bound);
  if (name) {
    emit(tokens, 'func', name, depth);
    i += name.length;
  } else {
    const begin = i;
    while (i < bound && src[i] !== '【' && src[i] !== '】' && !src.startsWith('>=<', i)) i += 1;
    if (i > begin) emit(tokens, 'func', src.slice(begin, i), depth);
  }
  i = parsePlain(src, tokens, i, bound, depth + 1, true);
  if (close !== -1) {
    emit(tokens, 'bracket', '】', depth);
    return close + 1;
  }
  return i;
}

export function tokenize(src: string): Token[] {
  const tokens: Token[] = [];
  parsePlain(src, tokens, 0, src.length, 0, false);
  return tokens;
}

type EditorProps = {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  maxLength?: number;
  id?: string;
  disabled?: boolean;
  placeholder?: string;
};

export function ChanceEditor({ value, onChange, className, maxLength, id, disabled, placeholder }: EditorProps) {
  const tokens = React.useMemo(
    () => tokenize(value).map(token => ({
      className: `cc-token cc-${token.k} cc-d${token.d % 4}`,
      v: token.v,
    })),
    [value],
  );
  return (
    <SyntaxEditor
      value={value}
      onChange={onChange}
      tokens={tokens}
      highlightClass="chance-highlight"
      className={className}
      maxLength={maxLength}
      id={id}
      disabled={disabled}
      placeholder={placeholder}
    />
  );
}
