from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name='Category',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('name',models.CharField(max_length=40,unique=True))]),
        migrations.CreateModel(name='Book',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('title',models.CharField(max_length=200)),('description',models.TextField()),('rating',models.PositiveSmallIntegerField(validators=[MinValueValidator(1),MaxValueValidator(5)])),('author',models.CharField(max_length=120)),('author_info',models.TextField(blank=True)),('author_works',models.TextField(blank=True)),('author_photo_url',models.URLField(blank=True)),('created_at',models.DateTimeField(auto_now_add=True)),('category',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='books',to='books.category')),('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='books',to=settings.AUTH_USER_MODEL))]),
        migrations.CreateModel(name='Thread',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('title',models.CharField(max_length=200)),('content',models.TextField()),('reading_date',models.DateField()),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('cover_image',models.ImageField(blank=True,upload_to='thread_covers/')),('book',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='threads',to='books.book')),('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='threads',to=settings.AUTH_USER_MODEL)),('likes',models.ManyToManyField(blank=True,related_name='liked_threads',to=settings.AUTH_USER_MODEL))]),
        migrations.CreateModel(name='Comment',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('content',models.TextField(max_length=1000)),('created_at',models.DateTimeField(auto_now_add=True)),('thread',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='comments',to='books.thread')),('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='comments',to=settings.AUTH_USER_MODEL))]),
    ]
