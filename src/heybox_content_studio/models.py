from __future__ import annotations

from dataclasses import dataclass, field as dc_field, asdict
from datetime import datetime, timezone
from typing import Any, Literal
import re
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Mode = Literal['live', 'example']
Column = Literal['buy_smart', 'classic_rediscovery', 'behind_the_game']
Form = Literal['deals', 'ratings', 'new_game', 'classic', 'detail', 'creator', 'ranking']
Status = Literal['backlog', 'needs_research', 'brief_ready', 'draft_ready', 'in_review', 'approved', 'scheduled', 'published', 'out_of_scope', 'blocked', 'expired', 'archived']
COLUMN_NAMES = {'buy_smart': '买得明白', 'classic_rediscovery': '经典再发现', 'behind_the_game': '作品背后'}
FORM_COLUMNS = {'deals': 'buy_smart', 'ratings': 'buy_smart', 'new_game': 'buy_smart', 'classic': 'classic_rediscovery', 'detail': 'classic_rediscovery', 'creator': 'behind_the_game', 'ranking': 'behind_the_game'}
FORM_NAMES = {'deals': '精选折扣', 'ratings': '评分筛选', 'new_game': '新游前瞻', 'classic': '经典回顾', 'detail': '细节拆解', 'creator': '制作人故事', 'ranking': '有界榜单'}
STATUS_NAMES = dict(zip(['backlog','needs_research','brief_ready','draft_ready','in_review','approved','scheduled','published','out_of_scope','blocked','expired','archived'], ['选题待定','待补证','简报就绪','待审初稿','审核中','已审核','已排期','已发布','不合受众','暂停处理','已过期','已归档']))

def uid() -> str:
    return uuid4().hex[:16]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('时间必须包含时区，例如 +08:00 或 Z')
    return dt.astimezone(timezone.utc)

class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    @field_validator('id', check_fields=False)
    @classmethod
    def safe_record_id(cls, value):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', value):
            raise ValueError('记录ID只允许字母、数字、下划线和短横线')
        return value

class Subject(Record):
    id: str = Field(default_factory=uid)
    name: str = Field(min_length=1, max_length=180)
    kind: Literal['game', 'person', 'studio', 'publisher', 'group'] = 'game'
    aliases: list[str] = Field(default_factory=list, max_length=30)
    platform_ids: dict[str, str] = Field(default_factory=dict)
    confirmed: bool = False
    familiarity: Literal['unknown', 'researched', 'played'] = 'unknown'
    notes: str = Field(default='', max_length=4000)

class SourceRecord(Record):
    id: str = Field(default_factory=uid)
    title: str = Field(default='', max_length=300)
    url: str = Field(default='', max_length=2000)
    source_type: Literal['official', 'interview', 'media', 'community', 'self', 'unknown'] = 'unknown'
    role: Literal['discovery', 'fact'] = 'discovery'
    publisher: str = Field(default='', max_length=180)
    original_date: str | None = None
    read_at: str | None = None
    read_status: Literal['unread', 'read', 'partial', 'failed', 'needs_access'] = 'unread'
    summary: str = Field(default='', max_length=16000)
    excerpt: str = Field(default='', max_length=1600)
    locator: str = Field(default='', max_length=1000)
    is_primary: bool = False
    provenance: Literal['manual', 'collector', 'import'] = 'manual'
    access_note: str = Field(default='', max_length=2000)

class Claim(Record):
    id: str = Field(default_factory=uid)
    text: str = Field(min_length=1, max_length=5000)
    kind: Literal['fact', 'inference', 'opinion', 'quote', 'price', 'rating', 'role', 'detail', 'design_intent', 'historical_low', 'free_offer', 'ranking'] = 'fact'
    required: bool = True
    source_ids: list[str] = Field(default_factory=list, max_length=30)
    locator: str = Field(default='', max_length=1200)
    status: Literal['pending', 'verified', 'conflict'] = 'pending'
    verified_by: str | None = None
    verified_at: str | None = None
    valid_until: str | None = None
    conflicts: str = Field(default='', max_length=4000)
    notes: str = Field(default='', max_length=4000)
    data: dict[str, Any] = Field(default_factory=dict)

