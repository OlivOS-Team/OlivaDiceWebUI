import React from 'react';
import { SyntaxEditor } from './syntaxEditor';

/**
 * OlivaDice reply highlighter.
 *
 * Braces nest by matching `{` / `}` (so `{{}` is an unmatched outer `{` plus
 * an inner pair). A leaf `{key}` is classified as a template var, {DEVIDE}/
 * {OR}, escape, or deck name. `|` is a random-reply split.
 */

export type ReplyTokenKind = 'text' | 'brace' | 'var' | 'special' | 'escape' | 'deck' | 'split' | 'open';
export type ReplyToken = { k: ReplyTokenKind; v: string; d: number };

const SPECIALS = new Set(['DEVIDE', 'OR']);
const T_VAR = /^t[A-Za-z][A-Za-z0-9_]*$/;
const ESCAPE = /^\\[nrtfbav]$/;

function emit(tokens: ReplyToken[], k: ReplyTokenKind, v: string, d: number) {
  if (!v) return;
  const last = tokens[tokens.length - 1];
  if (last && last.k === k && last.d === d && (k === 'text' || k === 'open')) last.v += v;
  else tokens.push({ k, v, d });
}

function keyKind(key: string): ReplyTokenKind {
  if (SPECIALS.has(key)) return 'special';
  if (ESCAPE.test(key)) return 'escape';
  if (T_VAR.test(key)) return 'var';
  return 'deck';
}

function matchingBrace(src: string, from: number, end: number): number {
  let depth = 0;
  for (let index = from; index < end; index += 1) {
    if (src[index] === '{') depth += 1;
    else if (src[index] === '}') {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  return -1;
}

function parseReply(src: string, tokens: ReplyToken[], from: number, end: number, depth: number) {
  let i = from;
  while (i < end) {
    if (src[i] === '{') {
      const close = matchingBrace(src, i, end);
      const bound = close === -1 ? end : close;
      const inner = src.slice(i + 1, bound);
      emit(tokens, close === -1 ? 'open' : 'brace', '{', depth);
      if (inner.includes('{')) parseReply(src, tokens, i + 1, bound, depth + 1);
      else if (close === -1) emit(tokens, 'open', inner, depth);
      else emit(tokens, keyKind(inner), inner, depth);
      if (close !== -1) emit(tokens, 'brace', '}', depth);
      i = close === -1 ? end : close + 1;
      continue;
    }
    if (src[i] === '|') {
      emit(tokens, 'split', '|', depth);
      i += 1;
      continue;
    }
    emit(tokens, 'text', src[i], depth);
    i += 1;
  }
}

export function tokenizeReply(src: string): ReplyToken[] {
  const tokens: ReplyToken[] = [];
  parseReply(src, tokens, 0, src.length, 0);
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

export function ReplyEditor({ value, onChange, className, maxLength, id, disabled, placeholder }: EditorProps) {
  const tokens = React.useMemo(
    () => tokenizeReply(value).map(token => ({
      className: `rv-token rv-${token.k} rv-d${token.d % 4}`,
      v: token.v,
    })),
    [value],
  );
  return (
    <SyntaxEditor
      value={value}
      onChange={onChange}
      tokens={tokens}
      highlightClass="reply-highlight"
      wrapperClassName="relative"
      className={className}
      maxLength={maxLength}
      id={id}
      disabled={disabled}
      placeholder={placeholder}
    />
  );
}
