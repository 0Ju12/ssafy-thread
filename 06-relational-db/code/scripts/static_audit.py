"""Django 미설치 환경에서도 수행 가능한 최소 프로젝트 정적 검사."""
import ast
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
files = list(ROOT.rglob('*.py'))
for file in files:
    ast.parse(file.read_text(encoding='utf-8-sig'), filename=str(file))
assert (ROOT/'mypjt/settings.py').exists()
assert (ROOT/'accounts/models.py').exists()
assert (ROOT/'books/models.py').exists()
assert (ROOT/'accounts/migrations/0001_initial.py').exists()
assert (ROOT/'accounts/migrations/0002_favorite_categories.py').exists()
assert (ROOT/'books/migrations/0001_initial.py').exists()
urls={}
for app in ('books','accounts'):
    text=(ROOT/app/'urls.py').read_text(encoding='utf-8')
    urls[app]=set(re.findall(r"name=['\"]([^'\"]+)['\"]",text))
for template in (ROOT/'templates').rglob('*.html'):
    body=template.read_text(encoding='utf-8')
    for app,name in re.findall(r"{%\s*url\s+['\"](books|accounts):([^'\"]+)['\"]",body):
        assert name in urls[app],f'Missing URL {app}:{name} in {template}'
assert 'AUTH_USER_MODEL=\'accounts.User\'' in (ROOT/'mypjt/settings.py').read_text(encoding='utf-8')
print(f'PASS: {len(files)} Python files AST, app configuration, migrations, template URL names')
