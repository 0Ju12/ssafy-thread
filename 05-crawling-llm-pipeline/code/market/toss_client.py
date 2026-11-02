"""토스증권의 읽기 전용 Open API 클라이언트.

토큰 발급과 공개 시세 API만 사용합니다. 계좌/주문 API는 구현하지 않습니다.
참고: https://developers.tossinvest.com/docs
"""
import logging
import re
import time
from threading import Lock

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)
ROOT = 'https://openapi.tossinvest.com'
CODE = re.compile(r'^[0-9A-Za-z]{6}$')
TOKEN_LOCK = Lock()


class TossAPIError(RuntimeError):
    pass


def configured():
    return bool(getattr(settings, 'TOSS_CLIENT_ID', '').strip() and
                getattr(settings, 'TOSS_CLIENT_SECRET', '').strip())


class TossClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()

    def token(self, force=False):
        if not configured():
            raise TossAPIError('토스증권 Open API client_id/client_secret이 설정되지 않았습니다.')
        key = 'thread:toss:v1:oauth:token'
        if not force:
            token = cache.get(key)
            if token:
                return token
        with TOKEN_LOCK:
            if not force:
                token = cache.get(key)
                if token:
                    return token
            try:
                response = self.session.post(
                    ROOT + '/oauth2/token',
                    data={'grant_type': 'client_credentials',
                          'client_id': settings.TOSS_CLIENT_ID,
                          'client_secret': settings.TOSS_CLIENT_SECRET},
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=(4, 12),
                )
                response.raise_for_status()
                body = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise TossAPIError('토스증권 OAuth 토큰 발급 실패: 인증키·허용 IP를 확인하세요.') from exc
            if not isinstance(body, dict) or not body.get('access_token'):
                raise TossAPIError('토스증권 토큰 응답 형식이 올바르지 않습니다.')
            token = body['access_token']
            ttl = max(30, int(body.get('expires_in', 3600)) - 120)
            cache.set(key, token, timeout=ttl)
            return token

    def get(self, path, params=None):
        # path는 코드에 정의된 정적 경로만 사용. 임의 외부 URL을 허용하지 않음.
        if not path.startswith('/api/v1/') or '://' in path:
            raise ValueError('허용되지 않은 API 경로')
        retry_auth = False
        for attempt in range(3):
            token = self.token(force=retry_auth)
            retry_auth = False
            try:
                response = self.session.get(ROOT + path,
                    params=params or {}, headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
                    timeout=(4, 12))
                if response.status_code == 401 and attempt == 0:
                    cache.delete('thread:toss:v1:oauth:token')
                    retry_auth = True
                    continue
                if response.status_code == 429 and attempt < 2:
                    try:
                        delay = min(2, max(0.25, float(response.headers.get('Retry-After', '1'))))
                    except ValueError:
                        delay = 1
                    time.sleep(delay)
                    continue
                if response.status_code == 403:
                    raise TossAPIError('토스증권 API 접근 차단(403): 허용 IP 등록을 확인하세요.')
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or 'result' not in body:
                    raise TossAPIError('토스증권 API 응답에 result가 없습니다.')
                return body['result']
            except requests.RequestException as exc:
                logger.warning('토스증권 읽기 요청 실패: %s (%s)', path, type(exc).__name__)
                raise TossAPIError('토스증권 시세 조회 실패: 네트워크·API 이용 상태를 확인하세요.') from exc
            except (ValueError, TypeError) as exc:
                raise TossAPIError('토스증권 API JSON 응답 오류') from exc
        raise TossAPIError('토스증권 API 호출 한도 초과 또는 재인증 실패')


def code_ok(code):
    return bool(CODE.fullmatch(str(code)))
