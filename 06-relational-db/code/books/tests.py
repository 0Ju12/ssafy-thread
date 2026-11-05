from datetime import date
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Book,Thread,Category,Comment
User=get_user_model()
class BookTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_user(username='owner',password='Pass12345!')
        self.other=User.objects.create_user(username='other',password='Pass12345!')
        self.category=Category.objects.create(name='과학')
        self.book=Book.objects.create(user=self.owner,title='테스트',description='소개',rating=5,author='작가',category=self.category)
        self.thread=Thread.objects.create(user=self.owner,book=self.book,title='감상',content='본문',reading_date=date.today())
    def test_public_pages(self):
        for url in [reverse('books:index'),reverse('books:detail',args=[self.book.pk]),reverse('books:thread_detail',args=[self.thread.pk])]:
            self.assertEqual(self.client.get(url).status_code,200)
    def test_post_only(self):
        self.client.force_login(self.owner)
        for url in [reverse('books:delete',args=[self.book.pk]),reverse('books:thread_delete',args=[self.thread.pk]),reverse('books:like',args=[self.thread.pk])]:
            self.assertEqual(self.client.get(url).status_code,405)
    def test_ownership(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('books:delete',args=[self.book.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('books:thread_delete',args=[self.thread.pk])).status_code,404)
    def test_like_toggle(self):
        self.client.force_login(self.other)
        url=reverse('books:like',args=[self.thread.pk]);self.client.post(url)
        self.assertTrue(self.thread.likes.filter(pk=self.other.pk).exists())
        self.client.post(url);self.assertFalse(self.thread.likes.filter(pk=self.other.pk).exists())
    def test_comment_permissions(self):
        url=reverse('books:comment_create',args=[self.thread.pk])
        self.assertEqual(Comment.objects.count(),0)
        self.client.post(url,{'content':'익명'})
        self.assertEqual(Comment.objects.count(),0)
        self.client.force_login(self.other)
        self.client.post(url,{'content':'댓글'})
        self.assertEqual(Comment.objects.count(),1)
        comment=Comment.objects.first()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('books:comment_delete',args=[comment.pk])).status_code,404)
    def test_category_filter(self):
        response=self.client.get(reverse('books:index'),{'category':str(self.category.pk)})
        self.assertContains(response,'테스트')

    def test_book_crud_and_permissions(self):
        create_url=reverse('books:create')
        self.assertEqual(self.client.get(create_url).status_code,302)
        self.client.force_login(self.other)
        payload={'title':'두번째 책','description':'읽을거리','rating':4,'author':'저자','category':self.category.pk}
        response=self.client.post(create_url,payload)
        self.assertEqual(response.status_code,302)
        created=Book.objects.get(title='두번째 책')
        self.assertEqual(created.user,self.other)
        self.assertEqual(self.client.get(reverse('books:update',args=[self.book.pk])).status_code,404)
        response=self.client.post(reverse('books:update',args=[created.pk]),{**payload,'title':'수정된 책'})
        self.assertEqual(response.status_code,302)
        created.refresh_from_db();self.assertEqual(created.title,'수정된 책')
        self.assertEqual(self.client.post(reverse('books:delete',args=[created.pk])).status_code,302)
        self.assertFalse(Book.objects.filter(pk=created.pk).exists())

    def test_thread_create_update_delete(self):
        self.client.force_login(self.other)
        url=reverse('books:thread_create',args=[self.book.pk])
        payload={'title':'내 감상','content':'참 좋은 이야기','reading_date':'2026-11-05'}
        self.assertEqual(self.client.post(url,payload).status_code,302)
        thread=Thread.objects.get(title='내 감상')
        self.assertEqual(thread.user,self.other)
        self.assertEqual(thread.book,self.book)
        self.assertEqual(self.client.get(reverse('books:thread_update',args=[self.thread.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('books:thread_update',args=[thread.pk]),{**payload,'title':'수정 감상'}).status_code,302)
        thread.refresh_from_db();self.assertEqual(thread.title,'수정 감상')
        self.assertEqual(self.client.post(reverse('books:thread_delete',args=[thread.pk])).status_code,302)
        self.assertFalse(Thread.objects.filter(pk=thread.pk).exists())

    def test_invalid_book_and_thread_forms(self):
        self.client.force_login(self.owner)
        count=Book.objects.count()
        self.assertEqual(self.client.post(reverse('books:create'),{'title':'오류','rating':999}).status_code,200)
        self.assertEqual(Book.objects.count(),count)
        self.assertEqual(self.client.post(reverse('books:thread_create',args=[self.book.pk]),{'title':'','content':''}).status_code,200)

    def test_category_and_comments_visible(self):
        self.client.force_login(self.other)
        self.client.post(reverse('books:comment_create',args=[self.thread.pk]),{'content':'좋았습니다'})
        response=self.client.get(reverse('books:thread_detail',args=[self.thread.pk]))
        self.assertContains(response,'좋았습니다')


class ExtendedPermissionTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_user(username='neo_owner',password='Pass12345!')
        self.other=User.objects.create_user(username='neo_other',password='Pass12345!')
        self.book=Book.objects.create(user=self.owner,title='권한 검증',description='도서 설명',rating=4,author='홍길동')
        self.thread=Thread.objects.create(user=self.owner,book=self.book,title='읽은 감상',content='상세 내용',reading_date=date.today())

    def test_anonymous_mutations_redirect(self):
        for name, pk in [('books:like', self.thread.pk), ('books:delete', self.book.pk), ('books:thread_delete', self.thread.pk), ('books:comment_create', self.thread.pk)]:
            self.assertEqual(self.client.post(reverse(name,args=[pk])).status_code,302)
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())

    def test_mutations_reject_get(self):
        self.client.force_login(self.owner)
        for name,pk in [('books:like',self.thread.pk),('books:comment_create',self.thread.pk),('books:delete',self.book.pk)]:
            self.assertEqual(self.client.get(reverse(name,args=[pk])).status_code,405)

    def test_nonowner_cannot_modify(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('books:update',args=[self.book.pk]),{'title':'변경'}).status_code,404)
        self.assertEqual(self.client.post(reverse('books:thread_update',args=[self.thread.pk]),{'title':'변경'}).status_code,404)

    def test_comment_empty_rejected_and_owner_delete(self):
        self.client.force_login(self.owner)
        url=reverse('books:comment_create',args=[self.thread.pk])
        self.client.post(url,{'content':'   '})
        self.assertFalse(Comment.objects.exists())
        self.client.post(url,{'content':'정상 댓글'})
        comment=Comment.objects.get()
        self.assertEqual(self.client.post(reverse('books:comment_delete',args=[comment.pk])).status_code,302)
        self.assertFalse(Comment.objects.exists())

