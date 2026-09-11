# game-content-radar

**Game Demand Radar + Xiaoheihe Content Engine + Preliminary SEO Opportunity Radar**

V1.4 focuses on making the local Web Dashboard behave like a desktop tool instead of a developer server.

## Recommended daily use on macOS

After applying this update, normally you only need to double-click:

```text
scripts/start-web.command
```

V1.4 starts the FastAPI service in the background, waits for `/api/health` to become ready, opens the dashboard, and then the launcher process can exit. Closing the Terminal window no longer stops the dashboard.

Dashboard:

```text
http://127.0.0.1:8787
```

To stop or restart the background service:

```text
scripts/stop-web.command
scripts/restart-web.command
```

Runtime log:

```text
logs/web.log
```

PID file:

```text
.game-content-radar-web.pid
```

## Web UI changes in V1.4

The dashboard now defaults to the actual daily workflow:

1. open the page;
2. click **运行今日雷达**;
3. review **覆盖型推荐** and **深度型推荐**;
4. open/edit/copy a Draft;
5. inspect the separate SEO / game-site candidate.

Developer-oriented controls are moved into **高级选项**:

- config selector;
- real / fixture / offline mode;
- optional report date.

The default mode is **实时数据（正式使用）**.

The dashboard also polls `/api/health` and shows real service state:

- green: 服务正常;
- yellow: 雷达运行中;
- red: 服务断开.

If the backend stops while the browser page is still open, the page shows a reconnect banner instead of a misleading green status dot.

## CLI remains available

```bash
game-radar daily --config config/codex.yaml
game-radar web --config config/codex.yaml
```

The CLI is still useful for automation/debugging, but the Web Dashboard is the recommended daily interface.

## Important: Fixture is not live data

Fixture mode reads deterministic sample items from the repository. It exists only for development/testing and must not be used for actual Xiaoheihe topic decisions.

## Core workflow

```text
public game signals
→ normalize / cluster / aggregate
→ Xiaoheihe Publish Score
→ Reach Pick + Value Pick
→ Chinese Draft + Media Plan
→ preliminary SEO / game-site opportunity queue
→ human review
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Human review remains the publishing gate; V1.4 still does not automate Xiaoheihe login or posting.
