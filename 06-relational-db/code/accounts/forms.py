from django import forms
from django.contrib.auth.forms import UserCreationForm,UserChangeForm
from .models import User
class SignupForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model=User
        fields=('username','email','first_name','last_name','gender','age','weekly_reading_hours','yearly_books','profile_image','favorite_categories')
        widgets={'favorite_categories':forms.CheckboxSelectMultiple}
class ProfileForm(forms.ModelForm):
    class Meta:
        model=User
        fields=('email','first_name','last_name','gender','age','weekly_reading_hours','yearly_books','profile_image','favorite_categories')
        widgets={'favorite_categories':forms.CheckboxSelectMultiple}
