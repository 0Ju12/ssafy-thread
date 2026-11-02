from django.contrib import admin

from .models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'author', 'customer_review_rank', 'created_at')
    search_fields = ('title', 'author')
