export default function Placeholder({ title, issue }: { title: string; issue: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-700 p-10 text-slate-400">
      <h1 className="text-xl text-slate-200 mb-2">{title}</h1>
      <p>Scaffold placeholder. Build this screen in GitHub issue <code>{issue}</code> (see docs/03-how-it-works.md §1).</p>
    </div>
  );
}
