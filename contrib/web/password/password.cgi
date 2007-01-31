#! /usr/bin/env python
# -*- mode: python; coding: iso-8859-1; -*-

########################################################################

# Copyright 2002, 2003, 2004 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

# $Id$

__doc__ = """
Script for changing a user's password using a web based interface.

It uses the web page .template_<language>.html as a template, in
which ##Part## parts are replaced with the text for Part.

Requirements:
  python2.2 or later, Python-module M2Crypto, OpenSSL 0.9.7 or later.
  Compilation of M2Crypto requires Swig.  M2Crypto's installation
  instructions currently include strange maneuvers such as to edit
  an installed Python library.  The edit can be reverted afterwards.

Installation:
  - If M2Crypto is not installed, it may be installed below a subdirectory
    'python/' of the same directory as where this script resides.
    (See the statement which updates sys.path.)
  - Regularly rotate the log file with a crontab job which does
       password.cgi --log-rotate=<max number of saved logfile>
  - Since config() does umask(007), if you do
       chown <web server user>.<cerebrum admininstrator group>
    on <work_dir> and its files, followed by
       chmod ug=rwx,g+s <work_dir>
       chmod ug+rw      <files in work_dir>
    then both the web server and the cerebrum administrators can
    read and write the files.  The 's' permission on <work_dir>
    ensures that new files in that directory will get the same group
    as the directory itself.

httpd environment variables used, with an example
for the URL https://www.uio.no/cgi-bin/password.cgi?lang=en:
  REQUEST_URI (example: '/cgi-bin/password.cgi?lang=en'),
  SCRIPT_NAME (example: '/cgi-bin/password.cgi'),
  SERVER_NAME (example: 'www.uio.no'),
  and if present: HTTP_ACCEPT_LANGUAGE (example: 'no-bok, no, en').

Testing from the command line:
  Options:
    --<uname/pass/newpass/newpass2/lang>=<value> - CGI fields.
    --tester=<username> - where to mail any error messages.  Otherwise
                          mails are written to standard output.
    --full              - do not omit any HTML verbosity
  Environment variables:
    $BOFH_URL, $CACERT_FILE.  Used to test with another bofhd server.
    A $BOFH_URL starting with 'http:' gives an unencrypted connection,
    'https:' gives an encrypted connection.

Known bugs:
  In the Accept-Language: HTTP header, '*' is not implemented
  and the language tag quality is not computed quite right.

"""

date_created = '2007-01-05'
date_modified = '$Date$'[7:17].replace('/', '-')


########################################################################
#
# Program
#
import os
import re
import sys
import time
import cgi
import xmlrpclib
import socket

# Path where M2Crypto is installed if not installed with Python:
# the python/ directory below the directory containing this script.
sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[0]), 'python'))

from M2Crypto import SSL
from M2Crypto.m2xmlrpclib import Server, SSL_Transport

import password_config as config
import lang

# umask for new files (log file etc.)
os.umask(007)	# full access for owner & group, no access for others


# General functions
def status(level = -1, action = -1, msg = -1):
    if level != -1:
        status.level = level
    if action != -1:
        status.action = action
    if msg != -1:
        status.msg = msg


def rev_date(date):
    """Translate yyyy-mm-dd date to dd.mm.yyyy"""
    return date[8:10] + '.' + date[5:7] + '.' + date[0:4]


def sendmail(message):
    if command_line_mode > 1:
        sys.stdout.write(message)
    else:
        mail = os.popen(config.SENDMAIL_CMD, 'w')
        mail.write(message)
        mail.close()


def get_language():
    form_language = form.getfirst('lang')
    if form_language:
        langs = (form_language.lower() + '-',)
    else:
        try:
            score = 5.0
            langs = []
            for language in (os.environ['HTTP_ACCEPT_LANGUAGE']
                         .lower().replace(',', ' ').split()):
                language = language.split(';q=') + [1.0]
                langs.append((score - float(language[1]), language[0] + '-'))
                score += 0.000001
            langs.sort()
            langs = [language[1] for language in langs]
        except:
            langs = ()
    supported = [(language.lower() + '-', s[1])
                 for s in lang.supported_languages for language in s[1:]]
    for language in langs:
        for s in supported:
            if s[0].startswith(language):
                return s[1]
    return supported[0][1]


def get_html_top_bottom():
    """Get top and bottom of HTML page from template"""
    template = ''
    if not config.TEMPLATE_URL_PREFIX is None:
        template_URL = config.TEMPLATE_URL_PREFIX + language + '.html'
        host, localpart = template_URL.split('/', 3) [2:4]
        try:
            import httplib
            h = httplib.HTTP(host)
            h.putrequest('GET', '/' + localpart)
            h.putheader('Host', host)
            h.endheaders()
            errcode, errmsg, headers = h.getreply()
            if errcode == 200:
                f = h.getfile()
                template = f.read().strip()
                f.close()
            elif config.WWW_ADMIN:
                sendmail(text.bad_template_mail %
                         (config.WWW_ADMIN, self_URL,
                          template_URL, errcode, errmsg))
        except:
            pass
    if template == '':
        template = text.default_webpage_template % text.template_params
    return (template
            .replace('8888-88-88', date_created)
            .replace('9999-99-99', date_modified)
            .replace('88.88.8888', rev_date(date_created))
            .replace('99.99.9999', rev_date(date_modified))
            .replace('##TITLE##', text.title)
            .replace('##KEYWORDS##', text.webpage_keywords)
            .replace('##EDITOR.NAME##', config.EDITOR_NAME)
            .replace('##EDITOR@EMAIL##', config.EDITOR_EMAIL)
            .split('##BODY##', 1))


