"""관통 7 · FastAPI 프록시 (공개본)

Django → 이 서버 → SSAFY GMS 순서로 호출합니다. GMS 키는 이 서버의 .env 에만 둡니다.

공개 범위
- 직접 구현한 부분(F702~F711: 추천 생성, Guardrail, 라우트 결정, 이미지 생성·정규화, 공통 오류 처리,
  이미지 분석, 점수, 난이도별 모델 선택, TTS)만 담았습니다.
- SSAFY 가 제공한 GMS 호출 함수(ask_gms)와 요청·응답 스키마 원본은 빼고, 같은 자리에
  공개용 대체 코드를 두었습니다(schemas.py, 아래 '제공 코드 자리').

실행: uvicorn main:app --port 8081   (이 폴더 안에서)  ·  문서: http://localhost:8081/docs
"""
import base64
import json
import os
import io
from PIL import Image, UnidentifiedImageError

import requests
from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException

from schemas import (
    ChatGuardrailRequest,
    ChatGuardrailResponse,
    ChatRequest,
    ChatResponse,
    ChatScoreRequest,
    ChatScoreResponse,
    DecideRouteRequest,
    DecideRouteResponse,
    GenerateSpeechRequest,
    GenerateSpeechResponse,
    ImageAnalysisRequest,
    ImageAnalysisResponse,
    ImageGenerationRequest,
    ImageGenerationResponse,
)

# .env가 설정돼 있으면 그 값을 우선하여 Windows의 오래된 환경변수로
# 엉뚱한 인증키를 전송하는 일을 방지합니다. 실제 키는 절대로 로그에 남기지 않습니다.
_ENV_VALUES = dotenv_values(os.path.join(os.path.dirname(__file__), ".env"))
def setting(name, default=None):
    value = _ENV_VALUES.get(name)
    if value is None or not str(value).strip():
        value = os.getenv(name, default)
    return str(value).strip().strip('"').strip("'") if value is not None else None

GMS_KEY = setting("GMS_KEY")
GMS_URL = setting("GMS_URL")
HEADERS = {"Authorization": f"Bearer {GMS_KEY}"}

MODEL_NANO = "gpt-5-nano"
MODEL_MINI = "gpt-5-mini"
MODEL_SOL = "gpt-6.1-sol"
# 이미지 모델은 GMS가 제공하는 실제 ID를 .env에서 변경할 수 있습니다.
MODEL_IMAGE = setting("IMAGE_MODEL", "gemini-3.1-flash-lite-image")
# GMS 제공 인터페이스에 따라 openai_images 또는 gemini_native를 선택합니다.
IMAGE_API_STYLE = setting("IMAGE_API_STYLE", "gemini_native").strip().lower()
IMAGE_API_PATH = setting("IMAGE_API_PATH", "").strip()
# Gemini는 OpenAI 도메인으로 보내지 않습니다. 실제 GMS 제공 주소는 운영 환경에서 확인하세요.
GMS_GEMINI_URL = setting(
    "GMS_GEMINI_URL",
    "https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta",
).rstrip("/")

# F711 TTS 모델
MODEL_TTS = "gpt-4o-mini-tts"

app = FastAPI(title="Book Recommend Proxy (FastAPI)")


# ######################################################################
# 제공 코드 자리 — SSAFY 가 준 GMS 호출 함수(Chat Completions / Responses API 변환)는
# 공개하지 않습니다. 테스트는 이 함수를 mock 으로 바꿔 끼워 실행합니다.
# ######################################################################

def ask_gms(messages, model=MODEL_NANO, response_format=None):
    """messages 를 GMS 에 보내 응답 텍스트(str)를 돌려주는 함수 — 원본은 SSAFY 제공 코드라 공개본에서 제외"""
    raise HTTPException(503, "model server error")


def selected_model(mode):
    return MODEL_SOL if mode == "sol" else MODEL_NANO


# ######################################################################
# 직접 구현 — 요구사항 번호 순서 (F702~F711)
# ######################################################################

