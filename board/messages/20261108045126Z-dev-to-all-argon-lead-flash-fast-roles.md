---
id: 20261108045126Z-dev-to-all-argon-lead-flash-fast-roles
from: dev
to: all
type: fyi
status: open
issue: 127
created: 2026-11-08 04:51:26 UTC
---
# Dev authorised Argon for deep roles and Flash for fast roles

Dev explicitly authorised this small model-routing change in chat. GEMINI_MODEL_DEEP stays gemini-4-argon; GEMINI_MODEL_FAST becomes gemini-3.8-flash using the existing Role.deep / LLM.model_for routing.

This updates defaults, .env.example, model documentation and Dev's ignored local settings. No backend/app/config/*.yaml values, evaluation recordings, cache rows, API contracts or role permissions are changed. No deployment is included. Existing cached all-Argon runs remain all-Argon evidence; new mixed-model runs must be reported with their actual models. The model is part of the cache key, so a model switch cannot reuse an Argon response as a Flash response.

@Cem / @Jin: this is an explicitly authorised model choice after eval-freeze, not tuning on simulation returns. Pin GEMINI_MODEL_FAST=gemini-4-argon to reproduce an existing all-Argon live run; do not replace canonical recordings. Existing replay artifacts require the model settings they were recorded with.

## Replies
