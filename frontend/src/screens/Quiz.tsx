// SCAFFOLD: renders questions and posts answers. TODO(#fe-quiz): one question per step, £ examples, follow-up question, mandate editor.
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Mandate, ProfileResult, Question } from "../lib/types";

export default function Quiz() {
  const [qs, setQs] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<{ profile: ProfileResult; mandate: Mandate } | null>(null);
  useEffect(() => { api.questions().then((r) => setQs(r.questions)); }, []);
  return (
    <div className="max-w-2xl space-y-6">
      {qs.map((q) => (
        <div key={q.id}>
          <p className="font-medium">{q.text}</p>
          <div className="flex flex-wrap gap-2 mt-2">
            {q.options.map((o) => (
              <button key={o.id} onClick={() => setAnswers({ ...answers, [q.id]: o.id })}
                className={`rounded px-3 py-1 text-sm border ${answers[q.id] === o.id ? "border-emerald-400 text-emerald-300" : "border-slate-700"}`}>
                {o.label}
              </button>
            ))}
          </div>
        </div>
      ))}
      <button className="rounded bg-emerald-600 px-4 py-2" onClick={() => api.quiz(answers).then(setResult)}>See my profile</button>
      {result && (
        <div className="rounded-xl bg-slate-900 p-4">
          <p className="text-lg capitalize">{result.profile.name}</p>
          <p className="text-sm text-slate-400">{result.profile.explanation}</p>
          {result.profile.follow_up_question && <p className="mt-2 text-amber-300">{result.profile.follow_up_question}</p>}
          <pre className="mt-3 text-xs text-slate-400">{JSON.stringify(result.mandate.ranges, null, 1)}</pre>
        </div>
      )}
    </div>
  );
}
