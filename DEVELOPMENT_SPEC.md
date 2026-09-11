# game-content-radar V1.4 — Web/desktop usability revision

## Goal

Keep the V1.2/V1.3 evidence-first radar pipeline unchanged while turning the local Web Dashboard into the normal daily operating surface.

The operator should not need to understand FastAPI, ports, foreground processes, Fixture mode, or CLI lifecycle just to run a daily radar.

## Daily UX

Default flow:

```text
Double-click start-web.command
→ background service starts
→ health endpoint becomes ready
→ browser opens
→ click 运行今日雷达
→ review Reach + Value
→ edit/copy Draft
→ inspect SEO/site opportunity
```

The main page exposes one primary action. Development/test controls live under collapsed **高级选项**.

## Background service lifecycle

### start-web.command

Must:

- create `.venv` when missing;
- install the editable package when dependencies are missing;
- detect an already healthy service and simply open it;
- remove stale PID state;
- start `game-radar web` via `nohup` with stdout/stderr redirected to `logs/web.log`;
- write `.game-content-radar-web.pid`;
- poll `/api/health` before opening the browser;
- exit after successful startup without killing the dashboard.

### stop-web.command

Stops the PID created by the launcher and removes the PID file.

### restart-web.command

Runs stop then start.

## Health API

`GET /api/health` returns:

```json
{
  "ok": true,
  "status": "ready | busy",
  "version": "0.3.0",
  "started_at": "...",
  "active_job": null
}
```

When a daily radar job is queued/running, status becomes `busy`.

## Frontend service state

The browser polls health periodically:

- ready → green / 服务正常;
- busy → yellow / 雷达运行中;
- failed fetch → red / 服务断开.

A disconnected cached page must not retain a green status indicator.

## Main dashboard information hierarchy

1. Service state
2. Today-run action
3. Current report mode warning (only when needed)
4. Summary metrics
5. Reach + Value recommendations
6. Candidate pool
7. Best website opportunity
8. Source coverage + warnings
9. SEO queue
10. Report history

## Advanced options

Collapsed by default:

- config;
- data mode: live / fixture / offline;
- optional report date.

The default mode remains `live`.

## Non-goals

No changes to:

- automatic Xiaoheihe publishing;
- account/login automation;
- core scoring model;
- source collection policy;
- evidence guard;
- Semrush/SERP validation requirement.
