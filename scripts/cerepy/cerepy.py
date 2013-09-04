#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Changelog:
#     Jo Sama <jo.sama@usit.uio.no>, before July 2013
#     Alexander Rødseth <rodseth@usit.uio.no>, July 2013
#

# General imports
import rlcompleter
import readline
import code
from mx import DateTime

# Cerebrum-related imports
import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules import CLHandler

# Make Tab support both indentation and completion
readline.parse_and_bind("tab: complete")

class MyCompleter(rlcompleter.Completer):

    def complete(self, text, state):
        if text.lstrip() == '':
            if state == 0:
                return text + '\t'
            else:
                return None
        else:
            return rlcompleter.Completer.complete(self, text, state)

readline.set_completer(MyCompleter().complete)

# Write some information about what's happening
keywordcolor = "\033[94m"
textcolor = "\033[37m"
msg = """\033[92mCurrent session:\n\033[0m
    import cerebrum_path, cereconf
    from Cerebrum.Utils import Factory
    from Cerebrum import Errors
    from Cerebrum.modules import CLHandler
    db = Factory.get('Database')()
    cl = CLHandler.CLHandler(db)
    db.cl_init(change_program='cereutvsh')\n"""
msg = msg.replace("import", keywordcolor + "import" + textcolor)
msg = msg.replace("from", keywordcolor + "from" + textcolor)
print(textcolor + msg + "\033[0m")

# Get db and init cl
db = Factory.get('Database')(client_encoding='utf-8')
cl = CLHandler.CLHandler(db)
db.cl_init(change_program='cereutvsh')

# Define variablenames and classes
# This can potentially be used to autopopulate a
# variable, as part of an auto-text-config-environment thing
attrs = {'en': 'Entity',
         'pe': 'Person',
         'di': 'Disk',
         'co': 'Constants',
         'ac': 'Account',
         'ou': 'OU',
         'gr': 'Group',
         'pu': 'PosixUser',
         'pg': 'PosixGroup'}
inited = {}
shortvarcolor = "\033[95m"
textcolor = "\033[94m"
classnamecolor = "\033[97m"
for x in attrs:
    try:
        inited[x] = Factory.get(attrs[x])(db)
    except ValueError, e:
        print("\033[1;31m    %s\033[0;37m" % e)
    except ImportError, e:
        print("\033[1;31m    %s\033[0;37m" % e)
    finally:
        msg = textcolor + "    %s = Factory.get(%s)(db)\033[0m" % (
            x, attrs[x])
        msg = msg.replace(
            attrs[x],
            classnamecolor + "'" + attrs[x] + "'" + "\033[0m", 1)
        msg = msg.replace(x, shortvarcolor + x + "\033[0m", 1)
        print(msg)

locals().update(inited)

# TODO: Use a loop or filter that only keeps some values instead
del inited
del attrs
del shortvarcolor
del textcolor
del classnamecolor
del msg
del keywordcolor
del x

# Color of the Python information text that follows
print("\033[90m")

# This lines are for getting a colored prompt.
# Note that the control characters for changing the colors are
# between \001 and \002. \001 and \002 lets readline ignore
# the characters that are in between. 
code.sys.ps1 = '\001\033[1;93m\002>>>\001\033[0;37m\002 '
code.sys.ps2 = '\001\033[1;95m\002...\001\033[0;37m\002 '

# Start the interactive session
code.interact(local=locals())
