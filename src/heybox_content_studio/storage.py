from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import threading
from pathlib import Path
from typing import Callable

from .models import Brief, Mode, PolicyReview, Settings, Subject, now_iso

class ConflictError(ValueError):
    """Optimistic edit revision does not match the version on disk."""


def atomic_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.{threading.get_ident()}.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as handle:
            json.dump(obj, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def json_read(path: Path, default=None):
    if not path.exists():
        return default
    # Invalid persisted data is an error, never silently treated as an empty database.
    return json.loads(path.read_text(encoding='utf-8'))


def safe_id(value: str) -> str:
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', value):
        raise ValueError('非法记录ID')
    return value

class Store:
    """Single local service. Brief+pack+revisions are one atomic aggregate.

    Each brief contains immutable draft revisions and an audit trail. All modes
    are isolated. The OS lock also protects against two accidental processes.
    """
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.home = self.root / 'data' / 'editorial'
        self.home.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @contextlib.contextmanager
    def transaction(self):
        with self._lock:
            with (self.home / '.write.lock').open('a') as lockfile:
                try:
                    import fcntl
                    fcntl.flock(lockfile, fcntl.LOCK_EX)
                except ImportError:
                    fcntl = None
                try:
                    yield
                finally:
                    if fcntl is not None:
                        fcntl.flock(lockfile, fcntl.LOCK_UN)

    def mode_dir(self, mode: str) -> Path:
        if mode not in ('live', 'example'):
            raise ValueError('工作区只能是 live 或 example')
        return self.home / mode

    def brief_path(self, mode: Mode, bid: str) -> Path:
        return self.mode_dir(mode) / 'briefs' / f'{safe_id(bid)}.json'

    def get(self, mode: Mode, bid: str) -> Brief:
        d = json_read(self.brief_path(mode, bid))
        if d is None:
            raise FileNotFoundError('选题不存在')
        return Brief.model_validate(d)

    def list(self, mode: Mode) -> list[Brief]:
        return sorted([Brief.model_validate(json_read(p)) for p in (self.mode_dir(mode) / 'briefs').glob('*.json')], key=lambda b:b.updated_at, reverse=True)

    def create(self, brief: Brief) -> Brief:
        with self.transaction():
            if self.brief_path(brief.mode, brief.id).exists():
                raise ConflictError('选题已经存在')
            brief.audit.append({'at':now_iso(), 'action':'created', 'detail':'选题创建；尚未批准发布'})
            atomic_json(self.brief_path(brief.mode, brief.id), brief.model_dump(mode='json'))
        return brief

    def create_once(self, brief: Brief) -> tuple[Brief, bool]:
        # No recursive transaction: explicitly check and write under the same lock.
        with self.transaction():
            if brief.origin_key:
                for prev in self.list(brief.mode):
                    if prev.origin_key == brief.origin_key:
                        return prev, False
            brief.audit.append({'at':now_iso(), 'action':'created', 'detail':'从线索创建，不自动写全文'})
            atomic_json(self.brief_path(brief.mode, brief.id), brief.model_dump(mode='json'))
            return brief, True

    def mutate(self, mode: Mode, bid: str, expected: int, fn: Callable[[Brief], None], action: str) -> Brief:
        with self.transaction():
            b = self.get(mode, bid)
            if b.version != expected:
                raise ConflictError('记录已被其他页面或后台修改。请保留本地稿，再重新加载，不要覆盖新版本。')
            fn(b)
            b.version += 1
            b.updated_at = now_iso()
            b.audit.append({'at':b.updated_at, 'action':action})
            # Revalidate everything before the atomic write.
            b = Brief.model_validate(b.model_dump(mode='json'))
            atomic_json(self.brief_path(mode, bid), b.model_dump(mode='json'))
            return b

    def settings(self) -> Settings:
        return Settings.model_validate(json_read(self.home / 'settings.json', {}))

    def save_settings(self, settings: Settings):
        with self.transaction():
            atomic_json(self.home / 'settings.json', settings.model_dump(mode='json'))

    def policy(self) -> PolicyReview:
        return PolicyReview.model_validate(json_read(self.home / 'policy-review.json', {}))

    def save_policy(self, policy: PolicyReview):
        with self.transaction():
            atomic_json(self.home / 'policy-review.json', policy.model_dump(mode='json'))

    def subjects(self, mode: Mode) -> list[Subject]:
        return [Subject.model_validate(json_read(p)) for p in (self.mode_dir(mode) / 'subjects').glob('*.json')]

    def save_subject(self, mode: Mode, subject: Subject):
        with self.transaction():
            atomic_json(self.mode_dir(mode) / 'subjects' / f'{safe_id(subject.id)}.json', subject.model_dump(mode='json'))

    def latest(self, mode: str):
        if mode not in ('live','example','offline'):
            raise ValueError('无效运行模式')
        pointer = json_read(self.root / 'reports' / mode / 'latest.json', {})
        if not pointer:
            return None
        return json_read(self.root / 'reports' / mode / safe_id(pointer['run_id']) / 'run.json')

    def write_run(self, mode: str, run: dict):
        path = self.root / 'reports' / mode / safe_id(run['run_id']) / 'run.json'
        with self.transaction():
            atomic_json(path, run)
            atomic_json(path.parent.parent / 'latest.json', {'run_id':run['run_id'], 'at':now_iso()})


def fingerprint(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',',':')).encode()).hexdigest()