class MediaAsset(Record):
    id: str = Field(default_factory=uid)
    title: str = Field(default='', max_length=300)
    url: str = Field(default='', max_length=2000)
    local_file: str | None = None  # server-assigned basename only; never a user-supplied path
    source_id: str | None = None
    publisher: str = Field(default='', max_length=180)
    purpose: Literal['cover', 'evidence', 'illustration'] = 'illustration'
    caption: str = Field(default='', max_length=2000)
    timecode: str = Field(default='', max_length=120)
    usage_note: str = Field(default='', max_length=2000)
    usage_confirmed: bool = False
    spoiler_level: Literal['none', 'mechanics', 'minor_story', 'major_story'] = 'none'

class BriefInput(Record):
    title: str = Field(min_length=1, max_length=200)
    column: Column = 'classic_rediscovery'
    content_form: Form = 'classic'
    pool: Literal['timely', 'evergreen'] = 'evergreen'
    audience: str = Field(default='中文 PC / Steam 单机与精品游戏玩家', max_length=1500)
    reader_question: str = Field(default='', max_length=2000)
    angle: str = Field(default='', max_length=2000)
    thesis: str = Field(default='', max_length=3000)
    original_contribution: str = Field(default='', max_length=4000)
    reader_value: str = Field(default='', max_length=2000)
    scope_confirmed: bool = False
    subject_ids: list[str] = Field(default_factory=list, max_length=30)
    estimated_human_minutes: int | None = Field(default=None, ge=1, le=10000)
    actual_human_minutes: int = Field(default=0, ge=0, le=100000)
    expires_at: str | None = None
    spoiler_level: Literal['none', 'mechanics', 'minor_story', 'major_story'] = 'none'
    spoiler_note: str = Field(default='', max_length=2000)
    media_none_reason: str = Field(default='', max_length=2000)
    author_experience: str = Field(default='', max_length=2000)
    missing_evidence: list[str] = Field(default_factory=list, max_length=50)
    notes: str = Field(default='', max_length=5000)

    @model_validator(mode='after')
    def compatible_column(self):
        if FORM_COLUMNS[self.content_form] != self.column:
            raise ValueError('内容形态与栏目不匹配')
        if self.expires_at:
            parse_time(self.expires_at)
        return self

class DraftInput(Record):
    title: str = Field(min_length=1, max_length=220)
    title_candidates: list[str] = Field(default_factory=list, max_length=5)
    body_markdown: str = Field(min_length=1, max_length=60000)
    comment_hook: str = Field(default='', max_length=2000)
    used_claim_ids: list[str] = Field(default_factory=list, max_length=200)
    assistance: Literal['manual', 'web_ai_import', 'codex', 'command', 'outline'] = 'manual'

class DraftRevision(DraftInput):
    revision: int
    created_at: str = Field(default_factory=now_iso)
    fingerprint: str = ''
    check_notes: list[str] = Field(default_factory=list)

class Approval(Record):
    reviewer: str
    checked_at: str
    draft_revision: int
    fingerprint: str
    spoiler_checked: bool
    facts_checked: bool
    media_checked: bool
    policy_checked: bool

class PublicationRecord(Record):
    id: str = Field(default_factory=uid)
    url: str
    published_at: str
    draft_revision: int
    title: str
    recorded_at: str = Field(default_factory=now_iso)

class MetricSnapshot(Record):
    id: str = Field(default_factory=uid)
    publication_id: str
    observed_at: str
    window: Literal['24h', '72h', '7d', 'custom'] = '24h'
    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    favorites: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    follows: int | None = Field(default=None, ge=0)
    source_note: str = Field(default='', max_length=2000)
    missing_reason: str = Field(default='平台未提供 / 未记录', max_length=2000)
    comment_quality: str = Field(default='', max_length=2000)
    post_age_hours: float = 0

