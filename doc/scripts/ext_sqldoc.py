#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import getopt
import sys
import re

def get_table_desc(tab_comment):
    """Return the description for a given table.  The table is
    identified by /*<tab><tablename>, and ends with */ on a separate
    line"""
    
    m = re.match('\s+\S+', tab_comment)
    if m is None:
        sys.stderr.write("Badly formatted comment")
        sys.exit(1)

    # Trim leading and trailing blank lines
    lines = tab_comment.split("\n")
    start = 1
    for l in lines[1:]:
        if l.isspace() or len(l) == 0:
            start += 1
        else:
            break
    end = len(lines) - 1
    while end > 0:
        if lines[end].isspace() or len(lines[end]) == 0:
            end -= 1
        else:
            break
    return "\n".join(lines[start:end+1])

def get_table_info(fname, want_table):
    """Returns the definition of a table, and its immeadeately
    preceeding comment."""

    re_start_table_comment = re.compile(r'/\*')
    re_end_table_comment = re.compile(r'\*/')
    re_start_table = re.compile(r'create table (\S+)', re.IGNORECASE)
    re_end_table = re.compile(r'\);')

    f = file(fname, 'r')
    tab_def = tab_comment = tab_name = None
    in_tab_comment = False
    for line in f:
        if tab_name is not None:       # Inside table definition
            m = re_end_table.search(line)
            if m:
                tab_def += line[:m.end()]
                if tab_name == want_table:
                    return tab_def, tab_comment
                tab_name = tab_def = tab_comment = None
            else:
                tab_def += line
        elif in_tab_comment:           # Inside a table comment
            m = re_end_table_comment.search(line)
            if m:
                tab_comment += line[:m.start()]
                in_tab_comment = False
            else:
                tab_comment += line
        else:
            m = re_start_table_comment.search(line)
            if m:
                tab_comment = line[m.end():]
                in_tab_comment = True
            else:
                m = re_start_table.search(line)
                if m:
                    tab_name = m.group(1)
                    tab_def = line

def usage(exitcode=0):
    print """Usage: [options]
    --file file
    --type def|comment|desc      [default: desc]
      def = table definition
      comment = entire comment before table
      desc = table description (= parsed comment, see docstring)
    --table name

    Extracts information about given table from the file.  --table
    should be last argument
    """
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'table=', 'file=', 'type='])
    except getopt.GetoptError:
        usage(1)

    type = 'desc'
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--table',):
            i = get_table_info(fname, val)
            if i is None:
                sys.stderr.write("Table '%s' not found\n" % val)
            else:
                if type == 'desc':
                    print get_table_desc(i[1]),
                elif type == 'comment':
                    print i[1],
                elif type == 'def':
                    print i[0]
        elif opt in ('--type',):
            type = val
        elif opt in ('--file',):
            fname = val

if __name__ == '__main__':
    main()

