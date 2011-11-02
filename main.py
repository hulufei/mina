#!/usr/bin/env python
# coding=utf-8

import os
import urllib
import re
import random
import string
import hashlib
import simplejson
from datetime import datetime
import logging
import markdown

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.api import images
from google.appengine.api import xmpp

from lib.models import *

PAGESIZE = Site.get('page_size') or 10

def getavatar(email, size, default='identicon'):
    gravatar_url = 'http://www.gravatar.com/avatar/%s/?%s'
    if not re.match(r'\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*', email):
        email = ''.join(random.sample(string.letters, 8))
    return gravatar_url %(hashlib.md5(email).hexdigest(), urllib.urlencode({'d': default, 's': str(size)}))

def getparam(self, param):
    try:
        return self.request.get(param)
    except:
        raise 'Get param error'

def doRender(self, template_html, values={}):
    tpl = os.path.join(os.path.dirname(__file__), 'tpl')
    site_theme = Site.get('site_theme')
    themes = os.listdir(tpl)
    if site_theme is None or site_theme not in themes:
        site_theme = 'default'
    path = os.path.join(tpl, site_theme, template_html)
    if not values.has_key('site_author'):
        values['site_author'] = Site.get('author')
    if not values.has_key('admin'):
        values['admin'] = users.is_current_user_admin()
    archives = memcache.get('archives')
    if archives is None:
        archives = Archie.all().order('-date').fetch(100)
        memcache.set('archives', archives)
    values['archies'] = archives
    tags = memcache.get('tags')
    if tags is None:
        tags = Category.all().order('-name').fetch(100)
        memcache.set('tags', tags)
    values['categories'] = tags
    page = template.render(path, values)
    self.response.out.write(page)
    return page

def str2date(strDate):
    return datetime.strptime(strDate, '%Y-%m-%dT%H:%M')

class MainHandler(webapp.RequestHandler):
    def get(self):
        site_name = Site.get('name')
        site_slogan = Site.get('slogan')
        admin = users.is_current_user_admin()
        main_page = memcache.get('main_page')
        if not admin and main_page is not None:
            self.response.out.write(main_page)
        else:
            posts = Post.all().order('-date').filter('is_delete =', False).fetch(PAGESIZE)
            values = {
                'title': site_name,
                'site_name': site_name,
                'site_slogan': site_slogan,
                'posts':posts,
                'admin': admin
            }
            page = doRender(self, 'index.html', values)
            if not admin:
                memcache.add('main_page', page)

class AdminHandler(webapp.RequestHandler):
    def get(self):
        doRender(self, 'admin.html', {'site_name': Site.get('name')})

class WriterHandler(webapp.RequestHandler):
    def get(self):
        values = {}
        values['site_name'] = 'Writing'
        values['author'] = Site.get('author')
        key = getparam(self, 'key')
        values['categories'] = Category.all().fetch(50)
        if key:
            values['key'] = getparam(self, 'key')
            values['post'] = db.get(db.Key(key))
        doRender(self, 'write.html', values)

    def post(self):
        key = getparam(self, 'key')
        title = getparam(self, 'title')
        author = getparam(self, 'author')
        date = str2date(getparam(self, 'date'))
        content = getparam(self, 'content')
        content_formatted = markdown.markdown(content)
        #获取tags集合
        categories = set(self.request.get_all('category'))
        permalink = self.request.get('permalink')

        if permalink == '' or permalink is None:
            permalink = date.strftime('%Y%m%d%H%M')
        permalink = '-'.join(permalink.split())
        #构造查询Category的GqlQuery对象
        category_query = db.GqlQuery('SELECT * FROM Category WHERE name = :1')

        if key:	#edit post,update post
            post = db.get(db.Key(key))
            #相应文章当前所属tags集合
            post_categories = set(post.categories)    
            #编辑后取消关联的tags集合
            cancel_categories = post_categories - categories
            for cat in cancel_categories:   
                category_query.bind(cat)
                result = category_query.get()
                result.postNum -= 1
                post.categories.remove(cat)
                result.put()
            post.title = title
            post.author = author
            post.content = content
            post.content_formatted = content_formatted
            post.date = date
            post.permalink = permalink
        else: 
            # Add new post,create post
            post = Post(title=title, author=author, content=content, content_formatted=content_formatted, date=date, permalink=permalink)
        # Archie the post
        serial_date = date.date().replace(date.year, date.month, 1)
        archie = Archie.gql('WHERE date = :1', serial_date).get()
        if archie:
            archie.count += 1
        else:
            archie = Archie(date=serial_date, count=1)
        archie.put()
        post.archie = archie

        for category in categories:
            category_query.bind(category)
            result = category_query.get()
            if(result):
                if key and (category in post_categories):
                    continue	#for editing post
                result.postNum += 1
                result.put()
            else:
                category_instance = Category(name=category, postNum=1)
                category_instance.put()
            if category not in post.categories:
                post.categories.append(category)
        post.put()
        memcache.delete('main_page')
        memcache.delete('archives')
        memcache.delete('tags')
        self.redirect('/post/' + permalink)

