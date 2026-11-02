"""GMS 연결 확인 명령 : python manage.py gms_ping

아래 curl 과 같은 요청을 보내고 응답을 출력함
    curl "https://gms.ssafy.io/gmsapi/api.openai.com/v1/responses" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $GMS_KEY" \
      -d '{"model": "<GMS_MODEL>", "input": "Hello, World!"}'
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from books.ai import AIError, ping


class Command(BaseCommand):
    help = 'GMS Responses API 에 "Hello, World!" 를 보내 키 · 모델 설정을 확인합니다.'

    def handle(self, *args, **options):
        self.stdout.write(f'POST {settings.GMS_BASE_URL}/responses')
        self.stdout.write(f'model = {settings.GMS_MODEL}')
        self.stdout.write(f'GMS_KEY = {"설정됨" if settings.GMS_KEY else "없음 (.env 확인)"}')
        try:
            answer = ping()
        except AIError as error:
            raise CommandError(str(error))
        self.stdout.write(self.style.SUCCESS('응답 :'))
        self.stdout.write(answer)
