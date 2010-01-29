import time
import cherrypy

from gettext import gettext as _

import cerebrum_path
import cereconf

from lib.Main import Main
from lib.utils import is_correct_referer, get_referer_error
from lib import utils
from lib.templates.UserTemplate import UserTemplate
from Cerebrum.Utils import Factory
from lib.data.AccountDAO import AccountDAO
from Cerebrum.modules.PasswordChecker import PasswordGoodEnoughException

def index():
    template = UserTemplate()
    template.messages = []
    return template.respond()
index.exposed = True

def savepw(**vargs):
    logger = Factory.get_logger("root")
    remote = cherrypy.request.headerMap.get("Remote-Addr", '')

        
    template = UserTemplate()
    template.messages = []

    if not is_correct_referer():
        template.messages.append(get_referer_error())
        template.respond()
    uname = vargs.get('username', '')
    oldpwd = vargs.get('oldpassword', '')
    pwd1 = vargs.get('password1', '')
    pwd2 = vargs.get('password2', '')
    if not uname:
        template.messages.append('No username.')
        return template.respond()
    if not oldpwd:
        template.messages.append('No password.')
        return template.respond()
    if not pwd1 or not pwd2:
        template.messages.append('Passwords do not match.')
        return template.respond()
    if pwd1 and pwd2 and pwd1 != pwd2:
        template.messages.append('Passwords do not match.')
        return template.respond()
    if pwd1 and pwd2 and pwd1 == pwd2 and len(pwd1) < 8:
        template.messages.append('Passwords too short (min. 8 characters).')
        return template.respond()

    try:
        db = Factory.get("Database")()
        db.cl_init(change_program="set_password")
        const = Factory.get("Constants")(db)
        method = const.auth_type_md5_crypt

        acc = Factory.get("Account")(db)
        acc.clear()
        acc.find_by_name(uname)
        hash = acc.get_account_authentication(method)

        if not acc.verify_password(method, oldpwd, hash):
            logger.warn('Login failed for ' + uname + '. Remote-addr = ' + remote)
            db.rollback()
            raise Exception('Login failed.')
        try:
            acc.set_password(pwd1)
        except PasswordGoodEnoughException, e:
            # password not good enough
            template.messages.append('Password not good enough.' + \
                '  Try to make a stronger password.')
            db.rollback()
            return template.respond()
        try:
            acc.write_db()
        except Exception, e:
            template.messages.append('The server is unavailable.')
            template.messages.append('If the server remains ' + \
                ' unavailable, call (735) 91500 and notify ' + \
                'Orakeltjenesten of the situation.')
            logger.err(e)
            db.rollback()
            return template.respond()
        try:
            db.commit()
        except Exception, e:
            template.messages.append('The server is unavailable.')
            template.messages.append('If the server remains ' + \
                'unavailable, call (735) 91500 and notify ' + \
                'Orakeltjenesten of the situation.')
            logger.err(e)
            db.rollback()
            return template.respond()
    except Exception, e:
        template.messages.append('Login failed.')
        return template.respond()
    # i do not know if this is necessary...
    cherrypy.session.clear()
    logger.warn(uname + ' has changed password.  Remote-addr = ' + remote)
    template.messages.append('Password is changed!')
    return template.respond()
savepw.exposed = True