# Extract from Cerebrum/modules/bofhd/xmlutils.py:native_to_xmlrpc()
def bofh_encode(obj):
    """Translate Python string to bofhd-XML-RPC string"""
    if obj.startswith(":"):
        return ":" + obj
    return obj


def call_bofhd(request_handler, uname, password):
    """Call bofhd and print the results."""

    try:
        if config.BOFH_URL.startswith('https:'):
            # Seed PRNG if necessary
            if not os.path.exists('/dev/random'):
                from M2Crypto.Rand import rand_add
                rand_file = os.popen(config.RANDOM_DATA_CMD, 'r')
                rand_string = rand_file.read()
                rand_file.close()
                rand_add(rand_string, len(rand_string))
            # Log in and handle request
            ctx = SSL.Context('sslv3')
            ctx.load_verify_info(config.CACERT_FILE)
            ctx.set_verify(SSL.verify_peer, 10)
            status(action = 'connect')
            svr = Server(config.BOFH_URL, SSL_Transport(ctx),
                         encoding='iso8859-1')
        else:
            status(action = 'connect')
            svr = xmlrpclib.Server(config.BOFH_URL, encoding='iso8859-1')
        status(action = 'login')
        secret = svr.login(bofh_encode(uname), bofh_encode(password))
        request_handler(svr, secret, uname)

    except xmlrpclib.Fault, m:
        if m.faultString.startswith('Cerebrum.modules.bofhd.errors.'):
            bofh_error = m.faultString.split(':', 1)[1]
            if isinstance(bofh_error, unicode):
                bofh_error = bofh_error.encode("ISO-8859-1")
            print "<hr>\n%s\n<p>%s:</p>" % (text.not_success,
                                            text.operation_failed)
            print ("<FONT SIZE=+1><blockquote><p>%s</p></blockquote></FONT>" %
                   cgi.escape(bofh_error))
            print "<p>%s</p>" % text.probably_try_again
            status(level = 'warning', msg = bofh_error.replace("\n", "\n  "))
        else:
            status(level = 'error',
                   msg = "xmlrpclib: " + m.faultString.replace("\n", "\n  "))

    except SSL.SSLError, m:
        ssl_error = str(m)
        if config.CERT_WARN and ssl_error == 'certificate verify failed':
            # Warn via mail if more than 1 day since last warning
            try:
                if (os.stat(config.CERT_WARNED_FILE)[8] <
                    (time.time() - config.CERT_WARN_FREQUENCY)):
                    raise OSError # presumably CERT_WARNED_FILE does not exist
            except OSError:
                try:
                    open(config.CERT_WARNED_FILE, 'w').close()
                    if command_line_mode:
                        vars = ()
                    else:
                        vars = os.environ.keys()
                        vars.sort()
                    sendmail(text.wrong_certificate_mail %
                             (config.CERT_WARN, self_URL,
                              self_URL, config.BOFH_URL,
                              config.CACERT_FILE,
                              config.CERT_WARNED_FILE,
                              sys.argv[0], uname,
                              "".join(["%s=%s\n" % (v, os.environ[v])
                                       for v in vars])))
                except:
                    pass
        status(level = 'error', msg = "SSL: " + ssl_error)

    except socket.error, m:
        status(level = 'error', msg = "socket.error" + str(m))

    except IOError, m:
        status(level = 'error', msg = "IOError " + str(m))


# Functions to parse and handle the request

