#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2002 University of Oslo, Norway
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

import getopt
import getpass
import logging
import os
import readline
import signal
import sys
import threading
import xmlrpclib
from mx import DateTime

VERSION = "0.0.1"
logger = None


class AnalyzeCommandException(Exception):
    pass


class QuitException(Exception):
    pass


class BofhdException(Exception):
    pass


class ParseException(Exception):
    pass


class CommandLine(object):
    """Responsible for reading commands from stdin, and splitting them
    into seperate arguments"""

    def __init__(self, completer, default_prompt, max_timeout=None,
                 warn_delay=None):
        self._completer = completer
        self._default_prompt = default_prompt
        self.__max_timeout = max_timeout
        self.__warn_delay = warn_delay
        self.__timer_wait = None
        self.my_pid = os.getpid()
        self.__quit = False

    def __got_alarm(self, *args):
        self.__alarm_count += 1
        if self.__alarm_count > 1 or self.__warn_delay is None:
            print "Terminating program due to inactivity"
            self.__quit = True
            os.kill(self.my_pid, signal.SIGINT)
            return
        print "Session about to timeout, press enter to cancel"
        self.__set_alarm(self.__warn_delay)

    def __set_alarm(self, delay):
        # Pythons signal.alarm doesn't play well with raw_input() when
        # connected to readline, so we must use threads instead
        if self.__timer_wait is not None:
            self.__timer_wait.cancel()
        self.__timer_wait = threading.Timer(delay, self.__got_alarm)
        self.__timer_wait.setDaemon(True)
        self.__timer_wait.start()

    def prompt_arg(self, msg, default=None, postfix=''):
        """Prompt for a string, optionally returning a default value
        if user enters an empty string"""

        self.__alarm_count = 0
        self.__set_alarm(self.__max_timeout)

        if(default is not None):
            msg = "%s [%s]" % (msg, default)
        if postfix:
            msg = msg + postfix
        ret = ''
        while ret == '':
            try:
                ret = raw_input(msg)
            except Exception:
                if self.__quit:
                    raise QuitException
                logger.debug("Some exception")
                self.__timer_wait.cancel()
                raise
            if(ret == '' and default is not None):
                ret = default
        self.__timer_wait.cancel()
        return ret

    def prompt_password(self, msg):
        return getpass.getpass(msg)

    def split_command(cmd):
        """Split string into tokens, using whitespace as delimiter.
        Matching '/\" pairs can be used to include whitespace in the
        tokens.  Sub-groups marked by matching parenthesis are
        returned as sub-vectors. Sub-sub groups are not allowed."""

        ret = cur_app = []
        quote = sub_cmd = None
        pstart = 0
        cmd = cmd + ' '
        for i in range(len(cmd)):
            char = cmd[i]
            if quote is not None:
                if char == quote:
                    if i >= pstart:
                        cur_app.append(cmd[pstart:i])
                    pstart = i + 1
                    quote = None
            else:
                if char in ('"', "'"):
                    pstart = i+1
                    quote = char
                elif char in (' ()'):
                    if i > pstart:
                        cur_app.append(cmd[pstart:i])
                    pstart = i+1
                    if char == ')':
                        if sub_cmd is None:
                            raise ParseException(") with no (")
                        ret.append(cur_app)
                        cur_app = ret
                        sub_cmd = None
                    elif char == '(':
                        if sub_cmd is not None:
                            raise ParseException("nested paranthesis detected")
                        sub_cmd = []
                        cur_app = sub_cmd
        if quote is not None:
            raise ParseException("Missing end-quote")
        if sub_cmd is not None:
            raise ParseException("Missing end )")
        return ret
    split_command = staticmethod(split_command)

    def get_splitted_command(self):
        """The main prompt.  We only enable tab-completion here."""

        # TODO: we don't want sub-prompts to generate history entries,
        # but deletion of history entries is only supported in python
        # >= 2.4.  Is there any way around this?  Can history in
        # readline be disabled?  Looking Modules/readline.c indicates
        # that it can't

        old_completer = readline.get_completer()
        readline.parse_and_bind('tab: complete')
        readline.set_completer(self._completer.tab_complete)
        try:
            ret = CommandLine.split_command(
                self.prompt_arg(self._default_prompt))
        except Exception:
            raise
        readline.parse_and_bind('tab: rl_insert')
        readline.set_completer(old_completer)
        return ret


