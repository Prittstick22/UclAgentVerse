function LeadGlyph({ brand = false }: { brand?: boolean }) {
  return <>
    <path d="M8 28c0-5 2.6-8.9 6-10.6v-3.1a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2V16h1V11a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v5h1V8a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v11c2 2 3 5.1 3 9v2c0 7-4 11-11 11H19c-7 0-11-4-11-11Z" fill={brand ? "#ebedf2" : "#1e162a"} />
    <rect x="16" y="24" width="5" height="9" rx="2.5" fill={brand ? "#26292e" : "#faf4ff"} />
    <rect x="27" y="24" width="5" height="9" rx="2.5" fill={brand ? "#26292e" : "#faf4ff"} />
    {brand && <path d="M30 8a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3h-7Z" fill="#8fd8ad" />}
  </>;
}

export function BrandMark() {
  return <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false"><LeadGlyph brand /></svg>;
}

const portraits = {
  lead: <LeadGlyph />,
  bond_scout: <>
    <path d="M10 22 24 11l14 11-3 13H13Z" fill="#203431" />
    <rect x="15" y="22" width="18" height="14" rx="5" fill="#edf3e7" />
    <circle cx="20" cy="28" r="2" fill="#203431" /><circle cx="28" cy="28" r="2" fill="#203431" />
    <path d="M21 32h6" stroke="#203431" strokeWidth="1.5" strokeLinecap="round" />
  </>,
  stock_analyst: <>
    <path d="M11 26V13l10 5h6l10-5v13c0 9-6 13-13 13S11 35 11 26Z" fill="#412b25" />
    <path d="M15 27c1-6 7-7 9-2 2-5 8-4 9 2l-9 9Z" fill="#fff1dd" />
    <circle cx="19" cy="25" r="1.7" fill="#412b25" /><circle cx="29" cy="25" r="1.7" fill="#412b25" />
  </>,
  risk_analyst: (
    <>
      <path d="M10 20c0-4.5 1-8.2 3-10.6.7-.8 2-.8 2.7 0l4.2 4.1a18 18 0 0 1 8.2 0l4.2-4.1c.7-.8 2-.8 2.7 0 2 2.4 3 6.1 3 10.6v5.7c0 7.9-6.7 13.1-14 16.3-7.3-3.2-14-8.4-14-16.3Z" fill="#f3fff4" />
      <path d="M13.5 22c1.9-4.5 7.2-4.7 10.5-.8 3.3-3.9 8.6-3.7 10.5.8 1.8 4.5-1.8 8.9-6.2 7.8L24 28l-4.3 1.8c-4.4 1.1-8-3.3-6.2-7.8Z" fill="#183b31" />
      <rect x="17.6" y="21.7" width="3.4" height="5.3" rx="1.7" fill="#f3fff4" />
      <rect x="27" y="21.7" width="3.4" height="5.3" rx="1.7" fill="#f3fff4" />
      <path d="m21.5 32.3 1.8 1.8 3.2-3.4" fill="none" stroke="#183b31" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  news_analyst: (
    <>
      <path d="M9 29c0-8.2 5.7-13 11.6-14.1-.5-2-.2-4.2 1.1-5.9 2.7 1.3 4.4 3.2 5.1 5.5 2.3-1.9 5-2.5 7.7-1.7l-2.6 4.7a11.8 11.8 0 0 1 4.8 8.2l5 3.7c.9.7.7 2-.4 2.2l-5.4 1.2c-2.2 5.3-7 8-12.7 8C15.1 40.8 9 36.3 9 29Z" fill="#fff1ee" />
      <path d="M11.5 25.8c0-6.2 4.8-11.3 11-11.8" fill="none" stroke="#502132" strokeWidth="2.4" strokeLinecap="round" />
      <rect x="8" y="24.5" width="6.5" height="9.5" rx="3.25" fill="#502132" />
      <path d="M13 32c1.5 2.8 3.9 4 7.3 4" fill="none" stroke="#502132" strokeWidth="1.8" strokeLinecap="round" />
      <rect x="27.4" y="22.8" width="3.8" height="5.5" rx="1.9" fill="#502132" />
    </>
  ),
  equity_scout: (
    <>
      <path d="M17.8 20.7C11.5 18 7.9 12 8.5 8.5c6.3-.5 12 2.9 15 7.3C22.4 10.5 25 6.4 27 5.6c4.3 3.3 6.6 9 6 14.5 5.2 3.1 8 7.2 7.8 11.9-.3 7.6-8.5 10.2-16.2 10.2-8.3 0-14.5-3.2-14.5-9.9 0-5 3.1-8.9 7.7-11.6Z" fill="#101a36" />
      <circle cx="32.5" cy="28.3" r="5.6" fill="#f5f8ff" />
      <circle cx="33.8" cy="27.3" r="2.1" fill="#566dc1" />
      <path d="M19 30.1c1.4-1.7 3.3-1.6 4.6.3" fill="none" stroke="#a3baff" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
};

export default function AgentAvatar({ role }: { role: string }) {
  const portrait = Object.hasOwn(portraits, role) ? portraits[role as keyof typeof portraits] : portraits.lead;
  return <span className={`terminal-agent-avatar ${role}`} aria-hidden="true">
    <svg viewBox="0 0 48 48" focusable="false">{portrait}</svg>
  </span>;
}
