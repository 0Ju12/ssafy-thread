from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[('accounts','0001_initial'),('books','0001_initial')]
    operations=[migrations.AddField(model_name='user',name='favorite_categories',field=models.ManyToManyField(blank=True,related_name='fans',to='books.category'))]
