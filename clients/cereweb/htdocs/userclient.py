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
    cherrypy.session['lang'] = lang
    _ = get_translation('userclients', 'locale/', lang)
    cherrypy.response.headerMap['Content-Type'] = content_type
    return '''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
    <head>
        <meta http-equiv="Content-Type" content="''' + content_type + '''"/>
        <link rel="shortcut icon" type="image/gif" href="/img/litenmedtekst72.gif"/>
        <title>''' + _('NTNU&apos;s database for administering user accounts') + '''</title>
        <link rel="stylesheet" type="text/css" media="screen" href="css/ntnu.css" charset="utf-8" />
    </head>
    <body>
        <div class="pagewrap">
            <div class="orginfo">NORGES TEKNISKE-NATURVITENSKAPLIGE UNIVERSITET</div>
            <div id="topp">
                <img src="/img/BAS_ntnu_logo.png" alt="NTNU" />
            </div>
            <div id="page">
                <h1>''' + _('NTNU&apos;s database for administering user accounts') + '''</h1>
                <div class="text">
                    <a href="/passwd/index">''' + _('Change password for an existing user account') + '''
                    </a>
                </div>
                <div class="text">
                    <a href="/activation/index">
                        ''' + _('Activate your user account at NTNU') + '''
                    </a>
                </div>
                <br /><br />
                <div class="text">
                    ''' + choose_lang(lang) + '''
                </div>
            </div>
        </div>
    </body>
</html>'''
index.exposed = True

def choose_lang(lang):
    if lang == 'en':
        return '<a href="/?lang=no"><img src="/img/norsk_flagg50.gif" alt="Norsk" /></a>'
    return  '<a href="/?lang=en"><img src="/img/uk-flag50.gif" alt="English"/></a>'
