from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()
PASSWORD = 'ssafy-pass-1234!'


class AccountsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password=PASSWORD)

    def login(self):
        self.client.login(username='tester', password=PASSWORD)

    # F402 -----------------------------------------------------------------
    def test_custom_user_model(self):
        self.assertEqual(User._meta.label, 'accounts.User')

    # F406 login ------------------------------------------------------------
    def test_login_get_and_post(self):
        self.assertEqual(self.client.get(reverse('accounts:login')).status_code, 200)
        res = self.client.post(reverse('accounts:login'), {'username': 'tester', 'password': PASSWORD})
        self.assertRedirects(res, reverse('books:index'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_invalid_shows_error(self):
        res = self.client.post(reverse('accounts:login'), {'username': 'tester', 'password': 'wrong'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['form'].errors)

    def test_login_next_and_open_redirect(self):
        url = reverse('accounts:login') + '?next=/books/create/'
        res = self.client.post(url, {'username': 'tester', 'password': PASSWORD})
        self.assertRedirects(res, '/books/create/')
        self.client.logout()
        url = reverse('accounts:login') + '?next=https://evil.com/'
        res = self.client.post(url, {'username': 'tester', 'password': PASSWORD})
        self.assertRedirects(res, reverse('books:index'))

    def test_navbar_changes_by_login(self):
        res = self.client.get(reverse('books:index'))
        self.assertContains(res, 'LOGIN')
        self.assertNotContains(res, 'CREATE')
        self.login()
        res = self.client.get(reverse('books:index'))
        self.assertContains(res, 'CREATE')
        self.assertContains(res, 'MY PROFILE')
        self.assertContains(res, 'LOGOUT')
        self.assertNotContains(res, '>LOGIN<')

    def test_logged_in_user_cannot_open_login_signup(self):
        self.login()
        self.assertRedirects(self.client.get(reverse('accounts:login')), reverse('books:index'))
        self.assertRedirects(self.client.get(reverse('accounts:signup')), reverse('books:index'))

    # F407 logout -----------------------------------------------------------
    def test_logout_post_only(self):
        self.login()
        self.assertEqual(self.client.get(reverse('accounts:logout')).status_code, 405)
        res = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(res, reverse('books:index'))
        self.assertNotIn('_auth_user_id', self.client.session)

    # F408 + F418 signup ----------------------------------------------------
    def test_signup_with_extra_fields(self):
        res = self.client.post(reverse('accounts:signup'), {
            'username': 'newbie',
            'password1': PASSWORD,
            'password2': PASSWORD,
            'email': 'newbie@example.com',
            'last_name': '김',
            'first_name': '싸피',
            'gender': 'M',
            'age': 25,
            'weekly_avg_reading_time': 3,
            'annual_reading_amount': 12,
            'interested_genres': ['NOVEL', 'SCIENCE'],
        })
        self.assertRedirects(res, reverse('books:index'))
        user = User.objects.get(username='newbie')
        self.assertEqual(user.interested_genres, 'NOVEL,SCIENCE')
        self.assertEqual(user.get_interested_genres_display(), '소설/시/희곡, 과학')
        self.assertEqual(user.age, 25)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)  # 가입 후 로그인

    def test_signup_rejects_negative_numbers_and_mismatch(self):
        res = self.client.post(reverse('accounts:signup'), {
            'username': 'bad', 'password1': PASSWORD, 'password2': PASSWORD + 'x', 'age': -1,
        })
        self.assertEqual(res.status_code, 200)
        errors = res.context['form'].errors
        self.assertIn('password2', errors)
        self.assertIn('age', errors)
        self.assertFalse(User.objects.filter(username='bad').exists())

    def test_signup_labels_korean(self):
        res = self.client.get(reverse('accounts:signup'))
        form = res.context['form']
        self.assertEqual(form.fields['password1'].label, '비밀번호')
        self.assertEqual(form.fields['password2'].label, '비밀번호 확인')
        self.assertEqual(form.fields['age'].label, '나이')
        self.assertEqual(list(form.fields)[:3], ['username', 'password1', 'password2'])

    # F409 + F418 update ----------------------------------------------------
    def test_update_requires_login(self):
        res = self.client.get(reverse('accounts:update'))
        self.assertRedirects(res, reverse('accounts:login') + '?next=' + reverse('accounts:update'))

    def test_update_initial_and_save(self):
        self.user.interested_genres = 'NOVEL,KIDS'
        self.user.save()
        self.login()
        res = self.client.get(reverse('accounts:update'))
        form = res.context['form']
        self.assertEqual(form.initial['interested_genres'], ['NOVEL', 'KIDS'])
        # 일반 사용자가 보면 안 되는 칸은 없음
        for hidden in ('password', 'is_superuser', 'is_staff', 'username'):
            self.assertNotIn(hidden, form.fields)
        self.assertContains(res, reverse('accounts:change_password'))

        res = self.client.post(reverse('accounts:update'), {
            'email': 'a@b.com', 'last_name': '이', 'first_name': '영주',
            'gender': 'F', 'age': 30, 'interested_genres': ['SCIENCE'],
        })
        self.assertRedirects(res, reverse('books:index'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.interested_genres, 'SCIENCE')
        self.assertEqual(self.user.email, 'a@b.com')

    # F410 delete -----------------------------------------------------------
    def test_delete_post_only(self):
        self.login()
        self.assertEqual(self.client.get(reverse('accounts:delete')).status_code, 405)
        res = self.client.post(reverse('accounts:delete'))
        self.assertRedirects(res, reverse('books:index'))
        self.assertFalse(User.objects.filter(username='tester').exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    # F411 change_password --------------------------------------------------
    def test_change_password_keeps_login(self):
        self.login()
        self.assertEqual(self.client.get(reverse('accounts:change_password')).status_code, 200)
        new_pw = 'brand-new-pass-5678!'
        res = self.client.post(reverse('accounts:change_password'), {
            'old_password': PASSWORD, 'new_password1': new_pw, 'new_password2': new_pw,
        })
        self.assertRedirects(res, reverse('books:index'))
        # 강제 로그아웃되지 않았는지 : 로그인이 필요한 페이지 접근 가능
        self.assertEqual(self.client.get(reverse('accounts:update')).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_pw))

    def test_change_password_wrong_old(self):
        self.login()
        res = self.client.post(reverse('accounts:change_password'), {
            'old_password': 'nope', 'new_password1': 'x-new-pass-99', 'new_password2': 'x-new-pass-99',
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn('old_password', res.context['form'].errors)

    # F419 profile ----------------------------------------------------------
    def test_profile_page(self):
        self.user.email = 'tester@example.com'
        self.user.last_name, self.user.first_name = '홍', '길동'
        self.user.gender, self.user.age = 'M', 40
        self.user.weekly_avg_reading_time, self.user.annual_reading_amount = 1, 12
        self.user.interested_genres = 'NOVEL'
        self.user.save()
        self.login()
        res = self.client.get(reverse('accounts:profile', args=['tester']))
        for text in ('tester@example.com', '홍길동', '남성', '40세', '1시간', '12권', '소설/시/희곡',
                     '회원정보 수정', '회원탈퇴'):
            self.assertContains(res, text)

    def test_other_profile_hides_buttons(self):
        User.objects.create_user(username='other', password=PASSWORD)
        self.login()
        res = self.client.get(reverse('accounts:profile', args=['other']))
        self.assertNotContains(res, '회원탈퇴')
        self.assertEqual(self.client.get(reverse('accounts:profile', args=['ghost'])).status_code, 404)
