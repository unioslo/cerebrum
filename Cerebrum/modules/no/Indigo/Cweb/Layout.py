#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys
import os
import logging
from Cerebrum.modules.no.Indigo.Cweb import Cfg

from ZopePageTemplates import PageTemplate

"""Pagelayout looks like this:

   +--------------+
   |       1      |
   +-+------------+
   |2|     3      |
   | +------------+
   | |     4      |
   +-+------------+

We define a 'metal:define-macro' named 'page' with two
'metal:define-slot': 'menuframe' and 'bodyframe'.  1 is defined in the
main macro, 2 is menuframe, and 3&4 may be in bodyframe.

Subclasses uses similar tecnique for 3 & 4, with a 'body' slot for 4.
"""

class MyPageTemplate(PageTemplate):
    # Cachen har ingen hensikt medmindre vi bruker mod_python, men
    # hjelper da en del (0.0886369 -> 0.00772821 sek for � generere en
    # komplett side)
    cache = {}
    
    def __call__(self, context={}, *args):
        if not context.has_key('args'):
            context['args'] = args
        return self.pt_render(extra_context=context)

    def load(self, name, style):
        tdir = Cfg.template_dir
        style_loc, style_type = style
        for s in (style_loc, 'default'):
            f = os.path.join(tdir, '%s/%s_%s.zpl' % (s, name, style_type))
            if os.path.exists(f):
                break
            f = os.path.join(tdir, '%s/%s.zpl' % (s, name))
            if os.path.exists(f):
                break
        print >>sys.stderr, "Load %s" % f
        self.write(open(f, 'r').read())

    def get_by_name(tpl_name, style):
        key = tpl_name, style
        if MyPageTemplate.cache.has_key(key):
            return MyPageTemplate.cache[key]
        tpl = MyPageTemplate()
        tpl.load(tpl_name, style)
        MyPageTemplate.cache[key] = tpl
        return tpl
    get_by_name = staticmethod(get_by_name)

class MainTemplate(object):
    root_template = os.path.join('macro', 'outer')
    hdr = None

    def __init__(self, state_ref):
        self._state_ref = state_ref

    # Fra Utilities.py:
    def test(*args):
        l=len(args)
        for i in range(1, l, 2):
            if args[i-1]: return args[i]

        if l%2: return args[-1]
    test = staticmethod(test)

    def help_link(id, msg, style='normal'):
        if style == 'normal':
            #return '%s <a href="/web/templates/help.html#%s" target="helpframe">[?]</a>' % (
            #    msg, id)
            return '<a href="/web/templates/help.html#%s" target="helpframe"><img src="/web/templates/help.png" alt="help" border="0" width="12"></a>%s' % (
                id, msg)
        else:
            return '<a href="/web/templates/help.html#%s" target="helpframe">%s</a>' % (
                id, msg)
            
    help_link = staticmethod(help_link)

    def get_menu(self):
        tpl = MyPageTemplate.get_by_name('menu', self._state_ref.get_style())
        return tpl(context={'state': self._state_ref.get_state_dict()})
    
    def show(self, context, bodyframe, menu=True):
        u = MyPageTemplate.get_by_name('bodyframe', self._state_ref.get_style())
        if menu:
            context['menuframe'] = self.get_menu()
        else:
            context['menuframe'] = ''
        context['bodyframe'] = bodyframe
        html = self.apply_tpl(self.root_template, u, context)
        return html

    def apply_tpl(self, tpl_def, tpl_user, context):
        if isinstance(tpl_def, str):
            tpl = MyPageTemplate.get_by_name(tpl_def, self._state_ref.get_style())
        else:
            tpl = tpl_def

        if isinstance(tpl_user, str):
            u = MyPageTemplate.get_by_name(tpl_user, self._state_ref.get_style())
        else:
            u = tpl_user
        context['tpl'] = tpl
        context['test'] = MainTemplate.test
        context['help_link'] = MainTemplate.help_link
        return u(context=context)

    def __str__(self):
        return 'hdr: %s' % repr(self.hdr)

class SubTemplate(MainTemplate):
    def __init__(self, state_ref, tpl):
        super(SubTemplate, self).__init__(state_ref)
        self.tpl = tpl

    def show(self, context, menu=True):
        # TODO: variabel for � lagre current user/group/person-target
        context.setdefault('template', {})['tgt'] = 'Target TODO:obsolete'
        context['state'] = self._state_ref.get_state_dict()
        #print >>sys.stderr, context['state']
        html = self.apply_tpl(self.hdr, self.tpl, context)
        return super(SubTemplate, self).show(context, html, menu=menu)

# The User/Group/PersonTemplate classes allows spesific layout for
# such pages.
class UserTemplate(SubTemplate):
    hdr = os.path.join('macro', 'user_frame')

class PersonTemplate(SubTemplate):
    hdr = os.path.join('macro', 'person_frame')

class GroupTemplate(SubTemplate):
    hdr = os.path.join('macro', 'group_frame')

# arch-tag: cf3d3cfa-7155-11da-9945-71c67cf3c1a7
