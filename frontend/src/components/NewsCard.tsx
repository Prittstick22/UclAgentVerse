import { useEffect, useId, useRef, useState } from "react";
import { safeUrl } from "../lib/investigation";
import type { NewsItem } from "../lib/types";
import "./news-card.css";

const dateLabel = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
const tickerLabel = (ticker: string) => ticker.split(".")[0];
type CoverTopic = "markets" | "bonds" | "energy" | "companies";

function coverTopic(headline: string): CoverTopic {
  if (/\b(gilts?|bonds?|treasur(?:y|ies)|yields?|interest rates?)\b/i.test(headline)) return "bonds";
  if (/\b(oil|crude|energy|opec|natural gas)\b/i.test(headline)) return "energy";
  if (/\b(chips?|semiconductors?|supplier|factory|earnings|company|companies)\b/i.test(headline)) return "companies";
  return "markets";
}

function CachedStory({ item, date, source, close }: { item: NewsItem; date: string; source: string; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const title = useId();
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} className="terminal-glass news-story-dialog" aria-labelledby={title} onClose={close}>
    <button className="mvp-action" type="button" onClick={() => dialog.current?.close()}>Close</button>
    <h2 id={title}>{item.headline}</h2>
    <p className="news-story-byline">Source: {source}{date && " · " + date}</p>
    <p>{item.summary || "No summary was saved for this story."}</p>
    {item.tickers.length > 0 && <p className="news-story-byline">Tagged investments · {item.tickers.map(tickerLabel).join(", ")}</p>}
  </dialog>;
}

function CoverArt({ topic }: { topic: CoverTopic }) {
  return <svg className="news-cover-art" viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <path d="M128 180 221 0h99v180z" fill="var(--news-wash)" />
    <path d="M113 180 206 0M155 180 248 0" stroke="currentColor" opacity=".19" />
    {topic === "markets" && <g transform="translate(202 89)" fill="none" stroke="currentColor" strokeWidth="1.45">
      <circle r="66" fill="var(--news-wash)" stroke="none" />
      <circle r="57" /><ellipse rx="26" ry="57" /><path d="M0-57v114M-57 0h114M-49-29Q0-7 49-29M-49 29Q0 7 49 29" />
      <ellipse rx="78" ry="17" transform="rotate(-22)" opacity=".65" />
      <circle cx="68" cy="-31" r="4" fill="currentColor" stroke="none" />
    </g>}
    {topic === "bonds" && <g transform="translate(198 87) rotate(-13)" stroke="currentColor" strokeWidth="1.5">
      <rect x="-47" y="-35" width="96" height="82" rx="5" fill="var(--news-wash)" opacity=".7" />
      <rect x="-40" y="-42" width="96" height="82" rx="5" fill="var(--news-bg)" />
      <rect x="-33" y="-49" width="96" height="82" rx="5" fill="var(--news-wash)" />
      <path d="M-20-29h50m-50 9h62m-62 9h52m-52 9h25m-25 10h25" fill="none" opacity=".7" />
      <circle cx="41" cy="10" r="13" fill="var(--news-bg)" /><path d="m36 10 3 3 7-7" fill="none" />
    </g>}
    {topic === "energy" && <g transform="translate(207 89)" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle r="63" opacity=".4" /><circle r="50" strokeDasharray="2 5" opacity=".65" />
      <path d="M0-42C-5-30-29-6-29 12a29 29 0 0 0 58 0C29-6 5-30 0-42Z" fill="var(--news-wash)" />
      <path d="M-18 12c0 9 6 15 13 16M-82 0h26m112 0h27" opacity=".72" />
    </g>}
    {topic === "companies" && <g transform="translate(207 90) rotate(-13)" fill="none" stroke="currentColor" strokeWidth="1.55">
      <rect x="-48" y="-48" width="96" height="96" rx="13" fill="var(--news-wash)" />
      <rect x="-35" y="-35" width="70" height="70" rx="6" />
      <path d="M-28-48v-13m14 13v-13m14 13v-13m14 13v-13m14 13v-13M-28 48v13m14-13v13m14-13v13m14-13v13m14-13v13M-48-28h-13m13 14h-13m13 14h-13m13 14h-13m13 14h-13M48-28h13m-13 14h13m-13 14h13m-13 14h13m-13 14h13" />
      <path d="M-22-20h18v18h-18zm25 0h18v18H3zm-25 25h18v16h-18zm25 0h18v16H3z" opacity=".65" />
    </g>}
  </svg>;
}

export default function NewsCard({ item, compact = false, held, tourTarget = false }: {
  item: NewsItem; compact?: boolean; held?: ReadonlySet<string>; tourTarget?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const url = safeUrl(item.url);
  const published = new Date(item.published_at);
  const date = Number.isFinite(published.getTime()) ? dateLabel.format(published) : "";
  const publisher = item.source.trim() || "Unavailable";
  const source = publisher + (item.synthetic && !/synthetic/i.test(publisher) ? " · Synthetic" : "");
  const tickers = item.tickers.slice(0, compact ? 1 : 2);
  const topic = coverTopic(item.headline);
  const content = <>
    <span className="news-cover" data-topic={topic} aria-hidden="true">
      <CoverArt topic={topic} />
      {tickers.length > 0 && <span className="news-cover-tickers" title={item.tickers.map(tickerLabel).join(", ")}>
        {tickers.map(ticker => <span key={ticker} data-held={held?.has(ticker.trim().toUpperCase()) || undefined}>{tickerLabel(ticker)}</span>)}
      </span>}
      <svg className="news-cover-link-mark" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round">
        <path d={url ? "M5 11 12 4m-5 0h5v5" : "M5 3.5h6a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1Zm1.5 3h3m-3 2.5h3"} />
      </svg>
    </span>
    <div className="news-card-copy">
      <h3 className="news-card-title" title={item.headline}>{item.headline}</h3>
      <div className="news-card-byline">
        <span>Source: {source}</span>
        {date && <time dateTime={item.published_at}>{date}</time>}
      </div>
      {!compact && item.summary && <p className="news-card-summary" title={item.summary}>{item.summary}</p>}
    </div>
  </>;

  return <li className="news-card-item" data-compact={compact || undefined}>
    {url ? <a className="news-card news-card-link glass-feedback" data-tour-target={tourTarget ? "news-story" : undefined} href={url} target="_blank" rel="noreferrer"
      aria-label={item.headline + " (opens in a new tab)"}>{content}</a> :
      <article className="news-card news-card-link glass-feedback" data-tour-target={tourTarget ? "news-story" : undefined}>{content}
        <button type="button" className="news-card-open" aria-label={"Read cached story: " + item.headline}
          onClick={() => setOpen(true)} />
      </article>}
    {open && <CachedStory item={item} date={date} source={source} close={() => setOpen(false)} />}
  </li>;
}
