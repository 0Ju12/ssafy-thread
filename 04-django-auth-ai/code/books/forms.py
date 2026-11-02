from django import forms

from mypjt.forms import BootstrapFormMixin

from .models import Book


class BookForm(BootstrapFormMixin, forms.ModelForm):
    """도서 생성 · 수정 폼 (F405)

    ModelForm : 모델 필드 설정(max_length, validators 등)을 그대로 가져와 입력 칸 · 유효성 검사를 자동으로 만듦
    ※ author_info · author_works · author_image 는 AI 가 채우는 칸이므로 사용자 입력 칸에서 제외
    """

    class Meta:
        model = Book
        fields = ['title', 'description', 'customer_review_rank', 'author']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': '도서 제목'}),
            'description': forms.Textarea(attrs={'rows': 6, 'placeholder': '도서 설명'}),
            'customer_review_rank': forms.NumberInput(attrs={'min': 0, 'max': 10}),
            'author': forms.TextInput(attrs={'placeholder': '예) 헤르만 헤세'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
