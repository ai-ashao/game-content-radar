from game_content_radar.collectors.steam import SteamStoreCollector


class FakeHTTP:
    def get_json(self, url, **kwargs):
        row = {"id": 10, "name": "Game X", "discount_percent": 50, "original_price": 10000, "final_price": 5000, "currency": "CNY"}
        return {
            "specials": {"items": [row]},
            "top_sellers": {"items": [{"id": 10, "name": "Game X"}]},
            "new_releases": {"items": []},
        }


def test_store_merges_bucket_signals_per_app():
    result = SteamStoreCollector(FakeHTTP()).collect()
    assert len(result.items) == 1
    item = result.items[0]
    assert item.category == "sale"
    assert item.metrics["top_seller"] is True
    assert set(item.metrics["buckets"]) == {"specials", "top_sellers"}
