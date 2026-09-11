# 来源、适配与基线

## 代码基线

当前仓库：`ai-ashao/heybox-content-studio`；代码历史来自旧仓库 `ai-ashao/game-content-radar`。
本次通过GitHub连接读取到主分支提交：`4fc766ffcadae23fe51b7772ea8408515f3189cc`（2026-09-11）。
保留Steam适配器的原始blob为 `b944351dbc94bfda621682be7cec6b2a4cd556c7`，并与已有归档核对。新包保留与改造采集适配、完全拆分编辑数据和服务职责，不修改游戏词项目。

V2.0 在保留原 Git 历史的前提下完成仓库改名，并直接更新主分支；没有创建发布分支或执行公网部署。

## 官方技术参考

- Steam评论API：https://partner.steamgames.com/doc/store/getreviews
- Steam评论说明：https://partner.steamgames.com/doc/store/reviews
- Steam新闻API：https://partner.steamgames.com/doc/webapi/ISteamNews
- FastAPI静态文件：https://fastapi.tiangolo.com/tutorial/static-files/
- Codex非交互执行：https://developers.openai.com/codex/noninteractive
- Codex配置参考：https://developers.openai.com/codex/config-reference

核对日期2026-09-11。接口返回仍需在运行地区实际验证。商店featured/categories、appdetails和Epic促销JSON不被视为稳定不可变契约。

## 三份真实出处参考研究包

`examples/` 中的参考包根据以上Steam官方文档、Portal2官方商店页及PlayStation2015年访谈整理：

- https://store.steampowered.com/app/620/Portal_2/
- https://blog.playstation.com/2015/03/20/a-conversation-with-bloodborne-creator-hidetaka-miyazaki/

它们只提供短摘要和研究起点，不整篇复制文章，不携带“已审核”结论，不包含新编造的游戏价格/玩家数/好评率。三个参考包不能当作M5已完成：本环境没有执行当前Steam评论API网络采集，也没有本人实机画面或真实发帖。

## 小黑盒调查

此前用户确认的调查与计划原样置于 `docs/research/`。53条记录是内容选型观察，不是训练集，也不是已核验的游戏事实。研究中的历史周报不应被当成2026年完整现行公约。

## 素材与第三方库

本包无字体文件、无第三方游戏图片素材包。界面使用系统字体，品牌SVG为此工作台的简单图形。用户导入的素材需自行确认用途与使用条件。第三方Python依赖通过包管理器安装，不在ZIP里分发其源码或虚拟环境。
