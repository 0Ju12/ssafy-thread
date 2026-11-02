import csv
import json
import queue
import re
import threading

from django.db import close_old_connections
from django.db.models import Q
from django.http import Http404
from django.utils.safestring import mark_safe

from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .context_processors import DETAIL_LAYOUTS, DETAIL_TEMPLATES, ui_theme
from .forms import CompanyForm
from .models import CrawlResult
from .services.llm import LLMError
from .services.pipeline import run_pipeline
from .services.summary import summarize_comments
from .services.quality import assess_pair, highlight_difference
from .services.insights import make_insights, compare_result_data


def _get_company(request):
    """폼에서 회사명을 꺼낸다. 비어 있으면 '' (F601)"""
    form = CompanyForm(request.POST or None)
    if form.is_valid():
        return form.cleaned_data['company'], form
    return '', form


def _index_context(form=None, **extra):
    context = {
        'form': form or CompanyForm(),
        'recent_results': CrawlResult.objects.all()[:10],
    }
    context.update(extra)
    return context


@require_GET
def index(request):
    """회사명 입력 화면 + 최근 분석 이력; 시장 종목 링크에서 회사명 미리 입력."""
    company = request.GET.get('company', '')[:100].strip()
    return render(request, 'comments/index.html',
                  _index_context(CompanyForm(initial={'company': company})))


@require_POST
def run(request):
    """자바스크립트가 꺼져 있을 때 사용하는 일반 요청 버전 (진행 상황 없이 결과로 이동)"""
    company, form = _get_company(request)
    if not company:
        # F601 : 입력값이 없으면 데이터 수집 절차를 수행하지 않음 (화면만 그대로)
        return render(request, 'comments/index.html', _index_context(form))

    print(f'[입력] 회사명 : {company}')  # F601 : VS Code 터미널에 입력한 회사명 출력
    result = run_pipeline(company)
    obj = CrawlResult.create_from_pipeline(result)

    if not obj.is_ok:
        # F611 : 회사 없음 / 댓글 없음 / 오류 -> 입력 화면에 안내 메시지
        return render(request, 'comments/index.html',
                      _index_context(form, error_message=obj.message))
    return redirect('comments:detail', pk=obj.pk)


@require_POST
def run_stream(request):
    """크롤링 진행 상황을 한 줄씩(NDJSON) 흘려보내는 스트리밍 버전 (F603 선택)

    응답 한 줄 = JSON 하나
      {"type": "progress", "stage": "crawl", "message": "..."}
      {"type": "done", "url": "/results/3/"}               성공
      {"type": "fail", "message": "...", "status": "..."}  회사 없음 등 (F611)
    """
    company, _ = _get_company(request)
    if not company:
        return HttpResponse(status=204)  # F601 : 아무 동작도 하지 않음

    print(f'[입력] 회사명 : {company}')  # F601

    # 파이프라인은 별도 스레드에서 실행하고, 진행 메시지는 큐로 받아 즉시 응답에 씀
    messages = queue.Queue()
    outcome = {}

    def on_progress(stage, message):
        print(f'[{stage}] {message}')
        messages.put({'type': 'progress', 'stage': stage, 'message': message})

    def worker():
        # DB 저장은 스트리밍 제너레이터가 아니라 작업 스레드가 담당한다.
        # 사용자가 탭을 닫아도 해당 작업 스레드가 살아 있는 동안 저장을 시도한다.
        close_old_connections()
        try:
            data = run_pipeline(company, progress=on_progress)
            obj = CrawlResult.create_from_pipeline(data)
            outcome.update(pk=obj.pk, status=obj.status, message=obj.message)
            if obj.is_ok:
                on_progress('save', '결과를 DB에 저장했습니다')
        except Exception as e:
            # 파이프라인 예외도 실패 기록으로 남긴다 (오류 상세는 서버 로그에만 출력).
            print(f'[파이프라인 오류] {e.__class__.__name__}: {e}')
            try:
                obj = CrawlResult.objects.create(
                    query=company, status='error', message='분석 도중 오류가 발생했습니다.'
                )
                outcome.update(pk=obj.pk, status='error', message=obj.message)
            except Exception as db_error:
                print(f'[저장 오류] {db_error.__class__.__name__}: {db_error}')
                outcome.update(status='error', message='처리 중 오류가 발생했습니다.')
        finally:
            messages.put(None)
            close_old_connections()

    threading.Thread(target=worker, daemon=True, name='thread-crawl-worker').start()

    def line(data):
        return json.dumps(data, ensure_ascii=False) + '\n'

    def stream():
        yield line({'type': 'progress', 'stage': 'input', 'message': f"입력한 회사명 : '{company}'"})
        while True:
            item = messages.get()
            if item is None:
                break
            yield line(item)
        if outcome.get('status') == 'ok':
            yield line({'type': 'done', 'url': reverse('comments:detail', args=[outcome['pk']])})
        else:
            yield line({'type': 'fail', 'status': outcome.get('status', 'error'),
                        'message': outcome.get('message') or '분석 중 오류가 발생했습니다.'})

    response = StreamingHttpResponse(stream(), content_type='application/x-ndjson; charset=utf-8')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@require_GET
