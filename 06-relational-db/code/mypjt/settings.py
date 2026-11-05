from pathlib import Path
import os
BASE_DIR=Path(__file__).resolve().parent.parent
# Local .env support, without overriding environment variables or requiring extra packages.
env_file=BASE_DIR/'.env'
if env_file.is_file():
    for raw in env_file.read_text(encoding='utf-8-sig').splitlines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key,value=line.split('=',1)
        key=key.strip();value=value.strip().strip('"').strip("'")
        if key and key.isidentifier():
            os.environ.setdefault(key,value)
SECRET_KEY=os.environ.get('DJANGO_SECRET_KEY','development-only-change-this-key-before-production')
DEBUG=os.environ.get('DJANGO_DEBUG','1')=='1'
ALLOWED_HOSTS=os.environ.get('DJANGO_ALLOWED_HOSTS','127.0.0.1,localhost').split(',')
INSTALLED_APPS=['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','accounts.apps.AccountsConfig','books.apps.BooksConfig']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF='mypjt.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.debug','django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='mypjt.wsgi.application'
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
AUTH_USER_MODEL='accounts.User'
LANGUAGE_CODE='ko-kr';TIME_ZONE='Asia/Seoul';USE_I18N=True;USE_TZ=True
STATIC_URL='static/';STATICFILES_DIRS=[BASE_DIR/'static'];MEDIA_URL='media/';MEDIA_ROOT=BASE_DIR/'media'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField';LOGIN_URL='accounts:login';LOGIN_REDIRECT_URL='books:index'