# ---------------------------------------------------------------- F702 텍스트 추천 생성 (+F703, F710)
@app.post("/api/v1/chat/completions", response_model=ChatResponse)
def chat_completions(request: ChatRequest):
    if not request.messages or not isinstance(request.messages[-1].get("content"), str):
        raise HTTPException(422, "invalid messages")
    user_text = request.messages[-1]["content"]
    ensure_appropriate(user_text, request.model_mode)
    model = selected_model(request.model_mode)
    if request.use_tier_routing and request.model_mode == "spec":
        tier = decide_model_tier(user_text)
        model = MODEL_MINI if tier == "complex" else MODEL_NANO
    content = ask_gms(request.messages, model)
    return {"content": content, "model_used": model}



# ---------------------------------------------------------------- F703 Guardrail
GUARDRAIL_PROMPT = """도서 서비스 안전성 분류기. 명백하게 폭력·자해·혐오·성인 콘텐츠를 요구하거나 불법행위 실행 방법, 타인 개인정보를 요청할 때만 false. 문학 작품 속 주제 언급, 예방/교육/분석, 모호한 요청은 true. JSON 스키마에 맞게 답하라."""

def structured_schema(name, properties):
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}}}

def structured_answer(messages, name, properties, model=MODEL_NANO):
    try:
        data = json.loads(ask_gms(messages, model, structured_schema(name, properties)))
        if not isinstance(data, dict) or any(k not in data for k in properties):
            raise ValueError("missing fields")
        return data
    except (ValueError, TypeError, KeyError) as exc:
        print("[GMS 응답 형식 오류]", type(exc).__name__)
        raise HTTPException(503, "model server error") from exc

@app.post("/api/v1/chat/guardrail", response_model=ChatGuardrailResponse)
def chat_guardrail(request: ChatGuardrailRequest):
    data = structured_answer([{"role":"developer","content":GUARDRAIL_PROMPT},{"role":"user","content":request.prompt}], "guardrail_response", {"is_appropriate":{"type":"boolean"}}, selected_model(request.model_mode))
    if type(data["is_appropriate"]) is not bool:
        raise HTTPException(503, "model server error")
    return data

def ensure_appropriate(prompt, model_mode="spec"):
    if not chat_guardrail(ChatGuardrailRequest(prompt=prompt, model_mode=model_mode))["is_appropriate"]:
        raise HTTPException(403, "inappropriate request")



# ---------------------------------------------------------------- F704 라우트 결정
ROUTE_PROMPT = """사용자 의도가 책 추천/텍스트 설명이면 /chat/completions, 책 표지 이미지를 그리거나 생성하라는 요청이면 /images/generations. 반드시 지정된 route 중 하나만 선택하라."""

@app.post("/api/v1/decide-route", response_model=DecideRouteResponse)
def decide_route(request: DecideRouteRequest):
    data = structured_answer([{"role":"developer","content":ROUTE_PROMPT},{"role":"user","content":request.prompt}], "route_response", {"route":{"type":"string","enum":["/chat/completions","/images/generations"]}}, selected_model(request.model_mode))
    if data["route"] not in ("/chat/completions", "/images/generations"):
        raise HTTPException(503, "model server error")
    return data



# ---------------------------------------------------------------- F705 이미지 생성 (+F703)
def normalize_image_as_jpeg(encoded):
    """Gemini PNG/WEBP 및 OpenAI JPEG를 실제 JPEG base64로 통일(F705/F712)."""
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 20 * 1024 * 1024:
            raise ValueError("image too large")
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.width * image.height > 25_000_000:
                raise ValueError("pixel count limit")
            if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
                rgb = Image.new("RGB", image.size, "white")
                rgb.paste(image.convert("RGBA"), mask=image.convert("RGBA").getchannel("A"))
            else:
                rgb = image.convert("RGB")
            output = io.BytesIO()
            rgb.save(output, "JPEG", quality=88, optimize=True)
            return base64.b64encode(output.getvalue()).decode("ascii")
    except (ValueError, TypeError, OSError, UnidentifiedImageError, base64.binascii.Error) as exc:
        print("[이미지 변환 실패]", type(exc).__name__)
        raise HTTPException(503, "model server error") from exc


