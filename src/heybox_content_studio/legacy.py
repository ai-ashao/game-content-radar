from __future__ import annotations
import hashlib
import os
import re
import shutil
from pathlib import Path
from .models import now_iso, uid
from .storage import atomic_json, json_read


def inventory(root: Path) -> list[dict]:
    root=root.resolve(); paths=[]
    reports=root/'reports'
    if reports.is_dir():
        for folder in reports.iterdir():
            if folder.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}',folder.name):
                paths.extend(p for p in folder.rglob('*') if p.is_file())
    data=root/'data'
    if data.is_dir():
        paths += [p for p in data.iterdir() if p.is_file() and (p.suffix in ('.db','.sqlite','.sqlite3') or p.name.endswith(('.db-wal','.db-shm')))]
    rows=[]
    for p in sorted(set(paths)):
        if p.is_symlink() or not p.resolve().is_relative_to(root) or p.stat().st_size > 250_000_000: continue
        with p.open('rb') as f:
            digest=hashlib.file_digest(f,'sha256').hexdigest()
        rows.append({'path':str(p.relative_to(root)),'size':p.stat().st_size,'sha256':digest})
    return rows


def migrate(source: Path,target: Path, *, copy: bool=False) -> dict:
    source=source.resolve(); target=target.resolve()
    if not source.exists(): raise ValueError('旧项目目录不存在')
    records=inventory(source)
    manifest={'source_root':str(source),'created_at':now_iso(),'copied':False,'files':records,
              'note':'旧报告、编辑稿与玩家数据库只读保留，不转换为已审核新稿；未删除原文件。'}
    if not copy: return manifest
    # Require the old launcher process to be stopped before copying SQLite files.
    pidfile=source/'.game-content-radar-web.pid'
    if pidfile.exists():
        try:
            pid=int(pidfile.read_text().strip()); os.kill(pid,0)
        except (ValueError,ProcessLookupError,FileNotFoundError): pass
        except PermissionError: raise ValueError('无法确认旧服务是否退出，请先停止旧服务')
        else: raise ValueError('旧服务仍在运行；请先用旧项目stop-web.command停止，再备份迁移')
    archive=target/'legacy'/('snapshot-'+uid())
    for record in records:
        src=source/record['path']; dest=archive/record['path']; dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dest)
        with dest.open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=record['sha256']:
                raise ValueError('备份期间文件发生改变，已停止；原文件未更改')
        record['archived_path']=str(dest.relative_to(target))
    manifest['copied']=True; manifest['archive_dir']=str(archive.relative_to(target))
    atomic_json(archive/'manifest.json',manifest)
    old=json_read(target/'legacy'/'manifest.json',{'archives':[]})
    old['archives'].append(str((archive/'manifest.json').relative_to(target)))
    atomic_json(target/'legacy'/'manifest.json',old)
    return manifest


def available_archives(root: Path) -> list[dict]:
    rows=[]
    for r in inventory(root):
        rows.append({**r,'download_path':r['path'],'origin':'原项目目录（只读）'})
    for manifest_path in (root/'legacy').glob('snapshot-*/manifest.json'):
        for row in json_read(manifest_path,{}).get('files',[]):
            if row.get('archived_path'):
                rows.append({**row,'download_path':row['archived_path'],'origin':'校验备份'})
    return rows