class BofhCompleter(object):
    """Handles tab-completion, and allows short-forms of commands"""

    def __init__(self):
        self._complete = {}

    def clear(self):
        self._complete.clear()

    def add_completion(self, cmd_def, proto_cmd):
        """Register completion for cmd_def = (user_cmds, proto_args),
        and point to apropriate protocol command"""
        tgt_dict = self._complete
        for i in range(len(cmd_def[0])):
            if i == len(cmd_def[0]) - 1:
                tgt_dict[cmd_def[0][i]] = proto_cmd
            else:
                tgt_dict = tgt_dict.setdefault(cmd_def[0][i], {})

    def _find_matches_at(self, args, tgt_lvl):
        """Find matching commands at this argument number"""
        if len(args) > 2:
            raise AnalyzeCommandException("no matches")

        tmp_dict = self._complete
        lvl = 0
        for n in range(len(args)):
            a = args[n]
            logger.debug("TK %s: %s" % (a, repr(tmp_dict.keys())))
            matches = filter(lambda c: c.startswith(a), tmp_dict.keys())
            logger.debug("M (%i, %i): %s" % (tgt_lvl, lvl, matches))
            if a in matches:
                matches = [a]
            if tgt_lvl != lvl and len(matches) > 1:
                raise AnalyzeCommandException("Too many matches: %s" % matches)
            if not matches:
                raise AnalyzeCommandException("Unknown command %s" % a)
            tmp_dict = tmp_dict[matches[0]]
            if tgt_lvl == lvl:
                return matches
            if not isinstance(tmp_dict, dict):
                logger.debug("E: %s" % repr(tmp_dict))
                return []
            lvl += 1
        return []

    def tab_complete(self, text, state):
        """Called by readline to handle tab-completion."""

        # readline will call this function with state=0..n until we
        # return None indicating no more matches.  I.e. we should only
        # check for matches when state=0, and cache the results for
        # answering the next calls.  See the gnu-readline (C-version)
        # docs for details

        line = readline.get_line_buffer()
        endidx = readline.get_endidx()

        args = CommandLine.split_command(line[:endidx])
        if state == 0:
            try:
                lvl = len(args) - 1
                if endidx > 0 and line[endidx-1] == ' ':
                    lvl += 1
                    args.append('')
                self.__matches = self._find_matches_at(args, lvl)
            except AnalyzeCommandException:
                return None
            except Exception:
                logger.error("Unexpected tab-complete exception", exc_info=1)
        try:
            if state == len(self.__matches)-1:
                # The readline doc su**s.  This ugly hack aparently
                # makes appending a space to the match work.
                return self.__matches[state] + ' '
            return self.__matches[state]
        except IndexError:
            return None

    def analyze_command(self, args):
        """Expands unique short-forms of the first entries in args to
        their full names"""
        tmp_dict = self._complete
        for n in range(len(args)):
            a = args[n]
            matches = filter(lambda c: c.startswith(a), tmp_dict.keys())
            if a in matches:
                matches = [a]
            if len(matches) > 1:
                raise AnalyzeCommandException("Too many matches: %s" % matches)
            if not matches:
                raise AnalyzeCommandException("Unknown command %s" % a)
            tmp_dict = tmp_dict[matches[0]]
            if not isinstance(tmp_dict, dict):
                break
        if isinstance(tmp_dict, dict):
            raise AnalyzeCommandException("Incomplete command")
        return tmp_dict, args[n+1:]


