"""Offline proxy contract tests (no real GMS requests)."""
import base64
import importlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'proxy'))
proxy = importlib.import_module('main')
client = TestClient(proxy.app)


class FakeResponse:
    def __init__(self, data=None, content=b'ID3testing'):
        self.data = data
        self.content = content

    def json(self):
        return self.data


class ProxyContractTests(unittest.TestCase):
    def test_guardrail_true_false(self):
        for value in (True, False):
            with self.subTest(value=value), patch.object(proxy, 'ask_gms', return_value=json.dumps({'is_appropriate': value})):
                response = client.post('/api/v1/chat/guardrail', json={'prompt': 'sample'})
                self.assertEqual(response.status_code, 200)
                self.assertIs(response.json()['is_appropriate'], value)

    def test_guardrail_fail_closed(self):
        with patch.object(proxy, 'ask_gms', side_effect=Exception('should not happen')):
            pass
        with patch.object(proxy, 'ask_gms', return_value='broken'):
            response = client.post('/api/v1/chat/completions', json={'messages': [{'role':'user','content':'안녕'}]})
            self.assertEqual(response.status_code, 503)

    def test_rejection_prevents_generation(self):
        with patch.object(proxy, 'ask_gms', return_value='{"is_appropriate":false}') as mock_gms:
            response = client.post('/api/v1/images/generations',json={'prompt':'bad'})
            self.assertEqual(response.status_code,403)
            self.assertEqual(mock_gms.call_count,1)

    def test_routes(self):
        for route in ('/chat/completions','/images/generations'):
            with patch.object(proxy, 'ask_gms', return_value=json.dumps({'route':route})):
                response = client.post('/api/v1/decide-route',json={'prompt':'책'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['route'],route)

    def test_text_recommendation(self):
        with patch.object(proxy, 'ask_gms', side_effect=['{"is_appropriate":true}', '추천 도서']):
            response = client.post('/api/v1/chat/completions',json={'messages':[{'role':'user','content':'소설 추천'}]})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['model_used'],'gpt-5-nano')

    def test_spec_tier_routes_models(self):
        with patch.object(proxy, 'ask_gms', side_effect=['{"is_appropriate":true}', '{"tier":"complex"}', '추천 결과']) as calls:
            response = client.post('/api/v1/chat/completions', json={
                'messages': [{'role': 'user', 'content': '비오는 날에 읽을 위로 소설'}],
                'model_mode': 'spec', 'use_tier_routing': True,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['model_used'], 'gpt-5-mini')
            self.assertEqual(calls.call_args.args[1], 'gpt-5-mini')

    def test_optional_sol_mode(self):
        with patch.object(proxy, 'ask_gms', side_effect=['{"is_appropriate":true}', '추천 결과']):
            response = client.post('/api/v1/chat/completions', json={
                'messages': [{'role': 'user', 'content': '책 추천'}], 'model_mode': 'sol',
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['model_used'], 'gpt-6.1-sol')

    def test_malformed_text_response_becomes_503(self):
        with patch.object(proxy, 'gms_post', return_value=FakeResponse({'unexpected':42})):
            response = client.post('/api/v1/chat/completions',json={'messages':[{'role':'user','content':'안녕'}]})
            self.assertEqual(response.status_code,503)

    def test_score(self):
        with patch.object(proxy, 'ask_gms', return_value='{"score":87,"reason":"적합합니다"}'):
            response=client.post('/api/v1/chat/score',json={'messages':[{'role':'user','content':'에세이'}],'answer':'책 추천'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['score'],87)

    def test_image_mime(self):
        sample=base64.b64encode(b'\xff\xd8\xffjpegdata').decode()
        with patch.object(proxy,'ask_gms',side_effect=['{"is_appropriate":true}','분석 결과']) as mock_gms:
            response=client.post('/api/v1/images/analysis',json={'question':'책 표지 분석','image_base64':sample})
            self.assertEqual(response.status_code,200)
            self.assertTrue(mock_gms.call_args.args[0][1]['content'][0]['image_url']['url'].startswith('data:image/jpeg;base64,'))

    def test_image_bad_base64(self):
        with patch.object(proxy,'ask_gms',return_value='{"is_appropriate":true}'):
            response=client.post('/api/v1/images/analysis',json={'question':'책','image_base64':'???'})
            self.assertEqual(response.status_code,422)

    def test_speech(self):
        with patch.object(proxy,'ask_gms',return_value='{"is_appropriate":true}'), patch.object(proxy,'gms_post',return_value=FakeResponse(content=b'ID3hello')):
            response=client.post('/api/v1/generate-speech',json={'text':'안녕하세요'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(base64.b64decode(response.json()['audio_data']),b'ID3hello')


if __name__ == '__main__': unittest.main()
