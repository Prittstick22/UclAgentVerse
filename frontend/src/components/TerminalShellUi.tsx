import { useEffect, useRef, useState } from "react";

const iconPaths = {
  home: "m3 10 9-7 9 7v10H3z M9 20v-7h6v7",
  quiz: "M8 5H5v16h14V5h-3 M9 3h6v4H9z M8 12h8m-8 4h6",
  agents: "M15 20v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M21 20v-2a4 4 0 0 0-3-3.9 M16 3.3a4 4 0 0 1 0 7.4",
  timeline: "M3 12h4l3-7 4 14 3-7h4",
  decisions: "M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z M9 12l2 2 4-4",
  chart: "M3 3v17h18 M7 16v-4m5 4V8m5 8V5",
  search: "M10.5 18a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15Zm5.5-2 5 5",
  bell: "M18 8a6 6 0 0 0-12 0v4c0 2-1 3-2 4h16c-1-1-2-2-2-4V8Zm-8 12a2 2 0 0 0 4 0",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20 M12 6v6l4 2",
  wallet: "M20 8V5H4v14h16v-3 M15 8h6v8h-6z m2 4h1",
  close: "m6 6 12 12M18 6 6 18",
} as const;

export function ShellIcon({ name }: { name: keyof typeof iconPaths }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={iconPaths[name]} />
    </svg>
  );
}

export function TerminalBrand() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <path d="M8 28c0-5 2.6-8.9 6-10.6v-3.1a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2V16h1V11a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v5h1V8a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v11c2 2 3 5.1 3 9v2c0 7-4 11-11 11H19c-7 0-11-4-11-11Z" fill="#ebedf2" />
      <rect x="16" y="24" width="5" height="9" rx="2.5" fill="#26292e" />
      <rect x="27" y="24" width="5" height="9" rx="2.5" fill="#26292e" />
      <path d="M30 8a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3h-7Z" fill="var(--terminal-positive)" />
    </svg>
  );
}

export function DemoPasscodeDialog({ previousRejected, finish }: {
  previousRejected: boolean;
  finish: (passcode: string | null) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [value, setValue] = useState("");

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    element.showModal();
    return () => element.close();
  }, []);

  return (
    <dialog ref={dialog} className="terminal-passcode terminal-glass" aria-labelledby="demo-passcode-title"
      onCancel={(event) => { event.preventDefault(); finish(null); }}>
      <form onSubmit={(event) => { event.preventDefault(); if (value) finish(value); }}>
        <h2 id="demo-passcode-title">Enter the demo passcode</h2>
        <p>{previousRejected
          ? "The saved passcode was rejected. Enter the current passcode to continue."
          : "This action needs the public demo passcode."}</p>
        <label htmlFor="demo-passcode">Demo passcode
          <input id="demo-passcode" className="terminal-field" type="password" autoComplete="off" autoFocus required
            value={value} onChange={(event) => setValue(event.target.value)} />
        </label>
        <div className="terminal-passcode-actions">
          <button className="terminal-action" type="button" onClick={() => finish(null)}>Cancel</button>
          <button className="terminal-action terminal-action-primary" type="submit" disabled={!value}>Continue</button>
        </div>
      </form>
    </dialog>
  );
}
