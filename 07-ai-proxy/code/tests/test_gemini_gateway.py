"""Offline tests to prevent regression to OpenAI domain and PNG-as-JPG."""
import base64
import importlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'proxy'))
proxy = importlib.import_module('main')
client = TestClient(proxy.app)


class MockResponse:
    def __init__(self, payload):
        self.payload = payload
    def json(self):
        return self.payload


def png_base64():
    stream = io.BytesIO()
    Image.new('RGBA', (12, 12), (20, 30, 40, 100)).save(stream, format='PNG')
    return base64.b64encode(stream.getvalue()).decode('ascii')


class GeminiGatewayTests(unittest.TestCase):
    def test_png_to_real_jpeg(self):
        transformed = proxy.extract_generated_image({'candidates':[{'content':{'parts':[{'inlineData':{'data':png_base64(), 'mimeType':'image/png'}}]}}]})
        image_bytes = base64.b64decode(transformed)
        self.assertTrue(image_bytes.startswith(b'\xff\xd8\xff'))
        with Image.open(io.BytesIO(image_bytes)) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertEqual(image.size, (12, 12))

    def test_gemini_uses_separate_gateway(self):
        with patch.object(proxy, 'ensure_appropriate'), patch.object(proxy, 'IMAGE_API_STYLE', 'gemini_native'), patch.object(proxy, 'gms_post', return_value=MockResponse({'candidates':[{'content':{'parts':[{'inlineData':{'data':png_base64()}}]}}]})) as call:
            resp = client.post('/api/v1/images/generations', json={'prompt': '동화 표지'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(call.call_args.kwargs['base_url'], proxy.GMS_GEMINI_URL)
        self.assertNotIn('api.openai.com', call.call_args.kwargs['base_url'])
        self.assertEqual(call.call_args.kwargs['headers']['x-goog-api-key'], proxy.GMS_KEY)
        self.assertEqual(call.call_args.args[1]['model'], proxy.MODEL_IMAGE)
        self.assertEqual(call.call_args.args[1]['input'][0]['type'], 'text')
        self.assertEqual(call.call_args.args[0], '/interactions')

    def test_missing_image_returns_503(self):
        with patch.object(proxy, 'ensure_appropriate'), patch.object(proxy, 'IMAGE_API_STYLE', 'gemini_native'), patch.object(proxy, 'gms_post', return_value=MockResponse({'candidates': []})):
            response = client.post('/api/v1/images/generations', json={'prompt': '표지'})
        self.assertEqual(response.status_code, 503)

    def test_openai_compatibility_retained(self):
        with patch.object(proxy, 'ensure_appropriate'), patch.object(proxy, 'IMAGE_API_STYLE', 'openai_images'), patch.object(proxy, 'gms_post', return_value=MockResponse({'data':[{'b64_json':png_base64()}]})) as call:
            response = client.post('/api/v1/images/generations', json={'prompt': '표지'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('base_url', call.call_args.kwargs)

if __name__=='__main__': unittest.main()

class GeminiAuthAndInteractionTests(unittest.TestCase):
    def test_interaction_output_image(self):
        converted = proxy.extract_generated_image({'output_image':{'type':'image','data':png_base64()}})
        self.assertTrue(base64.b64decode(converted).startswith(b'\xff\xd8\xff'))

    def test_interaction_steps(self):
        data={'steps':[{'type':'model_output','content':[{'type':'image','data':png_base64()}]}]}
        converted=proxy.extract_generated_image(data)
        self.assertTrue(base64.b64decode(converted).startswith(b'\xff\xd8\xff'))

    def test_gemini_auth_headers_actual_requests_post(self):
        from fastapi import HTTPException
        with patch.object(proxy, 'GMS_KEY', 'TEST_KEY'), patch.object(proxy, 'GMS_URL', 'https://gms.ssafy.io/gmsapi/api.openai.com/v1'), patch.object(proxy.requests, 'post', return_value=type('R', (), {'status_code': 200})()) as post:
            proxy.gms_post('/interactions', {'model':'gemini-3.1-flash-lite-image','input':[]}, base_url='https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta', headers={'x-goog-api-key':'TEST_KEY','Content-Type':'application/json'})
            self.assertEqual(post.call_args.kwargs['headers']['x-goog-api-key'], 'TEST_KEY')
            self.assertEqual(post.call_args.kwargs['timeout'], 120)
            self.assertTrue(post.call_args.args[0].endswith('/v1beta/interactions'))

    def test_gemini_401_becomes_safe_503(self):
        from fastapi import HTTPException
        response=type('R', (), {'status_code':401, 'text':'GMS key not found in request for domain generativelanguage.googleapis.com'})()
        with patch.object(proxy, 'GMS_KEY', 'TEST_KEY'), patch.object(proxy.requests, 'post', return_value=response):
            with self.assertRaises(HTTPException) as caught:
                proxy.gms_post('/interactions', {}, base_url=proxy.GMS_GEMINI_URL, headers={'x-goog-api-key':'TEST_KEY'})
            self.assertEqual(caught.exception.status_code, 503)
