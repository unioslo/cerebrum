# -*- encoding: utf-8 -*-
import os.path
import os
import cherrypy
import passwd
import activation
import cerebrum_path
import cereconf
import locale
import gettext
from lib.utils import get_content_type
from lib.utils import negotiate_lang, get_translation

    
def index(**vargs):

    content_type = get_content_type()
    lang = negotiate_lang(**vargs)
    _ = get_translation('userclients', 'locale/', lang)
    cherrypy.response.headerMap['Content-Type'] = content_type
    return '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n' + \
'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">\n' + \
    '<head>\n' + \
    '<meta http-equiv="Content-Type" content="' + content_type + '"/>\n' +\
    '<link rel="shortcut icon" type="image/gif" href="/img/litenmedtekst72.gif"/>\n' + \
    '<title>\n' + \
         _('NTNU&apos;s database for administering user accounts') + \
    '\n</title>\n' + \
    '<link rel="stylesheet" type="text/css" media="screen" href="css/ntnu.css" charset="utf-8" />\n' + \
    '</head>\n' + \
    '<body>\n' + \
  '<div class="pagewrap">\n' + \
    '<div class="orginfo">\n' + \
      'NORGES TEKNISKE-NATURVITENSKAPLIGE UNIVERSITET\n' + \
    '</div>\n' + \
    '<div id="topp">\n' + \
    '<img src="/img/BAS_ntnu_logo.png" alt="NTNU" />\n' + \
    '</div>\n' + \
    '<div id="page">\n' + \
      '<h1>' + \
         _('NTNU&apos;s database for administering user accounts') + \
      '</h1>\n' + \
        '<div class="text">\n' + \
          '<a href="/passwd/index">' + \
            _('Change password for an existing user account') + \
          '</a>\n' + \
        '</div>\n' + \
        '<div class="text">\n' + \
          '<a href="/activation/index">' + \
                _('Activate your user account at NTNU') + \
          '</a>\n' + \
        '</div>\n' + \
        '<br /><br />' + \
        '<div class="text">\n' + \
            choose_link(lang) + '\n' + \
        '</div>\n' + \
    '</div>\n' + \
  '</div>\n' + \
'</body>\n' + \
'</html>\n'
index.exposed = True

def choose_link(lang):
    if lang == 'en':
        return 'Velg <a href="/?lang=no">norsk</a> språk.'
    return  'Choose <a href="/?lang=en">english</a> language.'