class DeletePost(webapp.RequestHandler):
    def get(self):
        key = getparam(self, 'key')
        db_key = db.Key(key)
        post = Post.get(db_key)
        for category in post.categories:
            category_entity = Category.all().filter('name =', category).get()
            if category_entity:
                category_entity.postNum -= 1
                if category_entity.postNum == 0:
                    category_entity.delete()
                else:
                    category_entity.put()
        comments = Comment.all().filter('post =', post).fetch(100)
        if len(comments) > 0:
            db.delete(comments)
        # Update archies
        date = post.date.date()
        archies = Archie.gql('WHERE date = :1', date.replace(date.year, date.month, 1)).get()
        archies.count -= 1
        if archies.count <= 0:
            db.delete(archies)
        else:
            archies.put()
        #db.delete(db_key)
        post.is_delete = True
        post.put()
        memcache.delete('main_page')
        memcache.delete('archives')
        memcache.delete('tags')
        self.response.out.write('<p>Deleted</p><a href="/">Back to home</a>')

class PostHandler(webapp.RequestHandler):
    def get(self, url):
        post = db.GqlQuery("SELECT * FROM Post WHERE permalink = :1 AND is_delete = :2 LIMIT 1", url, False).get()
        if post:
            tpl = 'article.html'
        else:
            tpl = '404.html'
            return doRender(self, tpl)
        post.format_date = (post.date).strftime('%Y-%m-%d %H:%M')
        post.hits = post.hits + 1
        try:
            post.put()
        except:
            post.hits = post.hits - 1
        comments = Comment.all().filter('post =', post).fetch(100)
        values = {
            'title': post.title,
            'post': post,
            'comments': comments,
            'site_name': Site.get('name'),
            'site_slogan': Site.get('slogan')
        }
        doRender(self, tpl, values)

class ArchiveHandler(webapp.RequestHandler):
    def get(self, date):
        values = {
            'site_name': Site.get('name'),
            'site_slogan': Site.get('slogan')
        }
        if date:
            year_month = date.split('-')
            year = int(year_month[0])
            month = int(year_month[1])
            next_month = month + 1
            if next_month > 12:
                limit_date = datetime.strptime(str(year + 1) + '-' + str(1), '%Y-%m')
            else:
                limit_date = datetime.strptime(str(year) + '-' + str(month + 1), '%Y-%m')
            posts = db.GqlQuery("SELECT * FROM Post WHERE is_delete = False AND date >=:1 AND date <=:2",
                datetime.strptime(date, '%Y-%m'), limit_date).fetch(100)
            values['posts'] = posts
            doRender(self, 'index.html', values)
        else:
            doRender(self, 'archive.html', values)

class TagHandler(webapp.RequestHandler):
    def get(self, tag):
        values = {
            'site_name': Site.get('name'),
            'site_slogan': Site.get('slogan')
        }
        tag = urllib.unquote(tag).decode('utf-8')
        query = Post.all().order('-date').filter('is_delete =', False).filter('categories =', tag)
        values['posts'] = query.fetch(PAGESIZE)
        doRender(self, 'index.html', values)

