from django import forms
from .models import Book,Thread,Comment
class BookForm(forms.ModelForm):
    class Meta:
        model=Book
        fields=('title','description','rating','author','category')
        widgets={'description':forms.Textarea(attrs={'rows':5})}
class ThreadForm(forms.ModelForm):
    class Meta:
        model=Thread
        fields=('title','content','reading_date','cover_image')
        widgets={'reading_date':forms.DateInput(attrs={'type':'date','class':'form-control'}),'content':forms.Textarea(attrs={'rows':6})}
class CommentForm(forms.ModelForm):
    class Meta:
        model=Comment
        fields=('content',)
