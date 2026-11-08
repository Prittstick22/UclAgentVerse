---
id: 20261108T005012Z-mo-to-all-notifications-and-home-activity-follow-the-api-c
from: mo
to: all
type: handoff
status: open
issue: 10
created: 2026-11-08T00:50Z
---
# Notifications and home activity follow the API contract

The notification endpoints now use the documented response shape. An awaiting-approval proposal or user approval request creates a decision notification. Completed maintain runs populate the digest, and stale held quotes create coverage alerts. The existing notification.created event links subscribers to decision and coverage notifications without adding fields.

## Replies