def detail(request, pk):
    """원본 / 전처리 / 증강 / 통합 결과 + 요약 화면 (F605 ~ F607, F610)"""
    obj = get_object_or_404(CrawlResult, pk=pk)
    # 화면 표시용 : 원본 댓글의 연속된 빈 줄은 한 줄로 (저장된 원본은 그대로)
    originals = [
        dict(item, text=re.sub(r'\n\s*\n+', '\n', item['text']))
        for item in (obj.records_by_stage('original') or [
            {'index': i, 'text': t, 'removed': False} for i, t in enumerate(obj.raw_comments)
        ])
    ]
    clean = obj.clean_comments
    augmented = obj.augmented_comments
    clean_records = obj.records_by_stage('clean')
    quality = obj.quality_checks or [dict(index=i, **assess_pair(a, b, stock_name=obj.stock_name)) for i, (a, b) in enumerate(zip(clean, augmented))]
    comparisons = []
    for i, (clean_text, aug_text) in enumerate(zip(clean, augmented)):
        source_index = clean_records[i].get('source_index') if i < len(clean_records) else None
        original = obj.raw_comments[source_index] if isinstance(source_index, int) and 0 <= source_index < len(obj.raw_comments) else None
        q = quality[i] if i < len(quality) else assess_pair(clean_text, aug_text, stock_name=obj.stock_name)
        comparisons.append({
            'number': i + 1, 'original': original, 'clean': clean_text,
            'augmented': aug_text, 'highlighted': mark_safe(highlight_difference(clean_text, aug_text)),
            'status': q.get('status', 'review'), 'issues': q.get('issues', []),
        })
    related = _related_results(obj)
    context = {
        'form': CompanyForm(initial={'company': obj.query}),
        'result': obj,
        'market_snapshot':obj.market_snapshot or {},
        'originals': originals,
        'pairs': list(zip(clean, augmented)) if augmented else [],
        'iqr': obj.iqr_info,
        'insights': make_insights(obj),
        'comparisons': comparisons,
        'related_results': related[:5],
        'stock_initial': (obj.stock_name or obj.query)[:2],
        'stage_labels': {'original': '원본', 'removed': '부적절 제거', 'clean': '전처리', 'augmented': '증강'},
    }
    # 테마에 따라 결과 화면 구조를 바꿈 (없으면 기본 detail.html)
    theme = ui_theme(request)['ui_theme']
    layout_name = DETAIL_TEMPLATES.get(theme, f'detail_{theme}.html')
    template = f'comments/{layout_name}' if theme in DETAIL_LAYOUTS else 'comments/detail.html' 
    return render(request, template, context)


@require_POST
def regenerate_summary(request, pk):
    """요약 버튼 : 요약을 다시 생성해 저장 (F610)"""
    obj = get_object_or_404(CrawlResult, pk=pk)
    try:
        obj.summary = summarize_comments(obj.stock_name, obj.raw_comments)
        obj.warnings = [w for w in obj.warnings if not w.startswith('요약')]
    except LLMError as e:
        obj.warnings = [w for w in obj.warnings if not w.startswith('요약')] + [f'요약을 생성하지 못했습니다: {e}']
    obj.save(update_fields=['summary', 'warnings'])
    return redirect(reverse('comments:detail', args=[pk]) + '#summary')


