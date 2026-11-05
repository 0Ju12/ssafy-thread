from django.core.management.base import BaseCommand
from books.models import Category
class Command(BaseCommand):
    help='기본 도서 장르 생성'
    def handle(self,*args,**kwargs):
        for name in ['소설/시/희곡','경제/경영','자기계발','인문/교양','취미/실용','어린이/청소년','과학']:
            Category.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS('장르 준비 완료'))
