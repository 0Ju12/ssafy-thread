from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserChangeForm,
    UserCreationForm,
)

from mypjt.forms import BootstrapFormMixin

User = get_user_model()

# 회원가입 · 회원정보 수정 폼에서 함께 쓰는 한글 label
USER_FIELD_LABELS = {
    'username': '아이디',
    'email': '이메일',
    'last_name': '성',
    'first_name': '이름',
    'gender': '성별',
    'age': '나이',
    'weekly_avg_reading_time': '주간 평균 독서 시간(시간)',
    'annual_reading_amount': '연간 독서량(권)',
}

# 회원가입 · 회원정보 수정 폼에서 함께 쓰는 추가 정보 필드 목록 (F418)
PROFILE_FIELDS = [
    'email',
    'last_name',
    'first_name',
    'gender',
    'age',
    'weekly_avg_reading_time',
    'annual_reading_amount',
    'interested_genres',
]


class CustomAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    """로그인 폼 (F406)

    ※ AuthenticationForm 은 ModelForm 이 아니라 기본 User 에 묶여 있지 않으므로 그대로 써도 동작함
    ※ 여기서는 label 한글화 · Bootstrap 스타일만 입힘
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = '아이디'
        self.fields['password'].label = '비밀번호'
        self.apply_bootstrap()


class CustomUserCreationForm(BootstrapFormMixin, UserCreationForm):
    """회원가입 폼 (F403, F418)

    ※ 부모(UserCreationForm)의 Meta.model 은 기본 User 로 고정되어 있음
      => Meta 를 상속해 model 만 우리 User 로 교체 (교체하지 않으면 가입 시 'Manager isn't available' 에러)
    """

    # 관심 장르 : 모델에서는 문자열 칸이지만, 폼에서는 여러 개 고르는 칸으로 바꿔 끼움
    # 체크한 값들은 cleaned_data 에 리스트(['NOVEL', 'SCIENCE'])로 들어옴
    interested_genres = forms.MultipleChoiceField(
        choices=User.GENRE_CHOICES,
        required=False,
        label='관심 장르',
        widget=forms.CheckboxSelectMultiple,
    )

    # 화면에 그릴 칸의 순서 (password1 · password2 는 부모 폼에서 선언된 칸이라 순서를 따로 지정)
    field_order = ['username', 'password1', 'password2'] + PROFILE_FIELDS

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ['username'] + PROFILE_FIELDS
        labels = USER_FIELD_LABELS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # password1 · password2 는 모델 필드가 아니라 Meta.labels 로 바꿀 수 없음 => 생성자에서 재설정
        self.fields['password1'].label = '비밀번호'
        self.fields['password2'].label = '비밀번호 확인'
        self.apply_bootstrap()


class CustomUserChangeForm(BootstrapFormMixin, UserChangeForm):
    """회원정보 수정 폼 (F403, F409, F418)

    ※ 일반 사용자가 보면 안 되는 칸(is_superuser · is_staff · 비밀번호 해시 등)은 출력하지 않음
    """

    # 비밀번호는 비밀번호 변경 화면에서만 바꾸도록 수정 폼에서 칸을 없앰
    password = None

    # 회원가입 폼과 동일하게 관심 장르를 여러 개 고르는 칸으로
    interested_genres = forms.MultipleChoiceField(
        choices=User.GENRE_CHOICES,
        required=False,
        label='관심 장르',
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta(UserChangeForm.Meta):
        model = get_user_model()
        # fields 를 지정하지 않으면 is_superuser 같은 권한 칸까지 사용자에게 열림
        fields = PROFILE_FIELDS
        labels = USER_FIELD_LABELS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class CustomPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    """비밀번호 변경 폼 (F411)

    ※ PasswordChangeForm 은 ModelForm 이 아니므로 그대로 써도 됨 => label · 스타일만 변경
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = '현재 비밀번호'
        self.fields['new_password1'].label = '새 비밀번호'
        self.fields['new_password2'].label = '새 비밀번호 확인'
        self.apply_bootstrap()
