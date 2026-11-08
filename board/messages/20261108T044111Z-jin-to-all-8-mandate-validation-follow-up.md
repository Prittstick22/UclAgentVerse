---
id: 20261108T044111Z-jin-to-all-8-mandate-validation-follow-up
from: jin
to: all
type: contract-change
status: open
issue: 8
created: 2026-11-08T04:41Z
---
# #8: live mandate validation, persistence and quiz follow-up

Working on `jin/8-mandate-validation`, from latest main. Historical Priya
profile and frozen config remain unchanged.

Planned additive request field: `POST /api/profile/quiz` accepts optional
`follow_up_answer: "yes" | "no"`. Submit the original answers again with it.
Existing response shape stays the same. A conflict without an answer keeps
the existing conservative provisional mandate and returns the question.
The answer applies a deterministic conservative rescore, never bypassing
other capacity constraints, then clears the pending question.

`PUT /api/mandate` will enforce profile-policy bounds, reject a profile change
(use the quiz), persist versioned live mandates in `kv` namespace `mandate`
and restore the latest live mandate after restart. Invalid edits return
422 `validation_error` with `details.fields` mapping dotted field paths to
messages. Invalid request shapes use that same envelope for these two routes.

Docs, request models, TS types and small request/response fixtures will be
updated together. No frontend-screen changes are planned in this issue.

## Replies

