from __future__ import annotations
import re
from ..http import HttpClient
from ..models import now_iso

class SteamDetailsClient:
    def __init__(self, http: HttpClient):
        self.http = http

    def collect(self, appid: int, country: str='CN') -> dict:
        if appid <= 0: raise ValueError('AppID必须为正整数')
        data = self.http.get_json('https://store.steampowered.com/api/appdetails',params={'appids':appid,'cc':country,'l':'schinese'})
        row = data.get(str(appid),{})
        if not row.get('success'): raise ValueError('该地区没有可用游戏详情')
        d = row['data']
        price = d.get('price_overview') or {}
        return {'appid':appid,'name':d.get('name'),'store':'steam','region':country,'currency':price.get('currency'), 'sku':str(appid),'edition':d.get('name'), 'observed_at':now_iso(), 'end_at':None,'price_minor':price.get('final'), 'original_price_minor':price.get('initial'), 'discount_percent':price.get('discount_percent'), 'is_free':d.get('is_free'), 'offer_type':'f2p' if d.get('is_free') else 'paid', 'source_url':f'https://store.steampowered.com/app/{appid}/', 'description':re.sub('<[^>]+>', ' ', d.get('short_description','')), 'languages':re.sub('<[^>]+>', ' ', d.get('supported_languages','')), 'developers':d.get('developers',[]),'publishers':d.get('publishers',[]), 'categories':d.get('categories',[]), 'release_date':d.get('release_date',{}), 'screenshots':[r.get('path_full') for r in d.get('screenshots',[])[:6]], 'header_image':d.get('header_image'), 'historical_low_evidence':None}
