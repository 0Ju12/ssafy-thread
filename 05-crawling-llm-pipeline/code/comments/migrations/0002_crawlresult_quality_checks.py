from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('comments', '0001_initial')]
    operations = [
        migrations.AddField(
            model_name='crawlresult',
            name='quality_checks',
            field=models.JSONField(blank=True, default=list, verbose_name='증강 검증 결과'),
        ),
    ]
