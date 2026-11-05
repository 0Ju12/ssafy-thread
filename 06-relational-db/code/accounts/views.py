from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth import login as auth_login,logout as auth_logout,update_session_auth_hash,get_user_model
from django.contrib.auth.forms import AuthenticationForm,PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods,require_POST
from .forms import SignupForm,ProfileForm
User=get_user_model()
@require_http_methods(['GET','POST'])
def login(request):
    if request.user.is_authenticated:return redirect('books:index')
    form=AuthenticationForm(request,data=request.POST or None)
    if request.method=='POST' and form.is_valid():auth_login(request,form.get_user());return redirect('books:index')
    return render(request,'accounts/form.html',{'form':form,'heading':'로그인'})
@require_POST
@login_required
def logout(request):auth_logout(request);return redirect('books:index')
@require_http_methods(['GET','POST'])
def signup(request):
    if request.user.is_authenticated:return redirect('books:index')
    form=SignupForm(request.POST or None,request.FILES or None)
    if request.method=='POST' and form.is_valid():
        user=form.save();auth_login(request,user);return redirect('books:index')
    return render(request,'accounts/form.html',{'form':form,'heading':'회원가입'})
@require_http_methods(['GET'])
def profile(request,username):
    person=get_object_or_404(User,username=username)
    return render(request,'accounts/profile.html',{'person':person})
@require_POST
@login_required
def follow(request,username):
    person=get_object_or_404(User,username=username)
    if person!=request.user:
        if request.user.followings.filter(pk=person.pk).exists():request.user.followings.remove(person)
        else:request.user.followings.add(person)
    return redirect('accounts:profile',username=username)
@require_http_methods(['GET','POST'])
@login_required
def update(request):
    form=ProfileForm(request.POST or None,request.FILES or None,instance=request.user)
    if request.method=='POST' and form.is_valid():form.save();return redirect('books:index')
    return render(request,'accounts/form.html',{'form':form,'heading':'회원정보 수정'})
@require_POST
@login_required
def delete(request):
    request.user.delete();auth_logout(request);return redirect('books:index')
@require_http_methods(['GET','POST'])
@login_required
def change_password(request):
    form=PasswordChangeForm(request.user,request.POST or None)
    if request.method=='POST' and form.is_valid():
        user=form.save();update_session_auth_hash(request,user);return redirect('books:index')
    return render(request,'accounts/form.html',{'form':form,'heading':'비밀번호 변경'})
