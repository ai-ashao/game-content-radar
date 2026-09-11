from __future__ import annotations

import ipaddress
import socket
import time
from urllib.parse import urlsplit, urljoin
import requests

class FetchError(RuntimeError):
    def __init__(self, message: str, status: str = 'failed'):
        self.status = status
        super().__init__(message)

class HttpClient:
    """Bounded public GET client; disallows private network / local file targets.

    Redirects are explicitly revalidated. Trusted fixed provider URLs are used for
    collectors. This local tool is NOT intended as a public general-purpose proxy.
    """
    def __init__(self, timeout: int = 10, user_agent: str = 'heybox-content-studio/2.0 (+local-editorial-research)', max_requests: int = 40):
        self.timeout = timeout
        self.remaining = max_requests
        self.session = requests.Session()
        self.session.headers.update({'User-Agent':user_agent,'Accept-Language':'zh-CN,zh;q=0.9,en;q=0.8'})

    @staticmethod
    def validate_url(url: str):
        p = urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):
            raise FetchError('只允许常规端口的公开HTTP/HTTPS来源', 'needs_access')
        try:
            addresses = {x[4][0] for x in socket.getaddrinfo(p.hostname, p.port or 443, type=socket.SOCK_STREAM)}
        except OSError as e:
            raise FetchError('来源域名无法解析：'+p.hostname) from e
        if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
            raise FetchError('不允许请求本机、私有网络或元数据服务', 'needs_access')

    def _get(self, url: str, **kwargs):
        for redirect in range(4):
            self.validate_url(url)
            for attempt in range(2):
                if self.remaining <= 0:
                    raise FetchError('本轮请求预算已用完', 'partial')
                self.remaining -= 1
                try:
                    response = self.session.get(url, timeout=self.timeout, allow_redirects=False, stream=True, **kwargs)
                    if response.status_code == 429:
                        response.close()
                        raise FetchError('来源限流(429)，本轮停止重试', 'rate_limited')
                    if response.status_code in (401,403):
                        response.close()
                        raise FetchError('来源需要权限或拒绝访问', 'needs_access')
                    if response.is_redirect:
                        next_url = urljoin(url, response.headers['Location'])
                        response.close()
                        url = next_url
                        kwargs.pop('params', None)
                        break
                    response.raise_for_status()
                    parts, size = [], 0
                    for part in response.iter_content(65536):
                        size += len(part)
                        if size > 4_000_000:
                            response.close()
                            raise FetchError('来源响应超出4MB预算', 'partial')
                        parts.append(part)
                    content = b''.join(parts)
                    encoding = response.encoding or 'utf-8'
                    response.close()
                    return content, encoding
                except FetchError:
                    raise
                except requests.RequestException as exc:
                    if attempt == 1:
                        raise FetchError('网络请求失败：'+str(exc)[:250]) from exc
                    time.sleep(.5)
            else:
                continue
        raise FetchError('重定向过多')

    def get_json(self, url: str, **kwargs):
        import json
        content, _ = self._get(url,**kwargs)
        return json.loads(content)

    def get_text(self, url: str, **kwargs) -> str:
        content, encoding = self._get(url,**kwargs)
        return content.decode('utf-8' if encoding.lower()=='iso-8859-1' else encoding, errors='replace')

    def close(self):
        self.session.close()
