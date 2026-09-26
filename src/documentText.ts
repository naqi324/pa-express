// Splits a clinical document into plain and marked runs so verbatim evidence
// quotes render as <mark> in place. Quotes that are not found verbatim, or
// that overlap an earlier quote, are left unmarked.

export interface TextPart {
  text: string;
  mark: boolean;
}

interface QuoteRange {
  start: number;
  end: number;
}

export function markedParts(text: string, quotes: string[]): TextPart[] {
  const ranges: QuoteRange[] = [];

  for (const quote of quotes) {
    const start = quote ? text.indexOf(quote) : -1;

    if (start >= 0) ranges.push({ start, end: start + quote.length });
  }

  const parts: TextPart[] = [];
  let cursor = 0;

  for (const range of ranges.toSorted((left, right) => left.start - right.start)) {
    if (range.start < cursor) continue;

    if (range.start > cursor) parts.push({ text: text.slice(cursor, range.start), mark: false });

    parts.push({ text: text.slice(range.start, range.end), mark: true });
    cursor = range.end;
  }

  if (cursor < text.length) parts.push({ text: text.slice(cursor), mark: false });

  return parts;
}

export function docTypeLabel(docType: string): string {
  const words = docType.replaceAll('_', ' ');

  return words.charAt(0).toUpperCase() + words.slice(1);
}
