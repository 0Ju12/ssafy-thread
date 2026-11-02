from django import forms


class BootstrapFormMixin:
    """폼의 모든 칸에 Bootstrap 클래스를 붙여 주는 Mixin

    각 폼의 __init__ 에서 super().__init__() 다음에 self.apply_bootstrap() 을 호출
    ※ 칸마다 widget attrs 를 반복해서 적지 않기 위해 사용
    """

    def apply_bootstrap(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxSelectMultiple):
                # 체크박스 묶음은 attrs 가 바깥 <div> 에도 붙어 모양이 깨지므로 클래스를 붙이지 않음
                # (모양은 base.html 의 .checkbox-list CSS 로 지정)
                continue
            elif isinstance(widget, forms.Select):
                css_class = 'form-select'
            elif isinstance(widget, forms.CheckboxInput):
                css_class = 'form-check-input'
            else:
                css_class = 'form-control'
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = f'{existing} {css_class}'.strip()