def handle_request():
    print "Content-type: text/html\n"

    if not config.BOFH_URL.startswith('https:'):
        if command_line_mode:
            print text.cmdline_bofh_URL_not_https
        else:
            print text.http_bofh_URL_not_https
            return

    html_top, html_bottom = get_html_top_bottom()
    print html_top
    status(level = 'critical', action = 'init', msg = "Unhandled exception:")
    try:
        os.stat(config.DOWNTIME_FLAGFILE)
        output_down_message()
        status(level = 'info', action = 'success', msg = None)
        print html_bottom
        return
    except OSError:
        # No flag file for downtime.  That's good.
        pass
    try:
        if not form.getfirst('action'):
            status(action = 'intro')

            print "\n".join(
                ['<div>']
                + ['[<a href="%s?lang=%s">%s</a>]' % (script_name, s[1], s[0])
                   for s in lang.supported_languages if s[1] != language]
                + ['</div>'])
            print text.start_body % {"sitename": text.sitename,
                                     "password_spread_delay": text.password_spread_delay,
                                     "additional": text.additional_info_for_start_page}
            print text.password_form % (cgi.escape(script_name, True),
                    text.uname, text.passw,
                    text.newpass, text.newpass2,
                    language, text.change, text.pw_now)
            status(level = None)
        else:
            status(action = 'check_fields')
            if not check_fields():
                print "<p>%s</p>" % text.try_again
                status(level = None)
            else:
                call_bofhd(logged_in,
                           form.getfirst('uname'), form.getfirst('pass'))
    finally:
        if status.level != None:
            if status.level in ('error', 'critical'):
                print (("<hr>\n%s\n<p>" + text.try_again_later_fmt + "</p>")
                       % (text.not_success, config.BUGREPORT_ADDR,
                          config.BUGREPORT_ADDR, text.status_webpage_string))

            # Log the request
            try:
                if config.LOG_FILE:
                    # Write both log items and exceptions to LOG_FILE
                    sys.stderr = file(config.LOG_FILE, "a", 0)
                else:
                    raise IOError
                prog = None
            except IOError:
                prog = sys.argv[0]
            password = form.getfirst(
                ('pass', 'newpass')[status.action != 'login'])
            if password:
                status.action += ", %d-char password" % len(password)
                if re.search('[^!-~]', password):
                    status.action += " with bad characters"
            sys.stderr.write("[%s] [%s] %s\n" % (time.ctime(), status.level,
                ": ".join(filter(None, (prog, form.getfirst('uname', '-'),
                                        status.action, status.msg)))))

        print html_bottom


def check_fields():
    pre = "<hr>\n"
    error = ""
    for k in 'uname', 'pass', 'newpass', 'newpass2':
        field = form.getfirst(k)
        if not field:
            error += "<p>" + (text.empty_field_fmt %
                              getattr(text, k)) + "</p>\n"
        else:
            found = re.sub('[!-~]+', '', field)
            if found:
                found = ", ".join(map(lambda c:
                                      "'<tt>%s</tt>'" % cgi.escape(c),
                                      found))
                print pre, ("<p>"
                            + (text.badchar_field_fmt %
                               (found, getattr(text, k)))
                            + "</p>")
                pre = ""
    if not error and form.getfirst('newpass') != form.getfirst('newpass2'):
        error = "<p>%s</p>\n" % text.new_password_mismatch
    if error:
        print "%s%s\n%s" % (pre, text.not_success, error)
    return not error


def logged_in(svr, secret, uname):
    status(action = 'change')
    svr.run_command(secret, 'user_password',
                    bofh_encode(uname),
                    bofh_encode(form.getfirst('newpass')))
    thank_you_text = text.thank_you % {"password_spread_delay":
                                       text.password_spread_delay}
    print "<hr>\n<p>%s</p>" % thank_you_text
    status(level = 'info', action = 'success', msg = None)


def output_down_message():
    try:
        message_file = config.DOWNTIME_FLAGFILE + "." + language
        os.stat(message_file)
    except OSError:
        message_file = config.DOWNTIME_FLAGFILE
    print "".join(open(message_file).readlines())


########################################################################
#
# Administration
#
def log_rotate(top):
    import errno
    suffixes = [""] + map(lambda n: "-%d" % n, range(0, top + 1))
    for i in range(top, -1, -1):
        if os.path.exists(config.LOG_FILE + suffixes[i]):
            try:
                os.rename(config.LOG_FILE + suffixes[i],
                          config.LOG_FILE + suffixes[i+1])
            except OSError, e:
                sys.exit("%s%s or %s: %s" %
                         (config.LOG_FILE, suffixes[i], suffixes[i+1], e))


########################################################################
#
# Run
#
try:
    command_line_mode = 0
    script_name = os.environ['SCRIPT_NAME']
    self_URL = 'https://'+os.environ['SERVER_NAME']+os.environ['REQUEST_URI']
except KeyError:
    command_line_mode = 2
    script_name = os.path.basename(sys.argv[0])
    self_URL = "test://test/" + script_name
    class fake_cgi_FieldStorage(dict):
        getfirst = dict.get
    form = fake_cgi_FieldStorage()#{ 'action': True })
    import getopt
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], '', ('log-rotate=',
                               'full', 'tester=', 'action=', 'lang=',
                               'uname=', 'pass=', 'newpass=', 'newpass2='))
        if args:
            raise getopt.GetoptError("non-option argument(s) given", None)
        for opt, val in opts:
            form[opt[2:]] = val
    except getopt.GetoptError, err:
        sys.exit(err)
else:
    form = cgi.FieldStorage()

language = get_language()
text = lang.get_text_by_language(language)

if command_line_mode:
    if 'log-rotate' in form:
        log_rotate(int(form['log-rotate']))
        sys.exit(0)
    if 'BOFH_URL' in os.environ:
        config.BOFH_URL = os.environ['BOFH_URL']
    if 'CACERT_FILE' in os.environ:
        config.CACERT_FILE = os.environ['CACERT_FILE']
    if form.getfirst('tester'):
        command_line_mode = 1
        if config.WWW_ADMIN:
            config.WWW_ADMIN = form['tester']
        if config.CERT_WARN:
            config.CERT_WARN = form['tester']
    if not 'full' in form:
        config.TEMPLATE_URL_PREFIX = None
        text.start_body = ''

handle_request()
