from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator
class User(AbstractUser):
    GENDERS=[('','선택 안 함'),('M','남성'),('F','여성'),('O','기타')]
    gender=models.CharField(max_length=1,choices=GENDERS,blank=True)
    age=models.PositiveIntegerField(null=True,blank=True)
    weekly_reading_hours=models.PositiveIntegerField(default=0)
    yearly_books=models.PositiveIntegerField(default=0)
    profile_image=models.ImageField(upload_to='profiles/',blank=True)
    followings=models.ManyToManyField('self',symmetrical=False,related_name='followers',blank=True)
    favorite_categories=models.ManyToManyField('books.Category',related_name='fans',blank=True)
