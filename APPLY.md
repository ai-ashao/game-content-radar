# 从 Game Content Radar V1.4 升级到盒友编辑台 V2.0

这是**完整源码包，不是覆盖增量包**。远程仓库未改名、未提交。`game-keyword-radar` 不在本次修改范围。

## 推荐安装方式：新旧并排，先验证再替换

1. 在旧项目运行 `scripts/stop-web.command`，确认旧8787服务已停止。
2. 将本包解压到新目录 `heybox-content-studio`，不要覆盖旧 `.venv`、`.git`、`data` 或 `reports`。
3. 双击 `启动盒友编辑台.command`。先试示例流程，再处理真实稿件。
4. 确认新工具可用后，再将新源码提交到内容项目。仓库可以在GitHub手动改名为 `heybox-content-studio`；本包不执行远程改名或提交。

新目录使用自己的虚拟环境，避免旧分发包的 `game-radar` 入口与游戏词雷达冲突。不需要删除旧数据，也不需要重写游戏词雷达。

## 迁移旧报告和编辑稿

先停止旧服务。打开**新项目目录**的终端：

```bash
source .venv/bin/activate

# 第一步：只读预览，检查识别出的文件
heybox-studio migrate --from "/你的路径/game-content-radar"

# 第二步：明确执行复制备份；每个文件校验SHA-256
heybox-studio migrate --from "/你的路径/game-content-radar" --copy
```

可识别旧 `reports/YYYY-MM-DD/` 中的报告、JSON、编辑稿，以及 `data/` 下的SQLite数据库与常见旁文件。复制进入新项目的 `legacy/snapshot-*/`，生成清单。网页“旧版归档”可只读下载；不会将旧SEO分、假样例或玩家历史转为新稿。

单文件超过250MB、符号链接和目录外文件不复制。当前工具不穷尽旧项目的所有自定义路径；自定义素材、配置、额外数据库请另行备份整个旧目录。旧配置不会自动覆盖新设置。

默认不删除或改写旧文件。源数据变动导致摘要不一致时会停止复制；原文件不变，但可能留下未完成的备份目录，可人工检查。

## 在原Git仓库提交新源码

先备份或提交未完成改动，保留 `.git` 和用户数据。将本包中的源码、文档、脚本、测试和配置示例复制到仓库。重点替换 `pyproject.toml`、README和启动器，并加入 `src/heybox_content_studio/`。

旧 `src/game_content_radar/` 不再参与新包构建（包发现只包含新模块）；确认归档和迁移完成后可从Git移除旧代码，**不要连带删除旧数据和报告**。不建议直接在旧虚拟环境上升级：新建本项目环境更清楚。仓库目录名本身不影响程序，但目录移动后请重新启动，让实例身份与新路径一致。

## 启动检查

正常启动后，打开 `http://127.0.0.1:8787/api/health`，应包含：

```json
{"service":"heybox-content-studio","version":"2.0.0","status":"ready"}
```

其余PID/实例字段随本机生成。终端关闭后刷新主页仍应正常；如失败，用 `scripts/view-logs.command` 查看日志。当前压缩包未在你的Mac上执行，不以Linux进程测试代替Finder验收。

## 回滚

停止新项目，重新启动旧目录。新旧数据独立，旧代码与原始报告未删除。若已修改原Git仓库，先保留新资料，再通过Git恢复代码；不要用 `git clean -fdx` 清理用户数据。
