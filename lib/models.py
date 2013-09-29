from google.appengine.ext import db
from google.appengine.api import memcache

class Archie(db.Model):
    date = db.DateProperty(required=True)
    count = db.IntegerProperty(default=0)

class Post(db.Model):
    title = db.StringProperty(required=True)
    author = db.StringProperty(required=True)
    date = db.DateTimeProperty(auto_now_add=True)
    last_modified = db.DateTimeProperty(auto_now=True)
    content = db.TextProperty(required=True, default='')
    content_formatted = db.TextProperty()

    comment_count = db.IntegerProperty(default=0)
    categories = db.StringListProperty(default=None)
    hits = db.IntegerProperty(default=0)
    permalink = db.StringProperty()
    is_page = db.BooleanProperty(required=True, default=False)
    is_delete = db.BooleanProperty(required=True, default=False)
    archie = db.ReferenceProperty(Archie)

class Category(db.Model):
    name = db.StringProperty(required=True)
    postNum = db.IntegerProperty(default=0)

class Comment(db.Model):
    post = db.ReferenceProperty(Post)
    date = db.DateTimeProperty(auto_now_add=True)
    nickname = db.StringProperty()
    email = db.StringProperty(default='example@gmail.com')
    gravatar = db.StringProperty()
    ip = db.StringProperty()
    site = db.StringProperty()
    content = db.TextProperty(required=True)
    response = db.StringProperty(default='')
    response_date = db.DateTimeProperty(auto_now_add=True)

class Site(db.Model):
    title = db.StringProperty(required=False, indexed=True)
    substance = db.TextProperty()

    def get(self, name):
        value = memcache.get(name)
        if value is None:
            q = db.GqlQuery('SELECT * FROM Site WHERE title = :1', name)
            if q.count() == 1:
                value = q[0].substance
                memcache.delete(name)
                memcache.set(name, value, 86400)
            else:
                value = ''
        return value
    get = classmethod(get)

    def set(self, name, value):
        q = db.GqlQuery('SELECT * FROM Site WHERE title = :1', name)
        if q.count() == 1:
            d = q[0]
        else:
            d = Site()
            d.title = name
        d.substance = value
        d.put()
        memcache.delete(name)
        memcache.set(name, d.substance, 86400)
    set = classmethod(set)
