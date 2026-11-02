from django import forms


class CompanyForm(forms.Form):
    """회사명 입력 폼 (F601) : 일부 문자열('삼성')도 입력 가능"""

    company = forms.CharField(
        label='회사명',
        max_length=50,
        required=False,  # 빈 값은 "오류"가 아니라 "아무 동작 안 함"으로 처리 (뷰에서 판단)
        strip=True,
        widget=forms.TextInput(attrs={
            'placeholder': '회사명을 입력하세요 (예: 삼성, 카카오)',
            'autocomplete': 'off',
            'autofocus': True,
        }),
    )