def extract_generated_image(body):
    """OpenAI b64_json, Gemini inlineData/inline_data 모두 처리합니다."""
    if not isinstance(body, dict):
        raise HTTPException(503, "model server error")
    data = body.get("data")
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and isinstance(entry.get("b64_json"), str):
                return normalize_image_as_jpeg(entry["b64_json"])
    # Gemini Interactions API의 현재 응답 형식: output_image 또는
    # steps[].content[].{type:image,data:...}. 기존 candidates도 지원합니다.
    output_image = body.get("output_image")
    if isinstance(output_image, dict) and isinstance(output_image.get("data"), str):
        return normalize_image_as_jpeg(output_image["data"])
    for step in body.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        for part in step.get("content", []) or []:
            if isinstance(part, dict) and part.get("type") == "image" and isinstance(part.get("data"), str):
                return normalize_image_as_jpeg(part["data"])
    for part in body.get("outputs", []) or []:
        if isinstance(part, dict) and part.get("type") == "image" and isinstance(part.get("data"), str):
            return normalize_image_as_jpeg(part["data"])
    candidates = body.get("candidates", [])
    if isinstance(candidates, list):
        for candidate in candidates:
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data") or {}
                if isinstance(inline, dict) and isinstance(inline.get("data"), str):
                    return normalize_image_as_jpeg(inline["data"])
    print("[이미지 응답 형식 오류] 생성된 이미지가 없습니다. 모델/응답 형식을 확인하세요.")
    raise HTTPException(503, "model server error")


def describe_gms_response(value, depth=0):
    """GMS 응답을 안전하게 진단합니다. 값 대신 키와 자료형만 출력합니다."""
    if depth >= 6:
        return "(하위 구조 생략)"
    if isinstance(value, dict):
        # 키도 API가 반환하는 임의 문자열일 수 있으므로 허용된 키만 사용합니다.
        safe_keys = {
            "id", "status", "type", "model", "output", "outputs", "steps",
            "content", "parts", "candidates", "data", "b64_json",
            "output_image", "inlineData", "inline_data", "mimeType", "mime_type",
            "result", "response", "image", "images", "uri", "url", "error",
            "code", "message", "detail", "text", "finishReason", "finish_reason",
        }
        result = {}
        for key, item in value.items():
            if key in safe_keys:
                if key in {"status", "type", "finishReason", "finish_reason"} and isinstance(item, str):
                    result[key] = item[:60] if len(item) <= 60 else "문자열"
                else:
                    result[key] = describe_gms_response(item, depth + 1)
        result["_field_count"] = len(value)
        return result
    if isinstance(value, list):
        return {"_list_length": len(value), "_sample": [describe_gms_response(v, depth + 1) for v in value[:2]]}
    if isinstance(value, str):
        return f"문자열 ({len(value)}자; 내용 미출력)"
    return type(value).__name__


@app.post("/api/v1/images/generations", response_model=ImageGenerationResponse)
def image_generations(request: ImageGenerationRequest):
    ensure_appropriate(request.prompt, request.model_mode)
    if IMAGE_API_STYLE == "gemini_native":
        path = IMAGE_API_PATH or "/interactions"
        payload = {
            "model": MODEL_IMAGE,
            "input": [{"type": "text", "text": request.prompt}],
        }
        gemini_headers = {
            "x-goog-api-key": GMS_KEY,
            "Content-Type": "application/json",
        }
        response = gms_post(path, payload, base_url=GMS_GEMINI_URL, headers=gemini_headers)
    elif IMAGE_API_STYLE == "openai_images":
        path = IMAGE_API_PATH or "/images/generations"
        payload = {"model": MODEL_IMAGE, "prompt": request.prompt, "size": "1024x1024"}
        response = gms_post(path, payload)
    else:
        print("[이미지 설정 오류] IMAGE_API_STYLE 값:", IMAGE_API_STYLE)
        raise HTTPException(503, "model server error")
    try:
        body = response.json()
    except (ValueError, TypeError) as exc:
        print("[GMS 이미지 응답 오류] JSON 형식이 아닙니다.")
        raise HTTPException(503, "model server error") from exc

    # Gemini Interactions 응답의 형태만 출력합니다.
    # 원본 텍스트, base64, 파일 URL 및 인증 정보는 출력하지 않습니다.
    print("[GMS 이미지 응답 구조]", json.dumps(
        describe_gms_response(body), ensure_ascii=False
    ))
    return {"image_base64": extract_generated_image(body)}


