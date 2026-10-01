import type { ReactNode } from "react";

/** Inline `**bold**` and `code`; everything else is plain text (React
 *  escapes it, so the change log can't inject markup). */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i} className="font-semibold text-ink">{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={i} className="bg-panel-2 px-1 text-[0.92em]">{part.slice(1, -1)}</code>;
    return part;
  });
}

const cells = (row: string) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
const isTableRow = (line: string) => /^\s*\|.*\|\s*$/.test(line);
const isDivider = (line: string) => /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(line);

interface Item {
  text: string;
  children: string[];
}

/** The subset of Markdown the change log (changes.md) uses: headings,
 *  bullet lists (one nesting level), tables, paragraphs, rules. */
export function MiniMarkdown({ source }: { source: string }) {
  const blocks: ReactNode[] = [];
  let list: Item[] = [];
  let table: string[] = [];
  const flushList = () => {
    if (!list.length) return;
    blocks.push(
      <ul key={`ul${blocks.length}`} className="my-2 flex list-disc flex-col gap-1.5 pl-5 text-sm leading-relaxed text-muted marker:text-pencil">
        {list.map((item, i) => (
          <li key={i} className="break-words">
            {inline(item.text)}
            {item.children.length > 0 && (
              <ul className="mt-1 flex list-[circle] flex-col gap-1 pl-5">
                {item.children.map((c, j) => <li key={j}>{inline(c)}</li>)}
              </ul>
            )}
          </li>
        ))}
      </ul>,
    );
    list = [];
  };
  const flushTable = () => {
    if (!table.length) return;
    const [head, ...rest] = table.filter((r) => !isDivider(r));
    blocks.push(
      <div key={`t${blocks.length}`} className="my-3 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-muted">
            <tr className="border-b border-line">{cells(head).map((c, i) => <th key={i} scope="col" className="py-2 pr-4 font-normal">{inline(c)}</th>)}</tr>
          </thead>
          <tbody>
            {rest.map((r, i) => (
              <tr key={i} className="border-b border-line">{cells(r).map((c, j) => <td key={j} className="py-2 pr-4 text-muted">{inline(c)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>,
    );
    table = [];
  };

  for (const raw of source.split("\n")) {
    const line = raw.trimEnd();
    if (isTableRow(line) || (table.length && isDivider(line))) {
      flushList();
      table.push(line);
      continue;
    }
    flushTable();
    const bullet = line.match(/^(\s*)[-*]\s+(.*)$/);
    if (bullet) {
      if (bullet[1].length >= 2 && list.length) list[list.length - 1].children.push(bullet[2]);
      else list.push({ text: bullet[2], children: [] });
      continue;
    }
    flushList();
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length;
      const cls = level === 1 ? "font-display text-[28px] mt-2" : level === 2 ? "font-display text-[22px] mt-6" : "text-sm font-semibold mt-4";
      blocks.push(<p key={blocks.length} role="heading" aria-level={level + 1} className={`m-0 ${cls}`}>{inline(heading[2])}</p>);
    } else if (/^-{3,}$/.test(line)) {
      blocks.push(<hr key={blocks.length} className="my-4 border-line" />);
    } else if (line.trim()) {
      blocks.push(<p key={blocks.length} className="my-1.5 break-words text-sm leading-relaxed text-muted">{inline(line)}</p>);
    }
  }
  flushList();
  flushTable();
  return <div className="flex flex-col">{blocks}</div>;
}
