from __future__ import annotations

from ..http import HttpClient
from ..models import now_iso
from ..validation import rating_percent

class SteamReviewsClient:
    """Query-summary is not a /10 rating or a one-page sample average.

    Reference: https://partner.steamgames.com/doc/store/getreviews
    day_range only controls helpful-review selection; no '30-day overall ratio'.
    """
    def __init__(self, http: HttpClient):
        self.http = http

    def collect(self, appid: int, language: str = 'all', purchase_type: str = 'steam', include_samples: bool = True) -> dict:
        if appid <= 0 or purchase_type not in ('steam','all','non_steam_purchase'):
            raise ValueError('无效AppID或购买口径')
        params = {'json':1,'filter':'all','language':language, 'day_range':365, 'cursor':'*', 'review_type':'all','purchase_type':purchase_type, 'num_per_page':5,'filter_offtopic_activity':1}
        url = f'https://store.steampowered.com/appreviews/{appid}'
        raw = self.http.get_json(url,params=params)
        if raw.get('success') != 1 or not isinstance(raw.get('query_summary'),dict):
            raise ValueError('Steam评论接口没有返回可用统计')
        q = raw['query_summary']
        positive, negative, total = (int(q[x]) for x in ('total_positive','total_negative','total_reviews'))
        ratio = rating_percent(positive,negative,total)
        result = {'platform':'steam','appid':appid,'scope':'matching_query_summary', 'observed_at':now_iso(), 'positive':positive,'negative':negative,'total_reviews':total, 'recommended_percent':ratio,'review_score_desc':q.get('review_score_desc'), 'filters':params,'source_url':url, 'samples':[], 'warnings':[]}
        if include_samples:
            # A maximum of 3 requests. User identities / profile details are discarded.
            for sentiment in ('positive','negative'):
                try:
                    subset = {**params,'review_type':sentiment,'num_per_page':3}
                    rr = self.http.get_json(url,params=subset)
                    for r in rr.get('reviews',[])[:3]:
                        result['samples'].append({'sentiment':sentiment,'excerpt':str(r.get('review',''))[:600],'created_at':r.get('timestamp_created'), 'source_url':url, 'sample_only':True})
                except Exception as exc:
                    result['warnings'].append('评价样本未完整获取：'+str(exc))
        return result
