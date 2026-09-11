# V2计划26项验收映射

下表是实际验证层级，不是把“可自动检查字段”混同于“已完成内容事实核查”。完整日志见 `docs/qa/`。所有模拟资料均未公开发布。

| 计划序号 / 目标 | 覆盖位置 | 实际验收与边界 |
|---|---|---|
| 1 未联网不冒充真实热点 | test_example_and_offline_cannot_change_real_workspace | API模式隔离通过；界面有示例标识 |
| 2 示例不覆盖真实latest | 同上 / test_create_once_mode_isolation | 自动测试通过 |
| 3 旧稿报告数据库可定位 | test_legacy_dryrun_copy_hash_and_no_deletion | 预览、复制哈希、原文件保留通过；用户自定义路径不保证全覆盖 |
| 4 无合格题不fallback | test_no_eligible_no_recommendation / seeds | 测试通过 |
| 5 常青不过72h硬淘汰、折扣过期 | test_evergreen_old_source_ok_and_expired_deal_block | 测试通过 |
| 6 单源失败不阻断 | test_collection_single_source_failure_is_soft | 模拟429 + 可用来源，测试通过；真实来源网络未通过验收 |
| 7 受众无关不因高互动入选 | scope_confirmed + draft_gate | 字段准入测试通过；读者匹配判断由编辑确认 |
| 8 最终选入清单可复算 | prices_scope_count / curation_rechecks | 数量、最小当前价格和派生数据依赖通过 |
| 9 缺历史证据不用史低 | unsupported_history / historical_low_requires_actual_history | 结构化与关键词lint通过；无法自动识别所有暗示性文案 |
| 10 免费保留/试玩/F2P区分 | free_types / epic_free_to_keep_not_f2p | 自动测试通过；具体平台活动仍需人核对 |
| 11 不跨评分量表、无评价不写0 | rating_ratio / invalid_review_scope | 自动测试通过 |
| 12 查询口径写入、单页不当总体 | review_query_summary_and_privacy | 模拟Steam接口契约通过；非真实API成功记录 |
| 13 有限样本不称全库排行 | text_checks / computed ranking universe | 全范围用语拦截和同口径计算实现；语义归纳仍需人 |
| 14 人物/工作室/发行商分开 | test_role_is_work_specific / test_subjects_are_typed_and_isolated | 数据类型和作品角色检查通过；不自动断言任职 |
| 15 引语类型、原始日期、来源 | test_quote_original_date_and_source_required | 字段检查通过；译文准确性需人工 |
| 16 不编本人体验 | unfounded_experience / text_checks | 常见表达lint通过；不是所有第一人称语义都可识别 |
| 17 细节画面和复现条件 | test_detail_needs_visual_location | 关联素材、时间码、条件检查通过；未实际游玩验证 |
| 18 剧透与封面 | test_spoilers_and_media_confirmation | 剧透标签和封面条件检查通过；没有AI视觉审查 |
| 19 不执行来源内指令 | external argv shell=False / writing payload tests | 命令构造和失败路径通过；不宣称所有模型都免疫提示注入 |
| 20 修改后重新核验 | stale_updates / workflow approval invalidation | 自动测试通过，保守撤销事实和旧批准 |
| 21 无模型仅大纲 | manual_generation / model fallback tests | 自动测试通过；真实认证Codex未验证 |
| 22 不保证平台激励 | policy record / README / source guard | UI记录与文案边界实现；现行规则未自动核查 |
| 23 缺浏览量不造比率/关注归因 | whole_api_review / metric tests | 实际年龄、null保留和窗口提醒通过 |
| 24 稿件保存/复制/重连/导出 | API whole workflow / ZIP tests / browser bridge | API与渲染联调通过；原生浏览器HTTP与localStorage验收被环境阻断 |
| 25 后台启动与状态一致 | test_detached_service_survives_launcher_and_isolation / browser bridge | Linux真进程/健康检查和断开恢复通过；Mac Finder/关终端需本机验证 |
| 26 命令与项目独立 | pyproject only heybox-studio / wheel inspection | 包入口与静态资源检查通过；未改游戏词仓库 |

## M0–M5状态

M0–M4的本地功能已经实现，具体自动化与人工输入范围见功能状态。M5中“真实来源三栏目资料试用、用户人工成本、实际发帖反馈”未在本环境完成。附带三份有真实出处的研究包是待核验输入，不充当M5通过记录。

## 必须在用户机器补测

首次依赖安装、Finder双击、关终端继续访问、本机网络读取Steam/Epic、已认证Codex、原生浏览器localStorage、真实小黑盒手动发布后观察。

这些不是让用户重新开发功能；是本环境无法替代的运行环境和真人内容验收。
