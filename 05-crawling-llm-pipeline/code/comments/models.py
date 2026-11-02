from django.db import models


class CrawlResult(models.Model):
    """한 번의 요청(회사명 입력)에 대한 수집·전처리·증강 결과 (F602, F607)"""

    STATUS_CHOICES = [
        ('ok', '성공'),
        ('no_company', '회사 없음'),
        ('no_comments', '댓글 없음'),
        ('error', '오류'),
    ]

    # 입력
    query = models.CharField('입력한 회사명', max_length=100)
    # 실제종목명 : 검색 결과 최상단에서 실제로 매칭된 종목의 공식 명칭
    stock_name = models.CharField('실제종목명', max_length=100, blank=True)
    stock_code = models.CharField('종목 코드', max_length=30, blank=True)
    status = models.CharField('처리 상태', max_length=20, choices=STATUS_CHOICES, default='ok')
    message = models.CharField('안내 메시지', max_length=255, blank=True)

    # 단계별 결과 (리스트는 JSON 으로 저장)
    raw_comments = models.JSONField('원본 댓글 목록', default=list, blank=True)
    removed_comments = models.JSONField('부적절 판정 댓글 목록', default=list, blank=True)
    clean_comments = models.JSONField('정제 댓글 목록', default=list, blank=True)
    augmented_comments = models.JSONField('증강 댓글 목록', default=list, blank=True)

    # 전처리 기준 정보
    criteria = models.CharField('부적절 판단 기준', max_length=255, blank=True)
    iqr_info = models.JSONField('IQR 임계값 정보', default=dict, blank=True)
    clean_steps = models.JSONField('정제 단계 기록', default=list, blank=True)

    # 통합 결과 : 원본·제거·정제·증강을 stage 로 구분한 하나의 결과 집합 (F607)
    records = models.JSONField('통합 결과', default=list, blank=True)

    summary = models.TextField('댓글 요약', blank=True)  # F610
    warnings = models.JSONField('경고', default=list, blank=True)
    quality_checks = models.JSONField('증강 검증 결과', default=list, blank=True)
    market_snapshot = models.JSONField('동시 수집 시장·환율 스냅샷', default=dict, blank=True)

    created_at = models.DateTimeField('생성 일시', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.created_at:%Y-%m-%d %H:%M}] {self.query} -> {self.stock_name or "-"}'

    @property
    def is_ok(self):
        return self.status == 'ok'

    @classmethod
    def create_from_pipeline(cls, result):
        """run_pipeline() 의 결과 딕셔너리를 그대로 DB 에 저장한다"""
        return cls.objects.create(
            query=result['query'],
            stock_name=result['stock_name'],
            stock_code=result['stock_code'],
            status=result['status'],
            message=result['message'][:255],
            raw_comments=result['raw'],
            removed_comments=result['removed'],
            clean_comments=result['clean'],
            augmented_comments=result['augmented'],
            criteria=result['criteria'],
            iqr_info=result['iqr_info'],
            clean_steps=result['clean_steps'],
            records=result['records'],
            summary=result['summary'],
            warnings=result['warnings'],
            quality_checks=result.get('quality_checks', []),
            market_snapshot=result.get('market_snapshot', {}),
        )

    def records_by_stage(self, stage):
        return [r for r in self.records if r.get('stage') == stage]
