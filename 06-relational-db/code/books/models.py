from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator,MaxValueValidator
class Category(models.Model):
    name=models.CharField(max_length=40,unique=True)
    def __str__(self):return self.name
class Book(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='books')
    title=models.CharField(max_length=200)
    description=models.TextField()
    rating=models.PositiveSmallIntegerField(validators=[MinValueValidator(1),MaxValueValidator(5)])
    author=models.CharField(max_length=120)
    category=models.ForeignKey(Category,on_delete=models.SET_NULL,null=True,blank=True,related_name='books')
    author_info=models.TextField(blank=True)
    author_works=models.TextField(blank=True)
    author_photo_url=models.URLField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    aladin_isbn13=models.CharField(max_length=13,blank=True,db_index=True)
    aladin_cover_url=models.URLField(blank=True,max_length=500)
    aladin_publisher=models.CharField(max_length=200,blank=True)
    aladin_pub_date=models.CharField(max_length=30,blank=True)
    def __str__(self):return self.title
class Thread(models.Model):
    book=models.ForeignKey(Book,on_delete=models.CASCADE,related_name='threads')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='threads')
    title=models.CharField(max_length=200)
    content=models.TextField()
    reading_date=models.DateField()
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    likes=models.ManyToManyField(settings.AUTH_USER_MODEL,related_name='liked_threads',blank=True)
    cover_image=models.ImageField(upload_to='thread_covers/',blank=True)
    def __str__(self):return self.title
class Comment(models.Model):
    thread=models.ForeignKey(Thread,on_delete=models.CASCADE,related_name='comments')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='comments')
    content=models.TextField(max_length=1000)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return self.content[:40]
