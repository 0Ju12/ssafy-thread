from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """커스텀 User (F402) + 추가 정보 필드 (F418 심화)

    AbstractUser 를 상속하므로 username · password · email · first_name · last_name 등
    기본 필드는 그대로 물려받고, 회원가입 시 받을 추가 정보만 더함
    """

    GENDER_CHOICES = [
        ('M', '남성'),
        ('F', '여성'),
    ]

    # 관심 장르 선택지 : (DB 에 저장될 코드, 화면에 보여 줄 이름)
    GENRE_CHOICES = [
        ('NOVEL', '소설/시/희곡'),
        ('ECONOMY', '경제/경영'),
        ('SELF', '자기계발'),
        ('HUMANITIES', '인문/교양'),
        ('SCIENCE', '과학'),
        ('HOBBY', '취미/실용'),
        ('KIDS', '어린이/청소년'),
    ]

    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        verbose_name='성별',
    )
    # 나이 · 주간 평균 독서 시간 · 연간 독서량 : 음수가 될 수 없으므로 PositiveIntegerField
    # 숫자 필드는 "입력하지 않음" 을 NULL 로 저장하기 위해 null=True + blank=True
    age = models.PositiveIntegerField(null=True, blank=True, verbose_name='나이')
    weekly_avg_reading_time = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='주간 평균 독서 시간(시간)'
    )
    annual_reading_amount = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='연간 독서량(권)'
    )
    # 관심 장르 : 여러 개를 'NOVEL,SCIENCE' 처럼 콤마로 이어 붙인 문자열 하나로 저장
    # ※ 모델 필드에 choices 를 걸지 않는 이유 : choices 는 값 하나만 허용하기 때문
    interested_genres = models.CharField(
        max_length=600,
        blank=True,
        verbose_name='관심 장르',
    )

    def get_genre_list(self):
        """'NOVEL,SCIENCE' -> ['NOVEL', 'SCIENCE']"""
        return self.interested_genres.split(',') if self.interested_genres else []

    def get_interested_genres_display(self):
        """'NOVEL,SCIENCE' -> '소설/시/희곡, 과학' (choices 필드의 get_FOO_display() 를 흉내 냄)"""
        labels = dict(self.GENRE_CHOICES)
        return ', '.join(labels.get(code, code) for code in self.get_genre_list())

    def get_full_name_korean(self):
        """한국식 이름 : 성 + 이름"""
        return f'{self.last_name}{self.first_name}'.strip()
