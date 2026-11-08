// SCAFFOLD: portfolio summary + correlation lattice. TODO(#fe-home, #fe-pnl, #fe-lattice, #fe-rebalances): full home screen.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, MOCK } from "../lib/api";
import type { CorrelationReport, Notification, Portfolio } from "../lib/types";
import CorrelationLattice from "../components/CorrelationLattice";

export default function Home() {
  const [p, setP] = useState<Portfolio | null>(null);
  const [corr, setCorr] = useState<CorrelationReport | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationError, setNotificationError] = useState("");
  const refreshVersion = useRef(0);

  const refresh = useCallback(() => {
    const version = ++refreshVersion.current;
    Promise.all([api.portfolio(), api.notifications()]).then(([portfolio, { items }]) => {
      if (refreshVersion.current !== version) return;
      setP(portfolio);
      setNotifications(items);
      setNotificationError("");
    }).catch(() => {
      if (refreshVersion.current === version) setNotificationError("Couldn't load portfolio activity.");
    });
  }, []);

  useEffect(() => {
    refresh();
    api.correlation().then(setCorr).catch(() => setCorr(null));
    const stream = MOCK ? null : new EventSource("/api/events/stream");
    for (const type of ["open", "run.started", "run.completed", "notification.created", "approval.decided",
      "order.filled", "clock.tick", "mode.changed"]) {
      stream?.addEventListener(type, refresh);
    }
    return () => {
      refreshVersion.current++;
      stream?.close();
    };
  }, [refresh]);

  function markRead(id: string) {
    setNotificationError("");
    api.markNotificationRead(id).then(() => {
      if (MOCK) {
        setNotifications((items) => items.map((item) => item.id === id ? { ...item, read: true } : item));
      } else {
        refresh();
      }
    }).catch(() => setNotificationError("Couldn't mark this item as read."));
  }

  const attention = notifications.filter((item) => item.kind !== "digest");
  const digest = notifications.filter((item) => item.kind === "digest");
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-6">
        <Stat label="Portfolio value" value={p ? `£${p.nav_gbp.toLocaleString()}` : "…"} />
        <Stat label="Status" value={p?.status.replaceAll("_", " ") ?? "…"} />
        <Stat label="Reviews" value={String(p?.counters.reviews ?? 0)} />
        <Stat label="Checks" value={String(p?.counters.checks ?? 0)} />
        <Stat label="Decisions asked of you" value={String(p?.counters.decisions_asked ?? 0)} />
        <Stat label="Adjustments" value={String(p?.counters.adjustments ?? 0)} />
      </div>
      {notificationError && <p role="alert">{notificationError}</p>}
      <ActivityList title="Notifications" items={attention} markRead={markRead} />
      <ActivityList title="Activity digest" items={digest} markRead={markRead} />
      {corr && <CorrelationLattice report={corr} />}
    </div>
  );
}

function ActivityList({ title, items, markRead }: {
  title: string; items: Notification[]; markRead: (id: string) => void;
}) {
  if (!items.length) return null;
  return (
    <section className="space-y-2">
      <h2 className="font-semibold">{title}</h2>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.id} className="rounded-xl bg-slate-900 px-4 py-3">
            <div className="font-medium">{item.title}</div>
            <p className="text-sm text-slate-400">{item.body}</p>
            {!item.read && <button className="mt-2 text-sm underline" onClick={() => markRead(item.id)}>Mark as read</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-slate-900 px-4 py-3"><div className="text-xs text-slate-400">{label}</div><div className="text-lg capitalize">{value}</div></div>;
}