ALLOWED_EXPORT_STAGES = {'all', 'original', 'removed', 'clean', 'augmented'}


def _related_results(result):
    """동일 종목의 성공 분석만 비교: 종목 코드 우선, 과거 데이터는 명칭으로 보완."""
    condition = Q(stock_name=result.stock_name)
    if result.stock_code:
        # 코드가 있는 결과끼리는 코드 일치를 우선하며, 과거 코드 누락 기록만 이름으로 보완
        condition = Q(stock_code=result.stock_code) | Q(stock_code='', stock_name=result.stock_name)
    return list(CrawlResult.objects.filter(condition, status='ok').exclude(pk=result.pk)
                .order_by('-created_at', '-pk')[:50])


def _csv_safe(value):
    """Excel 등에서 CSV의 셀 값을 수식으로 실행하지 않게 보호."""
    value = str(value if value is not None else '')
    if value.lstrip('\t\r\n ').startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


@require_GET
def export_result(request, pk, fmt):
    """원본/제거/정제/증강 결과를 CSV 또는 JSON으로 다운로드."""
    obj = get_object_or_404(CrawlResult, pk=pk)
    if fmt not in ('csv', 'json'):
        raise Http404('지원하지 않는 파일 형식')
    stage = request.GET.get('stage', 'all')
    if stage not in ALLOWED_EXPORT_STAGES:
        raise Http404('지원하지 않는 단계')
    rows = [row for row in obj.records if stage == 'all' or row.get('stage') == stage]
    filename = f'thread_{re.sub(r"[^A-Za-z0-9_-]", "", obj.stock_code) or obj.pk}_{obj.created_at:%Y%m%d}_{stage}.{fmt}'
    if fmt == 'json':
        content = {
            'result_id': obj.pk, 'stock_name': obj.stock_name,
            'stock_code': obj.stock_code, 'query': obj.query,
            'created_at': obj.created_at.isoformat(), 'status': obj.status,
            'stage_filter': stage, 'records': rows,
            'quality_checks': obj.quality_checks,
            'iqr_info': obj.iqr_info,
        }
        res = HttpResponse(json.dumps(content, ensure_ascii=False, indent=2),
                           content_type='application/json; charset=utf-8')
    else:
        res = HttpResponse(content_type='text/csv; charset=utf-8')
        res.write('\ufeff')
        writer = csv.writer(res)
        writer.writerow(['단계', '번호', '텍스트', '원본 번호', '정제 원본 번호', '부적절 판정'])
        for row in rows:
            writer.writerow([row.get('stage'), row.get('index', 0) + 1,
                             _csv_safe(row.get('text', '')),
                             (row['source_index']+1) if isinstance(row.get('source_index'), int) else '',
                             (row['origin_index']+1) if isinstance(row.get('origin_index'), int) else '',
                             'Y' if row.get('removed') else ''])
    res['Content-Disposition'] = f'attachment; filename="{filename}"'
    res['X-Content-Type-Options'] = 'nosniff'
    return res


@require_GET
def compare_history(request, pk):
    """같은 종목의 두 저장된 분석 사이 댓글 수/추출 단어/원문 차이."""
    obj = get_object_or_404(CrawlResult, pk=pk, status='ok')
    related = _related_results(obj)
    selected_id = request.GET.get('other')
    previous = None
    if selected_id:
        previous = next((r for r in related if str(r.pk) == selected_id), None)
        if previous is None:
            raise Http404('동일 종목의 비교 가능한 기록이 없습니다.')
    elif related:
        previous = related[0]
    return render(request, 'comments/history_compare.html', {
        'form': CompanyForm(initial={'company': obj.query}),
        'result': obj,
        'market_snapshot':obj.market_snapshot or {}, 'previous': previous, 'related_results': related,
        'comparison': compare_result_data(obj, previous) if previous else None,
    })