class BofhConnection(object):
    """Handles all communication with remote server"""

    def __init__(self, url, bofh_client, cacert_file=None, rand_cmd=None):
        self.__bc = bofh_client
        if url.startswith("https"):
            from M2Crypto.m2xmlrpclib import Server, SSL_Transport
            from M2Crypto import SSL
            if not os.path.exists('/dev/random') and rand_cmd is not None:
                from M2Crypto.Rand import rand_add
                rand_file = os.popen(rand_cmd, 'r')
                rand_string = rand_file.read()
                rand_file.close()
                rand_add(rand_string, len(rand_string))
            ctx = SSL.Context('sslv3')
            if cacert_file is not None:
                ctx.load_verify_info(cacert_file)
                ctx.set_verify(SSL.verify_peer, 10)
            self.conn = Server(url, SSL_Transport(ctx), encoding='iso8859-1')
        else:
            self.conn = xmlrpclib.Server(url, encoding='iso8859-1')

    def get_format_suggestion(self, cmd):
        return self.__send_raw_command("get_format_suggestion", [cmd])

    def get_help(self, args):
        return self.__auth_cmd("help", args)

    def get_motd(self, version):
        return self.__send_raw_command("get_motd", ("pybofh", version))

    def login(self, uname, password):
        self.__sessid = self.__send_raw_command("login", (uname, password))
        self.update_commands()

    def logout(self):
        return self.__auth_cmd("logout")

    def update_commands(self):
        self.commands = self.__auth_cmd("get_commands")

    def prompt_func(self, cmd, *args):
        tmp = [cmd]
        if args:
            tmp.extend(args)
        return self.__auth_cmd("call_prompt_func", tmp)

    def run_command(self, cmd, *args):
        tmp = [cmd]
        if args:
            tmp.extend(args)
        return self.__auth_cmd("run_command", tmp)

    def __auth_cmd(self, func_name, args=None):
        tmp = [self.__sessid]
        if args:
            tmp.extend(args)
        logger.debug("X: %s %s" % (repr(args), repr(tmp)))
        return self.__send_raw_command(func_name, tmp, sessid_loc=0)

    def __send_raw_command(self, cmd, args, sessid_loc=None,
                           got_restart=False):
        """Send the command to the server, and recognize and handle
        some common errors"""
        assert isinstance(args, (list, tuple))
        if True:
            # We don't want to log plaintext passwords
            # TBD: Is this really neccesary?  debuging has to be enabled
            # explicitly any way
            if cmd == 'login':
                logger.debug("-> %s(%s)" % (cmd, '************'))
            elif cmd == 'run_command':
                cmd_def = self.commands[args[1]]
                tmp = args[:]
                logger.debug("CD: %s" % repr(cmd_def))
                if len(cmd_def) > 1 and isinstance(cmd_def[1], (tuple, list)):
                    for i in range(len(cmd_def[1])):
                        if cmd_def[1][i]['type'] == 'accountPassword':
                            tmp[i] = '**********'
                logger.debug("-> %s(%s)" % (cmd, repr(tmp)))
            else:
                logger.debug("-> %s(%s)" % (cmd, repr(args)))
        else:
            logger.debug("-> %s(%s)" % (cmd, repr(args)))

        args = self.__wash_command_args(args)
        try:
            r = getattr(self.conn, cmd)(*args)
            logger.debug("<- %s" % repr(r)[:30])
            return self.__wash_response(r)
        except xmlrpclib.Fault, m:
            logger.debug("F: '%s'" % m.faultString)
            match = "Cerebrum.modules.bofhd.errors."
            if (not got_restart and
                    m.faultString.startswith(match+"ServerRestartedError")):
                self.update_commands()
                self.__bc.notify_restart()
                return self.__send_raw_command(cmd, args, got_restart=True)
            elif m.faultString.startswith(match+"SessionExpiredError"):
                self.__bc.show_message("Session expired, you must "
                                       "re-authenticate")
                self.__bc.login()
                if sessid_loc is not None:
                    args[sessid_loc] = self.__sessid
                return self.__send_raw_command(cmd, args)
            elif m.faultString.startswith(match):
                raise BofhdException(
                    "Error: %s" % m.faultString[m.faultString.find(":")+1:])
            else:
                raise BofhdException(
                    "Unexpected error: %s" % m.faultString)

    def __wash_command_args(self, args):
        """Handle out extensions to xml-rpc"""
        def check_safe_str(string):
            for c in string:
                c = ord(c)
                if not (c >= 0x20 or c in (0x9, 0xa, 0xd)):
                    raise BofhdException("Illegal character: %i" % c)
        ret = []
        for a in args:
            if isinstance(a, (tuple, list)):
                tmp = []
                for a2 in a:
                    if a2.startswith(":"):
                        a2 = ":" + a2
                    check_safe_str(a2)
                    tmp.append(a2)
                ret.append(tmp)
            else:
                if isinstance(a, (str, unicode)):
                    check_safe_str(a)
                ret.append(a)
        return ret

    def __wash_response(self, obj):
        """Handle out extensions to xml-rpc"""
        if isinstance(obj, (list, tuple)):
            return [self.__wash_response(i) for i in obj]
        elif isinstance(obj, (str, unicode)):
            if len(obj) > 0 and obj[0] == ':':
                obj = obj[1:]
                if obj == 'None':
                    obj = '<not set>'
            if isinstance(obj, unicode):
                return obj.encode('iso8859-1')
            return obj
        elif isinstance(obj, dict):
            ret = {}
            for k, v in obj.items():
                ret[k] = self.__wash_response(v)
            return ret
        else:
            return obj


