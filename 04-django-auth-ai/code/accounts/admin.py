from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


# UserAdmin : 비밀번호 해시 · 권한 설정 등 기본 회원 관리 화면을 그대로 사용
# ※ admin.site.register(User) 만 하면 비밀번호가 일반 글자 칸이 되어 해시 없이 저장됨
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # 관리자 화면에서 추가 정보(F418)도 보고 수정할 수 있도록 칸을 더함
    fieldsets = UserAdmin.fieldsets + (
        (
            '추가 정보',
            {
                'fields': (
                    'gender',
                    'age',
                    'weekly_avg_reading_time',
                    'annual_reading_amount',
                    'interested_genres',
                )
            },
        ),
    )
    list_display = ('username', 'email', 'last_name', 'first_name', 'is_staff')
