#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import getopt
import glob
import sys
import os
import re


doc_dir = os.path.realpath(os.path.join(
    os.path.dirname(sys.argv[0]), '..'))
script_dir = os.path.join(doc_dir, 'scripts')

dest_dir = ",build"
rst2html = '%s/rst2html.py' % script_dir
rst2docbook = '%s/rst2docbook.py' % script_dir

os.chdir(doc_dir)

# docutils don't allow environment-variables in paths to
# include-directive (and won't accept a patch supporting it), thus we
# make a symlink to avoid hardcoding the full path:
if not os.path.exists(
    os.path.join(doc_dir, ',ceresrc')):
    os.symlink(os.path.join(doc_dir, '..'),
               os.path.join(doc_dir, ',ceresrc'))

# TBD: Hvordan bør oversikten over hvilke filer man skal bygge doc for
# vedlikeholdes?
src_dirs = ['.', 'admin', 'spec', 'devel', 'extensions', 'overview',
            'user', 'extensions/dns']

def build_primitive_contents(outfile):
    print "Writing %s" % outfile
    f = file(outfile, 'w')
    for d in src_dirs:
        f.write("\n\nDocumentation in %s\n" % d)
        for src_file in glob.glob('%s/*.rst' % d):
            doc_title = 'error extracting doc title for %s' % src_file
            for line in file(src_file).readlines():
                if re.match(r'^[a-zA-Z]', line):
                    doc_title = line.strip()
                    break
            f.write("  `%s <%s>`_ (`%s <../%s>`_)\n\n" % (
                doc_title, _get_tgt_file(src_file, '.'), src_file, src_file))
    f.close()

def read_book_xml_file(fname):
    # TODO: vi ønsker å gi en warning for de rst filer som ikke er
    # referert i xml filen
    
    f = file(fname, 'r')
    re_entity = re.compile(r'(<!ENTITY\s+.*SYSTEM\s+")([^"]+)(">)')
    referenced_files = []
    if not os.path.isdir(dest_dir):
        os.mkdir(dest_dir)
    out = file(os.path.join(dest_dir,
                            os.path.basename(fname)[:-4]+'.xml'), 'w')
    for line in f:
        m = re_entity.match(line)
        if m:
            if m.group(2).endswith('.rst'):
               referenced_files.append(m.group(2))
            out.write(line[0:m.start()] +
                      m.group(1)+m.group(2)[:-4]+'.xml'+
                      m.group(3)+line[m.end():])
        else:
            out.write(line)
    out.close()
    for src_file in referenced_files:
        process_file(src_file, _get_tgt_file(src_file, dest_dir,
                                             extension='.xml'),
                     file_type='xml')

def process_file(src_file, tgt_file, file_type='html'):
    # Assert that target dir exists
    in_dir = os.path.dirname(tgt_file)
    if not os.path.isdir(in_dir):
        tmp_in_dir = os.path.split(in_dir)
        for n in range(1, len(tmp_in_dir)+1):
            tmp = os.path.join(*tmp_in_dir[:n])
            if not os.path.isdir(tmp):
                os.mkdir(tmp)

    # Only rebuild if src has been modified
    if (os.path.isfile(tgt_file) and
        os.path.getmtime(src_file) < os.path.getmtime(tgt_file)):
        return

    print "Building %s" % tgt_file
    if file_type == 'html':
        os.system("%s %s > %s" % (rst2html, src_file, tgt_file))
        if not os.path.exists(
            os.path.join(in_dir, 'default.css')):
            os.symlink(os.path.join(script_dir, '..', 'default.css'),
                       os.path.join(in_dir, 'default.css'))
    elif file_type == 'xml':
        f = os.popen("%s %s" % (rst2docbook, src_file), 'r')
        lines = f.readlines()
        out = file(tgt_file, 'w')
        #lines[4] = lines[4].replace("<article>", "<chapter>")
        #lines[-1] = lines[-1].replace("</article>", "</chapter>")
        #out.write("".join(lines[4:]))
        out.write("".join(lines[5:-1]))
        out.close()
        # os.system("%s %s > %s" % (rst2docbook, src_file, tgt_file))

    # make the figures catalog available as a symlink in each
    # directory
    # TBD: Do we really need this?
    if not os.path.exists(
        os.path.join(in_dir, 'figures')):
        os.symlink(os.path.join(script_dir, '..', 'figures'),
                   os.path.join(in_dir, 'figures'))
        

def _get_tgt_file(src_file, dest_dir, extension='.html'):
    tgt_file = os.path.join(dest_dir, src_file)
    return os.path.splitext(tgt_file)[0] + extension
    
def build_doc(dest_dir):
    for d in src_dirs:
        for src_file in glob.glob('%s/*.rst' % d):
            process_file(src_file, _get_tgt_file(src_file, dest_dir))

def build_all():
    build_primitive_contents("contents.rst")
    read_book_xml_file("book.xml")
    os.system("export SP_ENCODING=XML; export SP_CHARSET_FIXED=YES;"
              "cd ,build; db2pdf book.xml")

def usage(exitcode=0):
    print """Usage: [options]
    --help
    --xml file
    --build-contents contents.rst
    --all  : build all documentation

Note:  if db2pdf doesn't handle utf-8 characters, try:
export SP_ENCODING=XML
export SP_CHARSET_FIXED=YES
    """
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'build-contents=', 'xml=', 'all'])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--build-contents',):
            build_primitive_contents(val)
        elif opt in ('--xml',):
            read_book_xml_file(val)
            sys.exit(0)
        elif opt in ('--all',):
            build_all()
    build_doc(dest_dir)


if __name__ == '__main__':
    main()

# arch-tag: 52c80c79-7c4a-4187-a26d-770158b9e9e3