class BofhClient(object):
    """The actual client, running main_loop until termination"""

    def __init__(self, url, uname, password=None, **kwargs):
        self.uname = uname
        self.bc = BofhConnection(url, self, cacert_file=kwargs['cacert_file'],
                                 rand_cmd=kwargs['rand_cmd'])
        self.completer = BofhCompleter()
        self.cline = CommandLine(
            self.completer, kwargs['console_prompt'],
            max_timeout=kwargs['IdleTerminateDelay'],
            warn_delay=kwargs['IdleWarnDelay'])
        self.login(password=password)
        self.show_message(self.bc.get_motd(VERSION))
        self.show_message(
            'Welcome to pybofh, v%s, type "help" for help' % VERSION)
        self.main_loop()

    def login(self, password=None):
        if password is None:
            password = self.cline.prompt_password("Password:")
        self.bc.login(self.uname, password)
        self.notify_restart()

    def notify_restart(self):
        self.__update_completer()

    def __update_completer(self):
        self._known_formats = {}
        self.completer.clear()
        for proto_cmd, cmd_def in self.bc.commands.items():
            self.completer.add_completion(cmd_def, proto_cmd)
        self.completer.add_completion([["help"]], None)
        self.completer.add_completion([["source"]], None)

    def main_loop(self):
        while True:
            try:
                self.process_cmd_line()
            except QuitException:
                break
            except Exception, msg:
                self.show_message("Unexpected error (bug): %s" % msg)
                logger.error("Exception", exc_info=1)
        self.show_message("Bye")
        self.bc.logout()

    def process_cmd_line(self):
        """Reads command from the user, and runs it"""
        try:
            args = self.cline.get_splitted_command()
        except ParseException, msg:
            self.show_message("Bad command: %s" % msg)
            return
        except EOFError:
            raise QuitException
        try:
            self.run_command(args)
        except BofhdException, msg:
            self.show_message(msg)
        except QuitException:
            raise
        except EOFError:
            pass  # User aborted command
        except Exception:
            self.show_message("Unexpected error")
            logger.error("Unexpected exception", exc_info=1)

    def run_command(self, args, sourcing=False):
        """Runs the given command, starting prompt-mode if command is
        incomplete"""
        logger.debug("run_command(%s)" % repr(args))
        if args[0] == 'commands':
            self.show_message("".join(
                ["%s->%s\n" % k for k in self.bc.commands.items()]))
        elif args[0] == 'quit':
            raise QuitException
        elif args[0] == 'source':
            self.source_file(args[1])
        elif args[0] == 'help':
            self.show_message(self.bc.get_help(args[1:]))
        else:
            try:
                bofh_cmd, bofh_args = self.completer.analyze_command(args)
            except AnalyzeCommandException, msg:
                self.show_message(msg)
                return
            if not sourcing:
                bofh_args = self.check_args(bofh_cmd, bofh_args)
            logger.debug("Checked to %s" % repr(bofh_args))
            resp = self.bc.run_command(bofh_cmd, *bofh_args)
            if resp is not None:
                multiple_cmds = False
                if filter(lambda x: isinstance(x, (tuple, list)), bofh_args):
                    multiple_cmds = True
                self.show_response(bofh_cmd, resp, multiple_cmds)

    def source_file(self, fname):
        for line in open(fname, "r").readlines():
            line = line.strip()
            if not line or line[0] == '#':
                continue
            self.show_message("%s%s" % (self.cline._default_prompt, line))
            args = CommandLine.split_command(line)
            self.run_command(args, sourcing=True)

    def check_args(self, cmd, args):
        """Verify that the command is complete, using prompting to
        complete it if needed."""
        cmd_def = self.bc.commands[cmd]
        logger.debug("check_args for %s" % repr(cmd_def))
        if len(cmd_def) == 1:
            return args
        if cmd_def[1] == 'prompt_func':
            return self.process_server_command_prompt_function(cmd, args)
        ret = args
        if len(args) >= len(cmd_def[1]):
            return ret
        i = len(args)
        while i < len(cmd_def[1]):
            pspec = cmd_def[1][i]
            if int(pspec.get("optional", 0)) == 1:
                break
            defval = pspec.get("default", None)
            if isinstance(defval, (int, bool)):
                # TODO: This isn't used, and doesn't seem to work in
                # jbofh either
                defval = self.bc.get_default_param(ret)
            param_type = pspec.get("type", None)
            if param_type == "accountPassword":
                tmp_arg = self.cline.prompt_password(pspec['prompt'])
            else:
                tmp_arg = self.cline.prompt_arg(pspec['prompt'], defval,
                                                postfix='> ')
            if tmp_arg == '?':
                self.show_message(self.bc.get_help(("arg_help",
                                                    pspec['help_ref'])))
            else:
                ret.append(tmp_arg)
                i += 1
        return ret

    def process_server_command_prompt_function(self, cmd, args):
        """Handle a command that has a prompt_func"""
        while True:
            pspec = self.bc.prompt_func(cmd, *args)
            if not isinstance(pspec, dict):
                raise ValueError("server bug")
            if pspec.get("prompt", None) is None and "last_arg" in pspec:
                break
            if "map" in pspec:
                for n in range(len(pspec["map"])):
                    desc = pspec["map"][n][0]
                    if n == 0:
                        self.show_message("Num " + desc[0] % tuple(desc[1:]))
                    else:
                        self.show_message(("%4s " % n)
                                          + desc[0] % tuple(desc[1:]))

            defval = pspec.get("default", None)
            tmp_arg = self.cline.prompt_arg(pspec['prompt'], defval,
                                            postfix='> ')
            if tmp_arg == '?':
                self.show_message(self.bc.get_help("arg_help",
                                                   pspec['help_ref']))
                continue
            if "map" in pspec and "raw" not in pspec:
                tmp_arg = pspec["map"][int(tmp_arg)][1]
            args.append(tmp_arg)
            if "last_arg" in pspec:
                break
        return args

    def show_response(self, bofh_cmd, resp, multple_cmds, show_hdr=True):
        """Use format_suggestions etc. to display a properly formated
        result of a command."""

        if multple_cmds:
            for i in range(len(resp)):
                self.show_response(bofh_cmd, resp[i], False, show_hdr=(i == 0))
            return
        if isinstance(resp, (str, unicode)):
            self.show_message(resp)
            return
        if bofh_cmd not in self._known_formats:
            self._known_formats[bofh_cmd] = \
                self.bc.get_format_suggestion(bofh_cmd)
        format = self._known_formats[bofh_cmd]
        if show_hdr and "hdr" in format:
            self.show_message(format["hdr"])
        if not isinstance(resp, (tuple, list)):
            resp = [resp]
        for sv in format["str_vars"]:
            header = None
            if len(sv) == 3:
                format_str, order, header = sv
            else:
                format_str, order = sv
            if header:
                self.show_message(header)
            for row in resp:
                if order[0] not in row:
                    continue
                tmp = []
                for o in order:
                    t2 = o.split(":", 1)
                    tmp.append(row[t2[0]])
                    if len(t2) > 1 and tmp[-1] != '<not set>':
                        field, ftype = t2
                        if ftype.startswith('date:'):
                            fmt = ftype.split(":", 1)[1]
                            fmt = fmt.replace('yyyy', '%Y').replace(
                                'MM', '%m').replace('dd', '%d')
                            tmp[-1] = DateTime.ISO.ParseDateTime(
                                str(row[field])).strftime(fmt)
                self.show_message(format_str % tuple(tmp))

    def show_message(self, msg):
        print msg


