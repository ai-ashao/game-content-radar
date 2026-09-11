#!/usr/bin/env python3
"""Browser QA against a disposable workspace, never the user's data.

Normal mode tests actual HTTP navigation and browser localStorage.
--bridge is an explicitly labelled renderer/API harness for environments whose
managed browser disallows localhost navigation. It does not test native origins.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile

import requests
from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--bridge', action='store_true')
    parser.add_argument('--chromium', default=None, help='Optional Chromium executable')
    parser.add_argument('--output', default='qa/browser')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PYTHONPATH': str(project / 'src')}
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    errors: list[str] = []
    report = {'mode': 'renderer-api-bridge' if args.bridge else 'native-browser-http',
              'native_storage_tested': False, 'native_mode_requested': not args.bridge, 'status': 'not_run'}
    with tempfile.TemporaryDirectory(prefix='heybox-browser-qa-') as directory:
        cmd = [sys.executable, '-m', 'heybox_content_studio', '--root', directory]
        def control(action: str):
            argv = cmd + [action, '--port', str(port)]
            if action == 'start':
                argv += ['--no-browser']
            subprocess.run(argv, env=env, capture_output=True, text=True, check=True)
        control('start')
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=args.chromium, headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1050})
                page.on('pageerror', lambda error: errors.append(str(error)))
                if args.bridge:
                    session = requests.Session()
                    session.trust_env = False
                    def transport(payload):
                        path = payload['path']
                        if not path.startswith('/api/') or '\\' in path:
                            return {'status': 400, 'body': '{}'}
                        try:
                            res = session.request(payload.get('method', 'GET'),
                                f'http://127.0.0.1:{port}' + path,
                                headers=payload.get('headers', {}),
                                data=payload.get('body'), timeout=28)
                            return {'status': res.status_code, 'body': res.text}
                        except requests.RequestException:
                            return {'network_error': True}
                    page.expose_function('heyboxTestFetch', transport)
                    assets = project / 'src' / 'heybox_content_studio' / 'web_ui'
                    html = re.sub(r'<link[^>]+>|<script[^>]*></script>', '',
                                  (assets / 'index.html').read_text(encoding='utf-8'))
                    page.set_content(html)
                    page.add_style_tag(content=(assets / 'style.css').read_text(encoding='utf-8'))
                    page.evaluate('''() => {
                        const cache = new Map();
                        Object.defineProperty(window, 'localStorage', {value: {
                            setItem:(k,v)=>cache.set(k,v), getItem:k=>cache.get(k)||null,
                            removeItem:k=>cache.delete(k)}});
                        window.fetch = async (path, options={}) => {
                            const result = await window.heyboxTestFetch({path,
                                method:options.method||'GET', headers:options.headers||{},
                                body:options.body||null});
                            if(result.network_error) throw new TypeError('QA: connection interrupted');
                            return new Response(result.body,{status:result.status,
                                headers:{'Content-Type':'application/json'}});
                        };
                    }''')
                    page.add_script_tag(content=(assets / 'app.js').read_text(encoding='utf-8'))
                else:
                    page.goto(f'http://127.0.0.1:{port}', wait_until='domcontentloaded')
                page.get_by_text('服务正常', exact=True).wait_for()
                page.screenshot(path=str(output / '01-empty-desktop.png'), full_page=True)
                page.locator('[data-view=settings]').click()
                page.locator('[data-action=example]').click()
                page.locator('#navCount').filter(has_text='3').wait_for(timeout=15000)
                page.locator('[data-view=dashboard]').click()
                page.wait_for_timeout(200)
                page.screenshot(path=str(output / '02-example-desktop.png'), full_page=True)
                page.locator('[data-view=topics]').click()
                page.locator('#topicSearch').fill('不靠任务')
                assert page.locator('#topicsTable .topic-title').count() == 1
                page.locator('#topicsTable .topic-title').first.click()
                page.locator('[data-tab=draft]').click()
                page.screenshot(path=str(output / '03-draft-editor.png'), full_page=True)
                page.locator('[data-action=preview]').click()
                page.locator('.citation').first.click()
                assert page.locator('#modalTitle').inner_text() == '主张与来源定位'
                page.locator('#closeModal').click()
                page.locator('#draftBody').fill(page.locator('#draftBody').input_value() + '\n\n缓存回连测试。')
                assert '尚未保存' in page.locator('#editorSaveStatus').inner_text()
                control('stop')
                page.get_by_text('服务已断开', exact=True).wait_for(timeout=15000)
                assert '缓存回连测试' in page.locator('#draftBody').input_value()
                page.screenshot(path=str(output / '05-disconnected-editor.png'), full_page=True)
                control('start')
                page.get_by_text('服务正常', exact=True).wait_for(timeout=15000)
                assert '缓存回连测试' in page.locator('#draftBody').input_value()
                page.locator('[data-action=save-draft]').click()
                page.locator('#revisionSelect option[value="2"]').wait_for(state='attached', timeout=15000)
                assert page.locator('#revisionSelect option').count() >= 3
                page.locator('#closeEditor').click()
                page.set_viewport_size({'width':390, 'height':844})
                page.locator('[data-view=dashboard]').click()
                page.screenshot(path=str(output / '04-mobile.png'), full_page=True)
                assert not page.locator('html').evaluate('(element) => element.scrollWidth > window.innerWidth')
                assert not errors, errors
                report.update(status='passed', native_storage_tested=not args.bridge, page_errors=errors, checks=[
                    'empty UI', 'example isolation', 'topic search', 'draft editor',
                    'Markdown preview', 'claim source reference', 'unsaved edit cache',
                    'actual server stop', 'disconnected indicator', 'actual server restart',
                    'reconnect keeps editing', 'persist new revision', '390px no overflow'])
                browser.close()
        except Exception as exc:
            report.update(status='failed', error=str(exc), page_errors=errors)
            raise
        finally:
            try:
                control('stop')
            finally:
                (output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
