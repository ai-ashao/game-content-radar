from __future__ import annotations

import contextlib
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from . import SERVICE_ID
from .storage import atomic_json, json_read


def instance_id(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:24]


def health(port: int) -> dict|None:
    try:
        # System proxy settings must not intercept loopback readiness probes.
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'http://127.0.0.1:{port}/api/health',timeout=1) as response:
            return json.loads(response.read(500000))
    except Exception:
        return None


def belongs(info: dict|None, root: Path, pid: int|None=None) -> bool:
    return bool(info and info.get('service')==SERVICE_ID and info.get('instance')==instance_id(root) and (pid is None or info.get('pid')==pid))


def port_busy(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(.4)
        return sock.connect_ex(('127.0.0.1',port))==0

@contextlib.contextmanager
def process_lock(root: Path):
    directory=root/'.heybox-runtime'; directory.mkdir(parents=True,exist_ok=True)
    with (directory/'control.lock').open('a') as file:
        try:
            import fcntl
            fcntl.flock(file,fcntl.LOCK_EX)
        except ImportError:
            fcntl=None
        try: yield
        finally:
            if fcntl is not None: fcntl.flock(file,fcntl.LOCK_UN)


def start(root: Path,port: int=8787,open_browser: bool=True) -> dict:
    root=root.resolve()
    if not 1024<=port<=65535: raise ValueError('端口须在1024–65535范围')
    with process_lock(root):
        info=health(port)
        if info:
            if not belongs(info,root):
                raise RuntimeError(f'端口{port}被其他服务或其他项目目录占用；不会终止它。请先停止旧版本，或指定其他端口。')
            result=info
        else:
            if port_busy(port):
                raise RuntimeError(f'端口{port}已占用且不是可识别编辑台；不会按端口杀进程。')
            logdir=root/'logs'; logdir.mkdir(parents=True,exist_ok=True)
            with (logdir/'web.log').open('ab',buffering=0) as log:
                args=[sys.executable,'-m','heybox_content_studio','--root',str(root),'serve','--port',str(port),'--no-browser']
                kwargs={'cwd':root,'stdin':subprocess.DEVNULL,'stdout':log,'stderr':subprocess.STDOUT,'close_fds':True}
                if os.name=='posix': kwargs['start_new_session']=True
                else: kwargs['creationflags']=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS
                proc=subprocess.Popen(args,**kwargs)
            info=None
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError('编辑台未能启动；请双击查看日志，检查依赖和Python版本。')
                info=health(port)
                if belongs(info,root,proc.pid): break
                time.sleep(.15)
            else:
                # This is the process just created by this function, not a looked-up PID.
                proc.terminate()
                raise RuntimeError('启动后健康检查超时，请查看 logs/web.log')
            atomic_json(root/'.heybox-runtime'/'server.json',{'pid':proc.pid,'port':port,'instance':instance_id(root),'service':SERVICE_ID})
            result=info
    if open_browser: webbrowser.open(f'http://127.0.0.1:{port}')
    return result


def stop(root: Path,port: int|None=None):
    root=root.resolve()
    with process_lock(root):
        path=root/'.heybox-runtime'/'server.json'; record=json_read(path,{})
        use_port=port or record.get('port',8787)
        info=health(use_port)
        if info and not belongs(info,root):
            raise RuntimeError('该端口不是本项目实例，拒绝停止')
        if not info:
            if port_busy(use_port): raise RuntimeError('端口被占用但身份无法核对，拒绝按PID或端口误杀')
            path.unlink(missing_ok=True)
            return {'stopped':False,'message':'本项目服务未运行'}
        if record and info.get('pid')!=record.get('pid'):
            raise RuntimeError('PID与实例记录不一致，拒绝停止；请检查前台服务')
        pid=int(info['pid'])
        if pid==os.getpid() or pid<=1: raise RuntimeError('不允许终止该进程')
        os.kill(pid,signal.SIGTERM)
        for _ in range(50):
            if not belongs(health(use_port),root,pid):
                path.unlink(missing_ok=True)
                return {'stopped':True,'message':'本项目服务已停止'}
            time.sleep(.15)
        raise RuntimeError('服务正在退出，未使用强制杀进程；请稍后重试')
