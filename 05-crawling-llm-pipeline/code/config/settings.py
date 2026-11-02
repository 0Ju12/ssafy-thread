"""
Django settings for config project. (05-pjt : 토스증권 댓글 크롤링 · 전처리 · 증강)

Django 5.x / 6.x 모두에서 동작하도록 작성
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# .env (GMS_KEY, GMS_BASE_URL, MODEL ...) 를 환경 변수로 불러옴
load_dotenv(BASE_DIR / '.env')


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/stable/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-only-change-me")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "comments",
    "market",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "comments.context_processors.ui_theme",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/stable/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/stable/topics/i18n/

LANGUAGE_CODE = "ko-kr"

TIME_ZONE = "Asia/Seoul"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/stable/howto/static-files/

STATIC_URL = "static/"

# 기본 PK 타입을 명시 (Django 5.x 와 6.x 의 기본값이 달라 마이그레이션이 어긋나지 않도록)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ------------------------------------------------------------
# 댓글 수집·가공 파이프라인 설정 (.env 로 바꿀 수 있음)
# ------------------------------------------------------------
# 수집할 댓글 수 (F604 : 20개)
COMMENT_LIMIT = int(os.getenv('COMMENT_LIMIT', '20'))

# 1 이면 크롬 창 없이(headless) 크롤링. 진행 과정을 눈으로 보려면 0
CRAWLER_HEADLESS = os.getenv('CRAWLER_HEADLESS', '1') == '1'

# 1 이면 토스증권에 접속하지 않고 data/comments_sample.json 으로 진행 (개발·테스트용)
USE_SAMPLE_DATA = os.getenv('USE_SAMPLE_DATA', '0') == '1'
SAMPLE_DATA_PATH = BASE_DIR / 'data' / 'comments_sample.json'

# 부적절 댓글 판단 기준 : 'basic' 또는 'strict'
FILTER_CRITERIA = os.getenv('FILTER_CRITERIA', 'basic')

# 길이 필터 (F605 : 5 이상 ~ 76 이하)
#   clamp : IQR 로 계산한 정상 범위를 5~76 안으로 제한 (기본값)
#   fixed : 5~76 고정 (IQR 값은 계산해서 기록만 함)
LENGTH_MIN = 5
LENGTH_MAX = 76
LENGTH_FILTER_MODE = os.getenv('LENGTH_FILTER_MODE', 'clamp')

# 화면 디자인 테마 (.env 의 UI_THEME 로 선택)
#   clean : A 클린 증권 (기본)      board : B 시세 전광판      proof : C 교정지
#   chat  : D 커뮤니티 대화형       desk  : E 분석 워크스페이스  story : F 카드뉴스 스토리
#   aurora : G 오로라 AI            atelier: H 아틀리에 리서치   brutal: I 네오 브루탈
#   glass  : J 소프트 글래스        console: K 터미널 프로
UI_THEME = os.getenv('UI_THEME', 'clean')
# 1 이면 화면 우하단 디자인 선택 메뉴 표시 (?theme=board 로 미리 보기). 기본은 표시
SHOW_THEME_SWITCHER = os.getenv('SHOW_THEME_SWITCHER', '1') == '1'

# 공개 토스증권 웹 화면 Selenium 수집 (인증키 불필요)
MARKET_SAMPLE_MODE = os.getenv('MARKET_SAMPLE_MODE', '0') == '1'
MARKET_CACHE_SECONDS = int(os.getenv('MARKET_CACHE_SECONDS', '600'))
