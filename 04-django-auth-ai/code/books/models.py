from django.core.validators import MaxValueValidator
from django.db import models


class Book(models.Model):
    """도서 (F404) + AI 작가 정보 (F417 심화)"""

    # ---- 필수 4개 필드 (F404) ----
    title = models.CharField(max_length=100, verbose_name='제목')
    description = models.TextField(verbose_name='설명')
    # 회원 리뷰 평점 : 0 ~ 10 점 (음수 불가 => PositiveIntegerField, 상한은 Validator 로)
    customer_review_rank = models.PositiveIntegerField(
        validators=[MaxValueValidator(10)],
        help_text='0 ~ 10 사이의 정수를 입력하세요.',
        verbose_name='회원 리뷰 평점',
    )
    author = models.CharField(max_length=100, verbose_name='저자')

    # ---- AI 가 생성한 작가 정보 (F417) ----
    # 사용자가 입력하는 칸이 아니라 서버가 채우는 칸이므로 blank=True (폼에서도 제외)
    author_info = models.TextField(blank=True, verbose_name='작가 정보')
    # 대표작 목록 : 'Demian, Steppenwolf' 처럼 콤마로 이어 붙인 문자열
    author_works = models.TextField(blank=True, verbose_name='작가 대표작')
    # 위키피디아에서 찾은 작가 사진 주소
    author_image = models.URLField(max_length=500, blank=True, verbose_name='작가 사진 URL')

    # ---- 추가 기능 : AI 도서 분석 결과 ----
    # {'summary': ..., 'keywords': [...], 'target_readers': ..., 'reading_points': [...]}
    ai_analysis = models.JSONField(default=dict, blank=True, verbose_name='AI 도서 분석')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
