mina is a simple blog system based on [Google App Engine](http://code.google.com/intl/zh-CN/appengine/), developed for some of my friends who want to have their own blog, modified from my [original site](http://www.hulufei.com), stealing a lot from [livid/picky](https://github.com/livid/picky). Feel free to use it or modify it as you wish.

[Here](http://www.gongyiling.com) is what it looks like, and thank the guy give me power to finish it.

# 如何使用 #

1. 下载Google App Engine, 并且[注册账号](http://appengine.google.com/)
2. 在Google App Engine后台申请创建一个应用，并且记下ID
3. 下载[mina](https://github.com/hulufei/mina)，解压
4. 在解开的文件夹中，修改app.yaml文件，将其中的app-id替换成你自己申请的ID
5. 最后按照[说明](http://code.google.com/intl/zh-CN/appengine/docs/python/tools/uploadinganapp.html)上传应用，部署完成

为了能正常访问，推荐绑定自己的域名，并且使用CloudFlare服务

start.bat(for Windows), start.sh(for Linux)是一个简单的启动本地开发服务器的脚本，指定了数据存储在dev_appserver.datastore文件, 方便测试和开发

管理地址: /admin/, 写文章支持使用[markdown](http://daringfireball.net/projects/markdown/)，满足简单的排版格式需求

如有其他疑问，请发邮件：[f.calabash@gmail.com](mailto:f.calabash@gmail.com)
