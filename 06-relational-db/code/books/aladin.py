"""Aladin TTB books search adapter: network errors never prevent manual Book creation."""
import os
import requests

API_URL = "https://www.aladin.co.kr/ttb/api/ItemSearch.aspx"

class AladinError(Exception):
    pass

def search_books(keyword, max_results=10):
    key = os.getenv("ALADIN_TTBKEY", "").strip()
    if not key:
        raise AladinError("알라딘 TTB API 키가 설정되지 않았습니다. .env에 ALADIN_TTBKEY를 등록하세요.")
    keyword = keyword.strip()
    if not keyword or len(keyword) > 100:
        raise AladinError("검색어는 1~100자 사이로 입력해 주세요.")
    try:
        response = requests.get(API_URL, params={
            "TTBKey": key, "Query": keyword, "QueryType": "Keyword",
            "MaxResults": max(1, min(int(max_results), 20)), "Start": 1,
            "SearchTarget": "Book", "Cover": "Big", "output": "js",
            "Version": "20131101",
        }, timeout=8)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise AladinError("알라딘 서버 연결 또는 응답 해석에 실패했습니다.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("item", []), list):
        raise AladinError("알라딘 API 응답 형식이 올바르지 않습니다.")
    results = []
    for item in data.get("item", []):
        if not isinstance(item, dict):
            continue
        results.append({
            "title": str(item.get("title") or "")[:200],
            "author": str(item.get("author") or "")[:120],
            "description": str(item.get("description") or ""),
            "cover": str(item.get("cover") or ""),
            "publisher": str(item.get("publisher") or ""),
            "isbn13": str(item.get("isbn13") or ""),
            "pub_date": str(item.get("pubDate") or ""),
            "price": item.get("priceStandard"),
        })
    return results
