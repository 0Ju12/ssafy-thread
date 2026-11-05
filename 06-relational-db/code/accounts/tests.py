from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
User=get_user_model()
class AccountTests(TestCase):
    def setUp(self):
        self.a=User.objects.create_user(username='alice',password='Pass12345!')
        self.b=User.objects.create_user(username='bob',password='Pass12345!')
    def test_login_logout(self):
        self.assertEqual(self.client.post(reverse('accounts:login'),{'username':'alice','password':'Pass12345!'}).status_code,302)
        self.assertEqual(self.client.get(reverse('accounts:logout')).status_code,405)
        self.assertEqual(self.client.post(reverse('accounts:logout')).status_code,302)
    def test_follow_toggle_and_self_follow(self):
        self.client.force_login(self.a)
        url=reverse('accounts:follow',args=['bob'])
        self.client.post(url);self.assertTrue(self.a.followings.filter(pk=self.b.pk).exists())
        self.client.post(url);self.assertFalse(self.a.followings.filter(pk=self.b.pk).exists())
        self.client.post(reverse('accounts:follow',args=['alice']))
        self.assertFalse(self.a.followings.filter(pk=self.a.pk).exists())
    def test_profile_public(self):
        self.assertEqual(self.client.get(reverse('accounts:profile',args=['alice'])).status_code,200)

    def test_signup_with_required_data_and_profile_update(self):
        response=self.client.post(reverse('accounts:signup'),{'username':'newuser','password1':'ComplexPass2026!','password2':'ComplexPass2026!','weekly_reading_hours':2,'yearly_books':10})
        self.assertEqual(response.status_code,302)
        self.assertTrue(User.objects.filter(username='newuser').exists())
        response=self.client.post(reverse('accounts:update'),{'email':'new@example.com','first_name':'새','last_name':'유저','weekly_reading_hours':3,'yearly_books':11})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.url,reverse('books:index'))

    def test_profile_shows_threads_and_followers(self):
        from books.models import Book,Thread
        from datetime import date
        book=Book.objects.create(user=self.a,title='독서',description='내용',rating=5,author='저자')
        Thread.objects.create(user=self.a,book=book,title='나의 쓰레드',content='감상',reading_date=date.today())
        self.assertContains(self.client.get(reverse('accounts:profile',args=['alice'])),'나의 쓰레드')

    def test_password_change_preserves_session(self):
        self.client.force_login(self.a)
        url=reverse('accounts:change_password')
        response=self.client.post(url,{'old_password':'Pass12345!','new_password1':'NewSafePass2026!','new_password2':'NewSafePass2026!'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.url,reverse('books:index'))
        self.assertEqual(self.client.get(reverse('accounts:update')).status_code,200)


class AccountSecurityTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='secure_user',password='Pass12345!')

    def test_public_profile_and_protected_settings(self):
        self.assertEqual(self.client.get(reverse('accounts:profile',args=['secure_user'])).status_code,200)
        for name in ('accounts:update','accounts:change_password'):
            self.assertEqual(self.client.get(reverse(name)).status_code,302)

    def test_post_only_account_deletion(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('accounts:delete')).status_code,405)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertEqual(self.client.post(reverse('accounts:delete')).status_code,302)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
