from django.core import signing

SALT = "thread-aladin-selection-v1"

def make_token(book):
    return signing.dumps({key: book.get(key, "") for key in ("title", "author", "description", "cover", "publisher", "isbn13", "pub_date")}, salt=SALT, compress=True)

def read_token(token):
    try:
        return signing.loads(token, salt=SALT, max_age=3600)
    except (signing.BadSignature, signing.SignatureExpired):
        return None
