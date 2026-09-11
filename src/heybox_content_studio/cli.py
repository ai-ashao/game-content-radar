from __future__ import annotations
import argparse
import json
from pathlib import Path


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(prog='heybox-studio',description='盒友编辑台：本地选题、资料、审稿与运营')
    parser.add_argument('--root',default='.',help='项目 / 数据根目录')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('start','restart','serve','web'):
        p=sub.add_parser(name)
        p.add_argument('--port',type=int,default=8787)
        p.add_argument('--no-browser',action='store_true')
    for name in ('stop','status'):
        p=sub.add_parser(name); p.add_argument('--port',type=int,default=None)
    sub.add_parser('logs')
    update=sub.add_parser('update'); update.add_argument('--mode',choices=['live','example','offline'],default='live')
    sub.add_parser('seed')
    migrate=sub.add_parser('migrate'); migrate.add_argument('--from',dest='source',required=True); migrate.add_argument('--copy',action='store_true',help='默认为只读预览；此选项复制校验备份，不删除原文件')
    args=parser.parse_args(argv); root=Path(args.root).resolve()
    try:
        if args.command in ('serve','web'):
            import uvicorn
            from .webapp import create_app
            if not args.no_browser:
                import threading, webbrowser
                from .runtime import health, belongs
                def open_ready():
                    import time
                    for _ in range(80):
                        if belongs(health(args.port),root):
                            webbrowser.open(f'http://127.0.0.1:{args.port}'); return
                        time.sleep(.2)
                threading.Thread(target=open_ready,daemon=True).start()
            uvicorn.run(create_app(root),host='127.0.0.1',port=args.port,log_level='info',timeout_graceful_shutdown=8)
            return 0
        if args.command in ('start','stop','restart','status'):
            from .runtime import start,stop,health
            from .storage import json_read
            if args.command=='restart': stop(root,args.port)
            if args.command in ('start','restart'):
                result=start(root,args.port,not args.no_browser)
                print(f'盒友编辑台已就绪：http://127.0.0.1:{args.port}\n可以关闭此终端；服务仍在后台运行。')
            elif args.command=='stop': print(stop(root,args.port)['message'])
            else:
                port=args.port or json_read(root/'.heybox-runtime'/'server.json',{}).get('port',8787)
                print(json.dumps(health(port) or {'status':'disconnected'},ensure_ascii=False,indent=2))
        elif args.command=='logs':
            path=root/'logs'/'web.log'
            print(path.read_text(encoding='utf-8',errors='replace')[-16000:] if path.exists() else '尚无日志')
        elif args.command=='update':
            from .collection import collect_run
            from .storage import Store
            print(json.dumps(collect_run(Store(root),args.mode,print),ensure_ascii=False,indent=2))
        elif args.command=='seed':
            from .demo import create_seeds
            from .storage import Store
            print('已建立待研究题材：',len(create_seeds(Store(root))))
        elif args.command=='migrate':
            from .legacy import migrate
            print(json.dumps(migrate(Path(args.source),root,copy=args.copy),ensure_ascii=False,indent=2))
        return 0
    except (ValueError,RuntimeError,OSError) as exc:
        print('操作未完成：'+str(exc))
        return 1