# ---------------------------------------------------------------- F706 공통 에러 처리
def gms_post(path, payload, base_url=None, headers=None):
    if not GMS_KEY or not GMS_URL or GMS_KEY.startswith("여기에_"):
        print("[GMS 설정 오류] GMS_KEY 및 GMS_URL을 확인하세요.")
        raise HTTPException(503, "model server error")
    url = (base_url or GMS_URL).rstrip("/") + path
    request_headers = headers or HEADERS
    try:
        response = requests.post(url, headers=request_headers, json=payload, timeout=120)
    except requests.RequestException as exc:
        print("[GMS 연결 실패]", path, type(exc).__name__)
        raise HTTPException(503, "model server error") from exc
    if response.status_code != 200:
        # 응답 본문에는 민감정보가 포함될 수 있으므로 키/요청을 출력하지 않습니다.
        if response.status_code == 401 and "generativelanguage.googleapis.com" in url:
            print("[Gemini 인증 거부/401] x-goog-api-key 헤더 전송 설정 사용,"
                  " GMS에서 키를 해당 도메인에 인식하는지 확인 필요."
                  " .env 키를 확인하고 서버를 완전히 재시작하세요.")
        else:
            print("[GMS 호출 실패]", url.split('/gmsapi/')[-1], response.status_code, response.text[:250])
        raise HTTPException(503, "model server error")
    return response


# ---------------------------------------------------------------- F707 이미지 분석 (+F703)
ANALYSIS_PROMPT = """업로드한 책 표지를 보고 제목·장르를 추정하고 유사한 도서 2~3권을 추천하라. 표지만으로 확실하지 않은 제목이나 저자는 추정이라고 표시하고 허위 확신을 피하라. 한국어로 답하라."""

@app.post("/api/v1/images/analysis", response_model=ImageAnalysisResponse)
def image_analysis(request: ImageAnalysisRequest):
    ensure_appropriate(request.question, request.model_mode)
    # JPEG/PNG/GIF/WEBP signatures determine the data URI media type.
    try:
        image_bytes = base64.b64decode(request.image_base64, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise HTTPException(422, "invalid image") from exc
    if image_bytes.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif image_bytes.startswith((b"GIF87a", b"GIF89a")):
        mime = "image/gif"
    elif image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise HTTPException(422, "unsupported image format")
    image_url = f"data:{mime};base64," + request.image_base64
    messages = [{"role":"developer","content":ANALYSIS_PROMPT},{"role":"user","content":[{"type":"image_url","image_url":{"url":image_url}},{"type":"text","text":request.question}]}]
    return {"content":ask_gms(messages, selected_model(request.model_mode))}



# ---------------------------------------------------------------- F709 텍스트 응답 점수 계산 (심화)
SCORE_PROMPT = """사용자 취향 요청과 AI 추천 답변의 부합도를 0~100 정수로 평가하라. 선호 장르, 분위기, 제약, 이유의 구체성을 고려한다. reason은 한국어 한두 문장으로 작성한다."""

@app.post("/api/v1/chat/score", response_model=ChatScoreResponse)
def chat_score(request: ChatScoreRequest):
    messages = [{"role":"developer","content":SCORE_PROMPT}] + request.messages + [{"role":"user","content":"답변: " + request.answer}]
    data = structured_answer(messages,"score_response",{"score":{"type":"integer"},"reason":{"type":"string"}},selected_model(request.model_mode))
    if type(data["score"]) is not int or not 0 <= data["score"] <= 100 or not isinstance(data["reason"],str):
        raise HTTPException(503,"model server error")
    return data



# ---------------------------------------------------------------- F710 모델 등급 라우팅 (심화)
TIER_PROMPT = """책 추천 요청의 난이도를 판단하라. 조건 하나의 단순 요청은 simple, 여러 조건·감정·상황을 종합해야 하면 complex로 분류하라."""

def decide_model_tier(prompt):
    data = structured_answer([{"role":"developer","content":TIER_PROMPT},{"role":"user","content":prompt}],"tier_response",{"tier":{"type":"string","enum":["simple","complex"]}})
    if data["tier"] not in ("simple", "complex"):
        raise HTTPException(503, "model server error")
    return data["tier"]



# ---------------------------------------------------------------- F711 TTS (심화)
@app.post("/api/v1/generate-speech", response_model=GenerateSpeechResponse)
def generate_speech(request: GenerateSpeechRequest):
    ensure_appropriate(request.text, request.model_mode)
    response = gms_post("/audio/speech", {"model":MODEL_TTS,"input":request.text,"voice":"nova","response_format":"mp3"})
    return {"audio_data":base64.b64encode(response.content).decode("utf-8")}
