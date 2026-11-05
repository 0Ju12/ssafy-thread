from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("books", "0001_initial")]
    operations = [
        migrations.AddField(model_name="book", name="aladin_isbn13", field=models.CharField(max_length=13, blank=True, db_index=True)),
        migrations.AddField(model_name="book", name="aladin_cover_url", field=models.URLField(blank=True, max_length=500)),
        migrations.AddField(model_name="book", name="aladin_publisher", field=models.CharField(max_length=200, blank=True)),
        migrations.AddField(model_name="book", name="aladin_pub_date", field=models.CharField(max_length=30, blank=True)),
    ]