def setup_logger(debug_log):
    """Setup logging.  If debug_log=True, we log debug info to a file.
    Otherwise we setup a stdout-logger for loglevel ERROR (as those
    are indications of bugs that needs fixing)"""

    global logger
    logger = logging.getLogger("pybofh")
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    if debug_log:
        fh = logging.FileHandler("pybofh.log")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'u:qd', [
            'help', 'url=', 'username=', 'set='])
    except getopt.GetoptError:
        usage(1)

    user = getpass.getuser()
    password = None
    debug_log = False
    props_override = {'IdleTerminateDelay': 3600*36, 'IdleWarnDelay': 600,
                      'console_prompt': "pybofh> ",
                      'cacert_file': None, 'rand_cmd': None}
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-q',):
            user, password = 'bootstrap_account', 'test'
        elif opt in ('--username',):
            user = val
        elif opt in ('--set',):
            k, v = val.split('=', 1)
            props_override[k] = v
        elif opt in ('-d',):
            debug_log = True
        elif opt in ('-u', '--url'):
            url = val
    if not url:
        usage(1)

    setup_logger(debug_log)
    BofhClient(url, user, password, **props_override)


def usage(exitcode=0):
    print """Usage: [options]
    -u | --url url : url to connect to
    -q : for debugging
    -d : log debuging info to pybofh.log
    --set k=v : override properties:
        console_prompt : override default console prompt
        IdleTerminateDelay : seconds before receiving timeout warning
        IdleWarnDelay : seconds between warning and termination
        cacert_file : file containing servers ca cert
        rand_cmd : provides random-seed when /dev/random doesn't exist
                   (example: .../openssh/libexec/ssh-rand-helper)
    --username NAME: Override username.
    """
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