class Brief(BriefInput):
    id: str = Field(default_factory=uid)
    mode: Mode = 'live'
    version: int = 1
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    status: Status = 'backlog'
    origin_key: str | None = None
    sources: list[SourceRecord] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    assets: list[MediaAsset] = Field(default_factory=list)
    drafts: list[DraftRevision] = Field(default_factory=list)
    approval: Approval | None = None
    scheduled_at: str | None = None
    publications: list[PublicationRecord] = Field(default_factory=list)
    metrics: list[MetricSnapshot] = Field(default_factory=list)
    audit: list[dict[str, Any]] = Field(default_factory=list)

class Settings(Record):
    reviewer_name: str = Field(default='本机编辑', min_length=1, max_length=100)
    audience: str = Field(default='中文 PC / Steam 单机与精品游戏玩家', max_length=1500)
    column_mix: dict[str, int] = Field(default_factory=lambda: {'buy_smart':40, 'classic_rediscovery':40, 'behind_the_game':20})
    daily_minutes: int = Field(default=45, ge=5, le=1440)
    weekly_minutes: int = Field(default=240, ge=5, le=10080)
    heavy_posts_per_week: int = Field(default=2, ge=0, le=14)
    daily_posts_max: int = Field(default=2, ge=1, le=5)
    price_fresh_minutes: int = Field(default=30, ge=5, le=1440)
    min_review_count: int = Field(default=100, ge=1, le=10000000)
    country: str = Field(default='CN', pattern=r'^[A-Z]{2}$')
    enabled_sources: dict[str, bool] = Field(default_factory=lambda: {'steam_store':True, 'steam_news':True, 'epic':True, 'reddit':False, 'official_rss':False, 'xiaoheihe':False})
    watched_apps: dict[int, str] = Field(default_factory=dict)
    subreddits: list[str] = Field(default_factory=lambda:['Steam','gaming'], max_length=10)
    official_rss: list[str] = Field(default_factory=list, max_length=10)
    max_requests: int = Field(default=40, ge=1, le=150)
    request_timeout: int = Field(default=10, ge=2, le=30)
    llm_mode: Literal['manual', 'codex', 'command'] = 'manual'
    llm_timeout: int = Field(default=240, ge=15, le=600)

    @model_validator(mode='after')
    def validate_settings(self):
        if set(self.column_mix) != set(COLUMN_NAMES) or sum(self.column_mix.values()) != 100 or any(v < 0 for v in self.column_mix.values()):
            raise ValueError('三栏目配比必须非负且合计100')
        if len(self.watched_apps) > 20 or any(a <= 0 for a in self.watched_apps):
            raise ValueError('最多关注20个正整数Steam AppID')
        allowed = {'steam_store','steam_news','epic','reddit','official_rss','xiaoheihe'}
        if set(self.enabled_sources) - allowed:
            raise ValueError('未知数据源；本工具不再采集CCU/SEO增长')
        return self

class PolicyReview(Record):
    urls: list[str] = Field(default_factory=list, max_length=10)
    checked_at: str | None = None
    reviewer: str = ''
    ai_note: str = Field(default='', max_length=4000)
    notes: str = Field(default='', max_length=4000)
    incentive_status: Literal['unconfirmed', 'manual_reviewed'] = 'unconfirmed'

@dataclass(slots=True)
class SourceItem:
    """Compatibility contract for retained V1 collectors, not a publishing brief."""
    id: str
    source: str
    source_url: str
    source_type: str
    game_name: str
    title: str
    summary: str = ''
    published_at: str | None = None
    collected_at: str = dc_field(default_factory=now_iso)
    language: str = 'en'
    category: str = 'other'
    metrics: dict[str, Any] = dc_field(default_factory=dict)
    raw_text: str = ''
    media_urls: list[str] = dc_field(default_factory=list)

    def to_dict(self):
        return asdict(self)
