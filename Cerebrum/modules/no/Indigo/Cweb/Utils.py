# -*- coding: iso-8859-1 -*-
import cgi
from Cerebrum.modules.no.Indigo.Cweb import Layout

class HTMLUtil(object):
    def __init__(self, logger, state):
        self.logger = logger
        self.state = state

    def dump_form(self, form):
        return "Form:\n<pre>%s</pre>" % "\n".join(
            ["  %s=%s" % (k, form[k]) for k in form.keys()])

    def error(self, msg):
        tpl = Layout.SubTemplate(self.state, 'error')
        if self.state.is_logged_in():
            self.display(tpl.show({'message': msg}, menu=True))
        else:
            self.display(tpl.show({'message': msg}, menu=False))

    def show_page(self, tpl_class, tpl_name, menu=True):
        self.logger.debug("show_page(%s)" % tpl_name)
        tpl = tpl_class(self.state, tpl_name)
        return tpl.show({}, menu=menu)

    def display(self, html):
        cookie = ''
        if hasattr(self.state, 'cookie'):
            cookie = self.state.cookie
        print "Content-type: text/html"
        print "%s\n\n" % cookie
        print html

    def test_cgi(self, form):
        return
        #form['action'] = 'show_person_find'
        form.list.append(cgi.MiniFieldStorage('action', 'do_login'))
        form.list.append(cgi.MiniFieldStorage('uname', 'un'))
        form.list.append(cgi.MiniFieldStorage('pass', 'pp'))

    def form2items(self, form):
        return [(k, form[k]) for k in form.keys()]

# arch-tag: d07a2380-7155-11da-954b-12215614942d
