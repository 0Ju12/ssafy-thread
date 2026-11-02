from django.contrib import admin

from .models import CrawlResult


@admin.register(CrawlResult)
class CrawlResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'query', 'stock_name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('query', 'stock_name')
    readonly_fields = ('created_at',)
