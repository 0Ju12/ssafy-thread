from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('comments', '0002_crawlresult_quality_checks')]
    operations = [migrations.AddField(model_name='crawlresult', name='market_snapshot',
                                     field=models.JSONField(blank=True, default=dict,
                                                            verbose_name='동시 수집 시장·환율 스냅샷'))]
