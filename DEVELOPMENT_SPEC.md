# 盒友编辑台 V2.0 — 实际实现说明

产品基线见 `docs/research/HEYBOX_CONTENT_STUDIO_V2_REFACTOR_PLAN.md`，实际状态以 `docs/FEATURE_STATUS.md` 为准。

## 边界

本地优先，Python3.11+ / FastAPI / Pydantic v2 / 文件系统JSON / 原生HTML CSS JavaScript。不引入前端构建或云数据库。只服务编辑运营，`game-keyword-radar` 不依赖本服务。

## 模块

| 模块 | 职责 |
|---|---|
| models.py | 数据约束、三栏目七形态、稿件/审核/发布/指标模型 |
| storage.py | 模式隔离、原子JSON、文件锁、乐观版本、报告latest |
| service.py | 编辑变更、证据核验、审核失效、排期/发布/指标、推荐 |
| validation.py | 价格/评分/职务/引语/细节等字段检查、派生数据依赖、保守文本lint |
| collectors/ | 已有适配器改名复用与详情/评论新适配 |
| collection.py | 预算内发现线索、幂等候选、来源状态；不调用写稿 |
| writing.py | 研究包、大纲、可选模型结构化输出、ZIP与发布文本 |
| jobs.py | 本地后台任务记录；进程重启标记中断，不偷偷续写 |
| webapp.py | API、会话/同源/路径/图片防护、资料与编辑路由 |
| web_ui/ | 日常工作台、选题/题材/研究/编辑/排期/复盘/设置 |
| runtime.py / cli.py | 后台启动、就绪核对、独立CLI、身份安全停止 |
| legacy.py | 旧文件只读清单、显式复制与SHA-256校验 |

## 工程调整（相对计划）

1. 来源/主张/素材/版本/发布记录作为**一份Brief聚合JSON**原子保存，而不是多个独立目录分别写入，避免半更新。题材、上传文件、设置与运行报告分开。
2. 编辑优先级是填写完整度及预算的规则分；未知字段显示缺口。不是按53条调查样本训练的效果模型。
3. 变更正文或核心简报保守地将全部相关事实转为待核验，不声称已经实现语义级精确影响分析；已发表的历史版本仍保留。
4. 采集去重采用URL/来源身份+内容形态，不声称有完整跨站语义聚类。研究与合并由人选择角度。
5. 平台规则用人工核查记录，自动检查的是是否有人承担本次审核，不自动断言现行平台政策。
6. 无模型可用时只给大纲/研究包。待审稿由手动导入或成功的可选模型生成，不用模板填充伪造完成。

## 核心状态与版本

选题创建 → 待补证 → 简报就绪 → 待审稿 → 人工审核 → 已审核 → 排期 → 手动发布登记。另有不合受众、暂停、归档。

修改正文/事实/来源/素材将撤销批准，价格到期在批准复制或发布登记时再次拦截。所有变更要求 `expected_version`；错误版本返回409。稿件版本追加、发布记录钉住采用版本，不静默覆盖。

设置与PolicyReview不参与每篇的乐观锁；单机编辑有共享全局设置的设计，不能将其描述为多人同时编辑能力。

## 运行模式

`live` 真实资料、`example` 演示资料分目录；`offline` 只写独立运行记录，不清空真实选题。不默认从演示切入真实，也不读取未批准旧SEO产物来自动产生新稿。

## API概览

- GET `/api/meta`, `/api/health`, `/api/dashboard`, `/api/analytics`
- POST `/api/run`, `/api/seeds`, `/api/import-pack`
- GET/POST/PUT `/api/briefs` 与 `/api/briefs/{id}`
- PUT `.../source`, `.../claim`, `.../asset`, `.../draft`
- POST `.../claims/{id}/verify`, `.../steam`, `.../curate`, `.../generate`
- POST `.../approve`, `.../schedule`, `.../publish`, `.../metric`, `.../state`
- GET `.../prompt`, `.../bundle`, `.../copy`
- GET/PUT `/api/subjects`, `/api/settings`；PUT `/api/policy`
- GET `/api/legacy`, `/api/legacy/{index}`, `/api/jobs/{id}`

实际参数以FastAPI运行后的 `/docs` 以及模型为准。API写操作要求从 `/api/meta` 读取的 `X-Heybox-Token`；禁止跨站写入。上传端点用multipart，其他主要写入为JSON。

## 完成判定

实现和测试清单见质量报告与验收矩阵。自动字段检查、浏览器交互测试、真实来源测试、真人发布效果是四层不同工作，不能互相替代。