from unittest.mock import patch
from django.core import signing
from .aladin import search_books, AladinError
from .aladin_signing import make_token, read_token

class AladinIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='aladin_user', password='StrongPassword123!')
        self.client.force_login(self.user)
        self.item = {'title': '파이썬 알고리즘', 'author': '저자 A',
                     'description': '도서 설명', 'cover': 'https://example.com/cover.jpg',
                     'publisher': '출판사 B', 'isbn13': '9781234567890', 'pub_date': '2025-01-01'}

    def test_search_requires_key(self):
        with patch.dict('os.environ', {'ALADIN_TTBKEY': ''}):
            with self.assertRaises(AladinError):
                search_books('파이썬')

    @patch('books.aladin.requests.get')
    def test_search_normalizes_api_response(self, mocked_get):
        mocked_get.return_value.json.return_value = {'item': [dict(self.item, priceStandard=20000)]}
        with patch.dict('os.environ', {'ALADIN_TTBKEY': 'test-key'}):
            result = search_books('파이썬')
        self.assertEqual(result[0]['title'], self.item['title'])
        self.assertEqual(result[0]['price'], 20000)
        self.assertEqual(mocked_get.call_args.kwargs['timeout'], 8)
        self.assertNotIn('test-key', str(result))

    def test_invalid_token_rejected(self):
        self.assertIsNone(read_token('invalid'))
        self.assertEqual(self.client.post(reverse('books:aladin_select'), {'token': 'invalid'}).status_code, 302)
        self.assertEqual(Book.objects.count(), 0)

    def test_selection_requires_final_form_submission(self):
        token = make_token(self.item)
        response = self.client.post(reverse('books:aladin_select'), {'token': token})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '파이썬 알고리즘')
        self.assertEqual(Book.objects.count(), 0)
        response = self.client.post(reverse('books:create'), {
            'aladin_token': token, 'title': self.item['title'], 'author': self.item['author'],
            'description': self.item['description'], 'rating': 5,
        })
        self.assertEqual(response.status_code, 302)
        book = Book.objects.get(title=self.item['title'])
        self.assertEqual(book.aladin_isbn13, self.item['isbn13'])
        self.assertEqual(book.aladin_cover_url, self.item['cover'])

    def test_untrusted_client_changes_do_not_forge_book_metadata(self):
        token = make_token(self.item)
        response = self.client.post(reverse('books:create'), {
            'aladin_token': token, 'title': '다른 책', 'author': '다른 작가',
            'description': '직접 작성', 'rating': 4,
        })
        self.assertEqual(response.status_code, 302)
        book = Book.objects.get(title='다른 책')
        self.assertEqual(book.aladin_isbn13, '')

    def test_anonymous_aladin_access(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('books:aladin_search')).status_code, 302)
        self.assertEqual(self.client.post(reverse('books:aladin_select'), {'token': make_token(self.item)}).status_code, 302)
