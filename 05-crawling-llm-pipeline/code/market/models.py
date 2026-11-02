from django.db import models


class MarketCapture(models.Model):
    """공개 웹 화면에서 실제 수집한 시장/환율 스냅샷. 합성값은 저장하지 않음."""
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