class AddComment(webapp.RequestHandler):
    def post(self):
        post_key = db.Key(getparam(self, 'key'))
        nickname = self.request.get('nickname', default_value=u'路人')
        email = getparam(self, 'email')
        site = getparam(self, 'site').strip()
        content = getparam(self, 'content')

        if nickname.strip() == '':
            nickname = u'路人'
        if len(site) < 8 or not site.startswith('http://'):
            site = None
        if content.strip() == '':
            self.response.out.write('You comment has no meaning!!')
        gravatar = getavatar(email, size='40')
        comment = Comment(post=post_key, nickname=nickname, email=email,
            gravatar=gravatar, ip=self.request.remote_addr, site=site,
            content=content)
        comment.post.comment_count += 1
        comment.post.put()
        comment.put()
        permalink = self.request.host_url + '/post/' + comment.post.permalink
        self.redirect(permalink)
        gt = Site.get('gtalk')
        xmpp.send_message(gt, 
                '%s(%s) comments on %s: %s' % (nickname, email, permalink, content))

class DeleteComment(webapp.RequestHandler):
    def post(self):
        key = self.request.get('key')
        try:
            comment = db.get(db.Key(key))
            post = comment.post
            comment.delete()
            post.comment_count = post.comment_count - 1
            post.put()
            self.response.out.write('ok')
        except Exception, e: 
            self.response.out.write(e)

class ReplyComment(webapp.RequestHandler):
    def post(self):
        key = self.request.get('key')
        response = self.request.get('response')
        comment = db.get(db.Key(key))
        comment.response = response
        comment.put()
        response_data = {'content': response, 'date': datetime.now().strftime('%Y-%m-%d %H:%M')}
        json = simplejson.dumps(response_data)
        self.response.headers['content-type'] = 'application/json'
        self.response.out.write(json)

# livid/picky: 
# https://github.com/livid/picky/blob/master/main.py
class AtomFeedHandler(webapp.RequestHandler):
    def get(self):
        site_domain = Site.get('domain')
        site_name = Site.get('name')
        site_author = Site.get('author')
        site_slogan = Site.get('slogan')
        template_values = {
          'site_domain' : site_domain,
          'site_name' : site_name,
          'site_author' : site_author,
          'site_slogan' : site_slogan,
          'feed_url' : '/feed/',
          #'site_updated': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        }

        output = memcache.get('feed_output')
        if output is None:
          articles = db.GqlQuery("SELECT * FROM Post WHERE is_delete = FALSE ORDER BY date DESC LIMIT 100")
          template_values['articles'] = articles
          template_values['articles_total'] = articles.count()
          path = os.path.join(os.path.dirname(__file__), 'tpl', 'feed.xml')
          output = template.render(path, template_values)
          memcache.set('feed_output', output, 86400)
        self.response.headers['Content-type'] = 'text/xml; charset=UTF-8'
        self.response.out.write(output)

class SettingsHandler(webapp.RequestHandler):
    def get(self):
        values = {
            'page_name': 'Setting',
            'site_name': Site.get('name'),
            'slogan': Site.get('slogan'),
            'site_author': Site.get('author'),
            'site_domain': Site.get('domain'),
            'site_theme': Site.get('site_theme'),
            'gtalk': Site.get('gtalk')
        }
        doRender(self, 'setting.html', values)

    def post(self):
        Site.set('name', getparam(self, 'site_name'))
        Site.set('slogan', getparam(self, 'site_slogan'))
        Site.set('author', getparam(self, 'site_author'))
        Site.set('domain', getparam(self, 'site_domain'))
        Site.set('site_theme', getparam(self, 'site_theme'))
        Site.set('gtalk', getparam(self, 'gtalk'))
        memcache.delete('main_page')
        self.redirect('/')

class LogoutHandler(webapp.RequestHandler):
    def get(self):
        logout_url = users.create_logout_url('/')
        self.redirect(logout_url)

application = webapp.WSGIApplication(
				    [('/', MainHandler),
				     ('/admin/', AdminHandler),
				     ('/post/([0-9a-zA-Z\-\_]+)', PostHandler),
				     ('/post/(.*)', PostHandler),
                     ('/archive/(.*)', ArchiveHandler),
                     ('/tag/(.*)', TagHandler),
                     ('/feed/', AtomFeedHandler),
                     ('/admin/setting', SettingsHandler),
				     ('/admin/write', WriterHandler),
				     ('/admin/post/delete', DeletePost),
                     ('/admin/comment/delete', DeleteComment),
				     ('/comment', AddComment),
                     ('/admin/comment/reply', ReplyComment),
                     ('/logout', LogoutHandler)
				    ], debug=True)

def main():
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
