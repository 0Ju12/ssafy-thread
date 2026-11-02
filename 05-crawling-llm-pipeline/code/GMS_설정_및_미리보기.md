# ThRead — GMS 모델 설정 및 11종 테마 미리보기

## 1. GMS 응답 모델 변경

`comments/services/llm.py`에서 OpenAI Python SDK `client.responses.create()`를 사용하며, 이는 요청하신 `POST https://gms.ssafy.io/gmsapi/api.openai.com/v1/responses`와 동일한 방식입니다. 인증은 `GMS_KEY` 환경변수에서 읽어 Bearer 헤더로 전송합니다.

`manage.py`와 같은 폴더에 `.env` 파일을 만들어 다음을 입력하세요. **실제 키를 코드나 Git에 넣지 마세요.**

```env
GMS_KEY=YOUR_OWN_GMS_KEY
GMS_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1
MODEL=gpt-6.1-sol
UI_THEME=clean
SHOW_THEME_SWITCHER=1
```

- 기존 부적절 댓글 판정 / 증강 / 요약 3종 기능 모두 동일한 `run_llm()`을 사용하므로 모델이 동시에 변경됩니다.
- 응답이 늦는 상황을 고려하여 타임아웃 180초, 재시도 2회를 설정했습니다.
- `gpt-6.1-sol`의 실제 사용 권한·모델 사용 가능 여부는 사용자 GMS 계정으로 실행해야만 확인할 수 있습니다.
- 외부 API를 실행하지 않은 오프라인 미리보기는 실제 모델 출력이 아니라 데모 데이터입니다.

## 2. 실행 방법

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py test comments
python manage.py runserver
```

브라우저에서 `http://127.0.0.1:8000/`에 접속하세요. 우하단 `✦ 디자인 선택`에서 11개 테마를 즉시 바꿀 수 있습니다. 원하는 테마를 `.env`의 `UI_THEME`에 지정하고 서버를 재시작해도 됩니다.

## 3. 테마 미리보기

`theme_previews/gallery.html`을 브라우저로 열면 11개 테마의 홈·결과 화면 미리보기를 한꺼번에 비교할 수 있습니다. `theme_previews/`의 PNG는 *실제 GMS·Django 서버 출력이 아닌 동일 CSS를 Chromium에서 렌더링한 데모 화면*입니다.

기존 기능 로직, DB 스키마, URL은 수정하지 않았습니다.
