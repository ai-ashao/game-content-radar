from __future__ import annotations
import threading
import traceback
from pathlib import Path
from .models import uid, now_iso
from .storage import atomic_json, json_read, safe_id, ConflictError

class Jobs:
    def __init__(self,root: Path):
        self.directory=root/'data'/'editorial'/'jobs'
        self.lock=threading.Lock(); self.active_id=None
        # Never retry partially finished external operations silently after a restart.
        for p in self.directory.glob('*.json'):
            row=json_read(p,{})
            if row.get('status') in ('running','queued'):
                row.update(status='interrupted',message='本地服务曾重启。已保存的资料保留，请人工决定是否重新运行。',finished_at=now_iso())
                atomic_json(p,row)

    def get(self,jid):
        job=json_read(self.directory/f'{safe_id(jid)}.json')
        if not job: raise FileNotFoundError('任务不存在')
        return job

    def active(self):
        return self.get(self.active_id) if self.active_id else None

    def start(self,label,callback):
        with self.lock:
            if self.active_id: raise ConflictError('已有任务在运行，不能重复提交')
            jid=uid(); self.active_id=jid
            job={'id':jid,'label':label,'status':'queued','message':'等待开始','created_at':now_iso()}
            atomic_json(self.directory/f'{jid}.json',job)
        def progress(message):
            with self.lock:
                row=self.get(jid); row.update(status='running',message=message)
                atomic_json(self.directory/f'{jid}.json',row)
        def runner():
            try:
                progress(label)
                result=callback(progress)
                status='done'; message='任务已完成'
            except Exception as exc:
                result=None; status='error'; message=str(exc)[:2000]
            with self.lock:
                row=self.get(jid); row.update(status=status,message=message,result=result,finished_at=now_iso())
                atomic_json(self.directory/f'{jid}.json',row); self.active_id=None
        threading.Thread(target=runner,daemon=True).start()
        return job
