from __future__ import annotations
import json
from importlib.resources import files
from .models import Brief, Claim, SourceRecord, MediaAsset, DraftRevision, now_iso, uid
from .storage import Store

SEEDS = [
 ('buy_smart','deals','本周折扣里，适合一个人慢慢玩的游戏','时效价格、单人支持、玩法理由和不适合条件','timely'),
 ('buy_smart','ratings','高好评率背后，评价样本量应该怎么看？','同口径分子分母、筛选条件、不同规模的真实例子','evergreen'),
 ('buy_smart','deals','买本体还是合集：经典系列的版本怎么选','各SKU内容、当前地区价格和重复购买提醒','evergreen'),
 ('buy_smart','new_game','这款新游真正不同的，是哪个玩法？','官方机制说明、原始演示和未知项','timely'),
 ('classic_rediscovery','classic','小时候玩过的小游戏，现在该找哪个正式版本？','官方现代入口、原作/移植/重制的对应关系','evergreen'),
 ('classic_rediscovery','classic','不靠任务箭头，一段经典流程怎样引导玩家？','三个具体场景的画面与流程条件','evergreen'),
 ('classic_rediscovery','detail','大镖客的一个环境反应，怎样增强世界可信度？','原始演示或本人复现、平台版本和触发条件','evergreen'),
 ('classic_rediscovery','detail','星露谷的一条已知彩蛋，为什么还值得讨论？','可确认机制、具体画面与解释边界','evergreen'),
 ('behind_the_game','creator','从一段旧访谈，看宫崎英高如何取舍一个设计问题','原访谈日期与原文、具体作品职务、场景证据','evergreen'),
 ('behind_the_game','creator','一家工作室不同作品的设计共性，真的存在吗？','至少两个具体作品例子与反例、团队职责','evergreen'),
 ('behind_the_game','ranking','限定一个奖项，重新回顾一组工作室的作品','官方记录、时期、去重、归属和排序标准','evergreen'),
 ('behind_the_game','creator','一次开发限制，怎样改变了最终玩法？','开发日志/演讲、实际作品例子、角色说明','evergreen'),
]

def create_seeds(store: Store, mode: str='live') -> list[str]:
    ids=[]
    for i,(column,form,title,gap,pool) in enumerate(SEEDS):
        b=Brief(title=title,column=column,content_form=form,pool=pool,mode=mode,reader_question=title,
                origin_key='editorial-seed-v2-'+str(i),status='needs_research',missing_evidence=[gap],notes='这是待研究角度种子，不是已验证事实或已完成文章。')
        saved,_=store.create_once(b); ids.append(saved.id)
    return ids


def create_demo(store: Store) -> list[str]:
    ids=[]
    demos=[
        ('buy_smart','ratings','高分不等于适合你：一份有边界的选游清单','先按单人体验与语言筛选，再解释评分样本量','买得明白的资料演示','evergreen'),
        ('classic_rediscovery','classic','不靠任务箭头，游戏怎样悄悄给你指路？','对照三个场景的光线、运动方向和构图','经典再发现的资料演示','evergreen'),
        ('behind_the_game','creator','一个开发决定，怎样留下作品的个人风格？','从一次旧访谈追到一个场景，区分创作意图与个人解释','作品背后的资料演示','evergreen'),
    ]
    for i,(column,form,title,angle,thesis,pool) in enumerate(demos):
        source=SourceRecord(title='演示资料 / 非真实游戏事件',url='https://example.com/editorial-demo',source_type='official',role='fact',publisher='示例发布方',read_status='read',summary='此为离线界面演示。示例作品使用光线方向帮助玩家识别路径，不代表任何真实游戏事实。',read_at=now_iso(),is_primary=True,locator='演示材料第一段')
        claim=Claim(text='示例作品使用光线方向展示行进线索。',source_ids=[source.id],locator='示例材料第一段',status='verified',verified_by='示例审核标记',verified_at=now_iso())
        b=Brief(title=title,column=column,content_form=form,pool=pool,mode='example',reader_question=title,angle=angle,thesis=thesis,
                original_contribution='比较同一片段中引导方式的不同用途；此为演示贡献。',reader_value='帮助读者区分可以观察的事实与解释。',scope_confirmed=True,
                estimated_human_minutes=15,origin_key='demo-v2-'+str(i),sources=[source],claims=[claim],media_none_reason='示例只用于展示编辑流程，不发布',status='brief_ready')
        if i==0:
            b.pool='timely'
            claim.kind='rating'; claim.text='示例数据：同一查询下90条推荐 / 100条评价，推荐率90%。'
            claim.data={'platform':'steam','scope':'matching_query_summary','observed_at':now_iso(),'positive':90,'negative':10,'total_reviews':100,'filters':{'language':'all','review_type':'all','purchase_type':'steam','filter_offtopic_activity':1}}
            source.summary='示例评价数据为90条推荐和10条不推荐，共100条，仅为离线演示，不代表真实游戏。'
        if i==2:
            b.claims.append(Claim(text='示例制作人A在示例作品B中担任总监。',kind='role',source_ids=[source.id],locator='示例演示',data={'person':'示例制作人A','work':'示例作品B','role':'总监','as_of':'2026-09-11'}))
            b.status='needs_research'
        if i==1:
            b.drafts.append(DraftRevision(revision=1,title=title,title_candidates=[title,'一束光为什么能成为路标？','从一个场景看游戏的无声引导'],body_markdown=f'## 先看问题\n\n这是一篇**示例初稿**，只展示编辑、核验与保存流程，不代表真实作品事实。\n\n示例作品使用光线方向展示行进线索。[C:{claim.id}]\n\n## 再看解释\n\n这里的解释需要真实场景和对照。正式使用时，用你已经核实的游戏材料替换本稿，不要直接发布。',used_claim_ids=[claim.id],assistance='web_ai_import'))
            b.status='draft_ready'
        saved,_=store.create_once(b); ids.append(saved.id)
    return ids
