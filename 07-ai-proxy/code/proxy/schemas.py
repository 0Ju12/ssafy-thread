"""요청·응답 모양 — SSAFY 제공 원본 대신 공개용으로 필드만 맞춰 다시 쓴 최소 정의"""
from typing import Literal

from pydantic import BaseModel

Mode = Literal["spec", "sol"]          # spec = 기본 모델, sol = 선택형 상위 모델


class ChatRequest(BaseModel):
    model_mode: Mode = "spec"
    messages: list[dict]
    use_tier_routing: bool = False     # F710: 요청 난이도로 nano / mini 선택


class ChatResponse(BaseModel):
    content: str
    model_used: str = ""


class ChatGuardrailRequest(BaseModel):
    model_mode: Mode = "spec"
    prompt: str


class ChatGuardrailResponse(BaseModel):
    is_appropriate: bool


class DecideRouteRequest(BaseModel):
    model_mode: Mode = "spec"
    prompt: str


class DecideRouteResponse(BaseModel):
    route: str


class ImageGenerationRequest(BaseModel):
    model_mode: Mode = "spec"
    prompt: str


class ImageGenerationResponse(BaseModel):
    image_base64: str                  # JPEG base64


class ImageAnalysisRequest(BaseModel):
    model_mode: Mode = "spec"
    image_base64: str
    question: str


class ImageAnalysisResponse(BaseModel):
    content: str


class ChatScoreRequest(BaseModel):
    model_mode: Mode = "spec"
    messages: list[dict]
    answer: str


class ChatScoreResponse(BaseModel):
    score: int
    reason: str


class GenerateSpeechRequest(BaseModel):
    model_mode: Mode = "spec"
    text: str


class GenerateSpeechResponse(BaseModel):
    audio_data: str
