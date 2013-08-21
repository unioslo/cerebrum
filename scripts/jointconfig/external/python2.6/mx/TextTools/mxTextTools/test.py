# -*- coding: latin-1 -*-

from mx.TextTools import __version__
from mx.TextTools.Examples.HTML import *
from mx.TextTools.Constants.TagTables import *
import pprint, time, pickle

print 'Testing mxTextTools version', __version__
print

# Test for Unicode
try:
    unicode
except NameError:
    HAVE_UNICODE = 0
else:
    HAVE_UNICODE = 1
    ua = unicode('a')
    ub = unicode('b')
    uc = unicode('c')
    ud = unicode('d')
    ue = unicode('e')
    uabc = unicode('abc')
    uHello = unicode('Hello')
    uempty = unicode('')

# Find a HTML file usable for the test
if len(sys.argv) > 1:
    filenames = sys.argv[1:]
else:
    filenames = ['/usr/share/doc/packages/mysql/html/manual.html',
                 '../Doc/mxTextTools.html']
text = ''
for filename in filenames:
    try:
        text = open(filename).read()
    except IOError:
        pass
    else:
        print 'HTML file used for testing the Tagging Engine:'
        print '  ', filename
        print
        break
if not text:
    text = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<HTML>
<HEAD>
   <TITLE>mx Extension Series - License Information</TITLE>
   <META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=iso-8859-1">
</HEAD>

  <BODY TEXT="#000000" BGCOLOR="#FFFFFF" LINK="#0000EE" VLINK="#551A8B" ALINK="#FF0000">
...
    <CENTER><FONT SIZE=-1>&copy; 2000, Copyright by eGenix.com
    Software GmbH, Langengeld, Germany; All Rights Reserved. mailto:
    <A HREF="mailto:info@egenix.com">info@egenix.com</A>
    </FONT></CENTER>
  </BODY>
</HTML>

"""#"

# Test suite
while 1:

    if 1:
        print 'Tagging Engine:'
        print ' parsing HTML ...',
        utext = upper(text)
        t = time.clock()
        result, taglist, nextindex = tag(utext, htmltable)
        assert result == 1
        print ' done. (%5.2f sec.; len(taglist)=%i)' % \
              (time.clock() - t, len(taglist))
        if HAVE_UNICODE: 
            print ' parsing Unicode HTML ...',
            try:
                uutext = unicode(utext, 'latin-1')
            except UnicodeError:
                print ' ... HTML data must be Latin-1; skipping test.'
            else:
                t = time.clock()
                result, utaglist, nextindex = tag(uutext, htmltable)
                assert result == 1
                print ' done. (%5.2f sec.; len(utaglist)=%i)' % \
                      (time.clock() - t, len(utaglist))
                assert taglist == utaglist
                utaglist = None
                uutext = None
        utext = None
        taglist = None

        print ' testing some tag table semantics...'
        table = ((None,Word,'Word'),)
        assert tag('Word',table)[0] == 1
        assert tag('word',table)[0] == 0
        assert tag('xyz',table)[0] == 0

        table = ((None,Word,'Word',MatchFail),)
        assert tag('Word',table)[0] == 1
        assert tag('word',table)[0] == 0
        assert tag('xyz',table)[0] == 0

        table = ((None,Word,'Word',MatchOk),)
        assert tag('Word',table)[0] == 1
        assert tag('word',table)[0] == 1
        assert tag('xyz',table)[0] == 1

        table = ((None,Word,'Word',MatchOk,MatchFail),)
        assert tag('Word',table)[0] == 0
        assert tag('word',table)[0] == 1
        assert tag('xyz',table)[0] == 1

        print ' done.'

        #continue

    print 'splitat()'
    assert splitat('Hello','l') == ('He', 'lo')
    assert splitat('Hello','l',2) == ('Hel', 'o')
    assert splitat('Hello','l',-1) == ('Hel', 'o')
    assert splitat('Hello','l',-2) == ('He', 'lo')
    if HAVE_UNICODE:
        assert splitat(uHello,'l') == (unicode('He'), unicode('lo'))
        assert splitat(uHello,'l',2) == (unicode('Hel'), unicode('o'))
        assert splitat(uHello,unicode('l'),-1) == (unicode('Hel'), unicode('o'))
        assert splitat(uHello,unicode('l'),-2) == (unicode('He'), unicode('lo'))

    print 'suffix()'
    assert suffix('abc.html/',('.htm','abc','.html','/'),0,3) == 'abc'
    assert suffix('abc.html/',('.htm','abc','.html','/'),0,4) == None
    assert suffix('abc.html/',('.htm','abc','.html','/'),0,8) == '.html'
    if HAVE_UNICODE:
        assert suffix(unicode('abc.html/'),('.htm','abc','.html','/'),0,3) == unicode('abc')
        assert suffix(unicode('abc.html/'),(unicode('.htm'),unicode('abc'),'.html','/'),0,3) == unicode('abc')
        assert suffix(unicode('abc.html/'),('.htm','abc',unicode('.html'),'/'),0,3) == unicode('abc')
        try:
            suffix('abc.html/',(unicode('.htm'),'abc','.html','/'))
        except TypeError:
            pass
        else:
            raise AssertionError, \
                  'suffix(string,...) should not accept unicode suffixes'
        assert suffix(unicode('abc.html/'),('.htm','abc','.html','/'),0,4) == None

    print 'prefix()'
    assert prefix('abc.html/',('.htm','abc','.html','/'),0,3) == 'abc'
    assert prefix('abc.html/',('.htm','abc','.html','/'),1,4) == None
    assert prefix('abc.html/',('.htm','abc','.html','/'),3,9) == '.htm'
    if HAVE_UNICODE:
        assert prefix(unicode('abc.html/'),('.htm','abc','.html','/'),0,3) == unicode('abc')
        assert prefix(unicode('abc.html/'),(unicode('.htm'),unicode('abc'),'.html','/'),0,3) == unicode('abc')
        assert prefix(unicode('abc.html/'),('.htm','abc',unicode('.html'),'/'),0,3) == unicode('abc')
        try:
            prefix('abc.html/',(unicode('.htm'),'abc','.html','/'))
        except TypeError:
            pass
        else:
            raise AssertionError, \
                  'prefix(string,...) should not accept unicode prefixes'
        assert prefix(unicode('abc.html/'),('.htm','abc','.html','/'),0,4) == unicode('abc')

    print 'join()'
    assert join(('a','b','c')) == 'abc'
    assert join(['a','b','c']) == 'abc'
    assert join(('a','b','c'),' ') == 'a b c'
    assert join(['a','b','c'],' ') == 'a b c'
    assert join((('abc',0,1),('abc',1,2),('abc',2,3))) == 'abc'
    assert join((('abc',0,1),'b',('abc',2,3))) == 'abc'
    assert join((('abc',0,3),)) == 'abc'
    if HAVE_UNICODE:
        assert join((ua,ub,uc)) == uabc
        assert join([ua,ub,uc]) == uabc
        assert join((ua,ub,uc),' ') == unicode('a b c')
        assert join([ua,ub,uc],' ') == unicode('a b c')
        assert join(((uabc,0,1),(uabc,1,2),(uabc,2,3))) == uabc
        assert join(((uabc,0,1),ub,(uabc,2,3))) == uabc
        assert join(((uabc,0,3),)) == uabc

    print 'upper()'
    assert upper('HeLLo') == 'HELLO'
    assert upper('hello') == 'HELLO'
    assert upper('HELLO') == 'HELLO'
    assert upper('HELLO ') == 'HELLO '
    assert upper('HELLO 123') == 'HELLO 123'
    if HAVE_UNICODE:
        assert upper(unicode('HeLLo')) == unicode('HELLO')
        assert upper(unicode('hello')) == unicode('HELLO')
        assert upper(unicode('HELLO')) == unicode('HELLO')
        assert upper(unicode('HELLO ')) == unicode('HELLO ')
        assert upper(unicode('HELLO 123')) == unicode('HELLO 123')

    print 'lower()'
    assert lower('HeLLo') == 'hello'
    assert lower('hello') == 'hello'
    assert lower('HELLO') == 'hello'
    assert lower('HELLO ') == 'hello '
    assert lower('HELLO 123') == 'hello 123'
    if HAVE_UNICODE:
        assert lower(unicode('HeLLo')) == unicode('hello')
        assert lower(unicode('hello')) == unicode('hello')
        assert lower(unicode('HELLO')) == unicode('hello')
        assert lower(unicode('HELLO ')) == unicode('hello ')
        assert lower(unicode('HELLO 123')) == unicode('hello 123')

    print 'isascii()'
    assert isascii('abc') == 1
    assert isascii('abcäöü') == 0
    assert isascii('abcäöüdef') == 0
    assert isascii('.,- 1234') == 1
    if HAVE_UNICODE:
        assert isascii(uabc) == 1
        assert isascii(unicode('abcäöü', 'latin-1')) == 0
        assert isascii(unicode('abcäöüdef', 'latin-1')) == 0
        assert isascii(unicode('.,- 1234')) == 1

    print 'setstrip()'
    assert setstrip('Hello', set('')) == 'Hello'
    assert setstrip('Hello', set('o')) == 'Hell'
    assert setstrip(' Hello ', set(' o')) == 'Hell'
    assert setstrip(' Hello ', set(' o'), 0, len(' Hello '), -1) == 'Hello '
    assert setstrip(' Hello ', set(' o'), 0, len(' Hello '), 1) == ' Hell'
    assert setstrip('  ', set(' ')) == ''

    print 'setsplit()'
    assert setsplit('Hello', set('l')) == ['He', 'o']
    assert setsplit('Hello', set('lo')) == ['He',]
    assert setsplit('Hello', set('abc')) == ['Hello',]

    print 'setsplitx()'
    assert setsplitx('Hello', set('l')) == ['He', 'll', 'o']
    assert setsplitx('Hello', set('lo')) == ['He', 'llo']
    assert setsplitx('Hello', set('abc')) == ['Hello',]

    print 'joinlist()'
    assert joinlist('Hello', [('A',1,2), ('B',3,4)]) == \
           [('Hello', 0, 1), 'A', ('Hello', 2, 3), 'B', ('Hello', 4, 5)]
    assert join(joinlist('Hello', [('A',1,2), ('B',3,4)])) == \
           'HAlBo'
    if HAVE_UNICODE:
        assert joinlist(uHello, [('A',1,2), ('B',3,4)]) == \
               [(uHello, 0, 1), 'A', (uHello, 2, 3), 'B', (uHello, 4, 5)]
        assert join(joinlist(uHello, [('A',1,2), ('B',3,4)])) == \
               unicode('HAlBo')
        assert join(joinlist('Hello', [(ua,1,2), (ub,3,4)])) == \
               unicode('Halbo')

    print 'charsplit()'
    assert charsplit('Hello', 'l') == ['He', '', 'o']
    assert charsplit('Hello', 'e') == ['H', 'llo']
    assert charsplit('HelloHello', 'e') == ['H', 'lloH', 'llo']
    if HAVE_UNICODE:
        assert charsplit(uHello, unicode('l')) == [unicode('He'), unicode(''), unicode('o')]
        assert charsplit(uHello, unicode('e')) == [unicode('H'), unicode('llo')]
        assert charsplit(uHello*2, unicode('e')) == [unicode('H'), unicode('lloH'), unicode('llo')]

    print 'CharSet().contains()'
    tests = [
        ("a-z",
         ('a', 1), ('b', 1), ('c', 1), ('z', 1),
         ('A', 0), ('B', 0), ('C', 0), ('Z', 0),
         ),
        ("a\-z",
         ('a', 1), ('b', 0), ('c', 0), ('z', 1), ('-', 1),
         ),
        ]
    if HAVE_UNICODE:
        tests[len(tests):] = [
        ("a-z",
         ('a', 1), ('b', 1), ('c', 1), ('z', 1),
         ('A', 0), ('B', 0), ('C', 0), ('Z', 0),
         (unicode('a'), 1), (unicode('b'), 1), (unicode('c'), 1), (unicode('z'), 1),
         (unicode('A'), 0), (unicode('B'), 0), (unicode('C'), 0), (unicode('Z'), 0),
         ),
        ("abc",
         ('a', 1), ('b', 1), ('c', 1), ('z', 0),
         ('A', 0), ('B', 0), ('C', 0), ('Z', 0),
         (unicode('a'), 1), (unicode('b'), 1), (unicode('c'), 1), (unicode('z'), 0),
         (unicode('A'), 0), (unicode('B'), 0), (unicode('C'), 0), (unicode('Z'), 0),
         ),
        (unicode("abc"),
         ('a', 1), ('b', 1), ('c', 1), ('z', 0),
         ('A', 0), ('B', 0), ('C', 0), ('Z', 0),
         (unicode('a'), 1), (unicode('b'), 1), (unicode('c'), 1), (unicode('z'), 0),
         (unicode('A'), 0), (unicode('B'), 0), (unicode('C'), 0), (unicode('Z'), 0),
         ),
        (unicode('a-z\uFFFF', 'unicode-escape'),
         ('a', 1), ('b', 1), ('c', 1), ('z', 1),
         ('A', 0), ('B', 0), ('C', 0), ('Z', 0), 
         (unicode('a'), 1), (unicode('b'), 1), (unicode('c'), 1), (unicode('z'), 1),
         (unicode('A'), 0), (unicode('B'), 0), (unicode('C'), 0), (unicode('Z'), 0),
         (unichr(55555), 0), (unichr(1234), 0), (unichr(1010), 0),
         (unichr(0xFFFF), 1),
         ),
        (unicode("a\-z"),
         ('a', 1), ('b', 0), ('c', 0), ('z', 1), ('-', 1),
         ),
        ]

    for test in tests:
        cs = CharSet(test[0])
        for ch, rc in test[1:]:
            assert cs.contains(ch) == rc, \
                   'CharSet(%s).contains(%s) ... expected: %s' % \
                   (repr(cs.definition), repr(ch), rc)

    print 'CharSet().search()'
    tests = [
        ("a-z",
         ('', None), ('abc', 0), ('ABCd', 3),
         ),
        ("a\-z",
         ('', None), ('bcd', None), ('ABCd', None), ('zzz', 0),
         ),
        ("abc",
         ('', None), ('bcd', 0), ('ABCd', None), ('zzz', None), ('dddbbb', 3),
         ),
        ]
    if HAVE_UNICODE:
        tests[len(tests):] = [
        ("a-z",
         ('', None), ('abc', 0), ('ABCd', 3),
         (unicode(''), None), (unicode('abc'), 0), (unicode('ABCd'), 3),
         ),
        ("a\-z",
         ('', None), ('bcd', None), ('ABCd', None), ('zzz', 0),
         (unicode(''), None), (unicode('bcd'), None), (unicode('ABCd'), None), (unicode('zzz'), 0),
         ),
        ("abc",
         ('', None), ('bcd', 0), ('ABCd', None), ('zzz', None), ('dddbbb', 3),
         (unicode(''), None), (unicode('bcd'), 0), (unicode('ABCd'), None), (unicode('zzz'), None), (unicode('dddbbb'), 3),
         ),
        (unicode('a-z\uFFFF', 'unicode-escape'),
         ('', None), ('abc', 0), ('ABCd', 3),
         (unicode(''), None), (unicode('abc'), 0), (unicode('ABCd'), 3),
         (unichr(0xFFFF), 0),
         ),
        (unicode('a\-z'),
         ('', None), ('bcd', None), ('ABCd', None), ('zzz', 0),
         (unicode(''), None), (unicode('bcd'), None), (unicode('ABCd'), None), (unicode('zzz'), 0),
         ),
        (unicode('abc'),
         ('', None), ('bcd', 0), ('ABCd', None), ('zzz', None), ('dddbbb', 3),
         (unicode(''), None), (unicode('bcd'), 0), (unicode('ABCd'), None), (unicode('zzz'), None), (unicode('dddbbb'), 3),
         ),
        ]

    for test in tests:
        cs = CharSet(test[0])
        for ch, rc in test[1:]:
            assert cs.search(ch) == rc, \
                   'CharSet(%s).search(%s) ... expected: %s' % \
                   (repr(cs.definition), repr(ch), rc)

    print 'CharSet().match()'
    tests = [
        ("a-z",
         ('', 0), ('abc', 3), ('ABCd', 0),
         ),
        ("a\-z",
         ('', 0), ('bcd', 0), ('ABCd', 0), ('zzz', 3),
         ),
        ("abc",
         ('', 0), ('bcd', 2), ('ABCd', 0), ('zzz', 0), ('dddbbb', 0),
         ),
        ]
    if HAVE_UNICODE:
        tests[len(tests):] = [
        ("a-z",
         ('', 0), ('abc', 3), ('ABCd', 0),
         (unicode(''), 0), (unicode('abc'), 3), (unicode('ABCd'), 0),
         ),
        ("a\-z",
         ('', 0), ('bcd', 0), ('ABCd', 0), ('zzz', 3),
         (unicode(''), 0), (unicode('bcd'), 0), (unicode('ABCd'), 0), (unicode('zzz'), 3),
         ),
        ("abc",
         ('', 0), ('bcd', 2), ('ABCd', 0), ('zzz', 0), ('dddbbb', 0),
         (unicode(''), 0), (unicode('bcd'), 2), (unicode('ABCd'), 0), (unicode('zzz'), 0), (unicode('dddbbb'), 0),
         ),
        (unicode('a-z\uFFFF', 'unicode-escape'),
         ('', 0), ('abc', 3), ('ABCd', 0),
         (unicode(''), 0), (unicode('abc'), 3), (unicode('ABCd'), 0),
         (unichr(0xFFFF), 1),
         ),
        (unicode('a\-z'),
         ('', 0), ('bcd', 0), ('ABCd', 0), ('zzz', 3),
         (unicode(''), 0), (unicode('bcd'), 0), (unicode('ABCd'), 0), (unicode('zzz'), 3),
         ),
        (unicode('abc'),
         ('', 0), ('bcd', 2), ('ABCd', 0), ('zzz', 0), ('dddbbb', 0),
         (unicode(''), 0), (unicode('bcd'), 2), (unicode('ABCd'), 0), (unicode('zzz'), 0), (unicode('dddbbb'), 0),
         ),
        ]

    for test in tests:
        cs = CharSet(test[0])
        for ch, rc in test[1:]:
            assert cs.match(ch) == rc, \
                   'CharSet(%s).match(%s) ... expected: %s' % \
                   (repr(cs.definition), repr(ch), rc)

    print 'CharSet().strip()'
    assert CharSet('').strip('Hello') == 'Hello'
    assert CharSet('o').strip('Hello') == 'Hell'
    assert CharSet(' o').strip(' Hello ') == 'Hell'
    assert CharSet(' o').strip(' Hello ', -1, 0, len(' Hello ')) == 'Hello '
    assert CharSet(' o').strip(' Hello ', 1, 0, len(' Hello ')) == ' Hell'
    assert CharSet('  ').strip('  ') == ''
    if HAVE_UNICODE:
        assert CharSet('').strip(unicode('Hello')) == unicode('Hello')
        assert CharSet('o').strip(unicode('Hello')) == unicode('Hell')
        assert CharSet(' o').strip(unicode(' Hello ')) == unicode('Hell')
        assert CharSet(' o').strip(unicode(' Hello '), -1, 0, len(unicode(' Hello '))) == unicode('Hello ')
        assert CharSet(' o').strip(unicode(' Hello '), 1, 0, len(unicode(' Hello '))) == unicode(' Hell')
        assert CharSet(unicode('')).strip(unicode('Hello')) == unicode('Hello')
        assert CharSet(unicode('o')).strip(unicode('Hello')) == unicode('Hell')
        assert CharSet(unicode(' o')).strip(unicode(' Hello ')) == unicode('Hell')
        assert CharSet(unicode(' o')).strip(unicode(' Hello '), -1, 0, len(unicode(' Hello '))) == unicode('Hello ')
        assert CharSet(unicode(' o')).strip(unicode(' Hello '), 1, 0, len(unicode(' Hello '))) == unicode(' Hell')

    print 'CharSet().split()'
    assert CharSet('l').split('Hello') == ['He', 'o']
    assert CharSet('lo').split('Hello') == ['He',]
    assert CharSet('abc').split('Hello') == ['Hello',]
    if HAVE_UNICODE:
        assert CharSet('l').split(unicode('Hello')) == ['He', 'o']
        assert CharSet('lo').split(unicode('Hello')) == ['He',]
        assert CharSet('abc').split(unicode('Hello')) == ['Hello',]
        assert CharSet(unicode('l')).split(unicode('Hello')) == ['He', 'o']
        assert CharSet(unicode('lo')).split(unicode('Hello')) == ['He',]
        assert CharSet(unicode('abc')).split(unicode('Hello')) == ['Hello',]

    print 'CharSet().splitx()'
    assert CharSet('l').splitx('Hello') == ['He', 'll', 'o']
    assert CharSet('lo').splitx('Hello') == ['He', 'llo']
    assert CharSet('abc').splitx('Hello') == ['Hello',]
    assert CharSet(' ').splitx('x y ') == ['x', ' ', 'y', ' ']
    assert CharSet(' ').splitx(' x y ') == ['', ' ', 'x', ' ', 'y', ' ']
    if HAVE_UNICODE:
        assert CharSet('l').splitx(unicode('Hello')) == ['He', 'll', 'o']
        assert CharSet('lo').splitx(unicode('Hello')) == ['He', 'llo']
        assert CharSet('abc').splitx(unicode('Hello')) == ['Hello',]
        assert CharSet(' ').splitx(unicode('x y ')) == ['x', ' ', 'y', ' ']
        assert CharSet(' ').splitx(unicode(' x y ')) == ['', ' ', 'x', ' ', 'y', ' ']
        assert CharSet(unicode('l')).splitx(unicode('Hello')) == ['He', 'll', 'o']
        assert CharSet(unicode('lo')).splitx(unicode('Hello')) == ['He', 'llo']
        assert CharSet(unicode('abc')).splitx(unicode('Hello')) == ['Hello',]
        assert CharSet(unicode(' ')).splitx(unicode('x y ')) == ['x', ' ', 'y', ' ']
        assert CharSet(unicode(' ')).splitx(unicode(' x y ')) == ['', ' ', 'x', ' ', 'y', ' ']

    print 'CharSet() negative logic matching'
    assert CharSet('0-9').contains('a') == 0
    assert CharSet('^0-9').contains('a') == 1
    assert CharSet('0-9').match('abc') == 0
    assert CharSet('0-9').match('123abc') == 3
    assert CharSet('0-9').match('abc123') == 0
    assert CharSet('0-9').search('abc') == None
    assert CharSet('0-9').search('123abc') == 0
    assert CharSet('0-9').search('abc123') == 3
    assert CharSet('^0-9').match('abc') == 3
    assert CharSet('^0-9').match('123abc') == 0
    assert CharSet('^0-9').match('abc123') == 3
    assert CharSet('^0-9').search('abc') == 0
    assert CharSet('^0-9').search('123abc') == 3
    assert CharSet('^0-9').search('abc123') == 0
    if HAVE_UNICODE:
        assert CharSet('0-9').contains(unicode('a')) == 0
        assert CharSet('^0-9').contains(unicode('a')) == 1
        assert CharSet('0-9').match(unicode('abc')) == 0
        assert CharSet('0-9').match(unicode('123abc')) == 3
        assert CharSet('0-9').match(unicode('abc123')) == 0
        assert CharSet('0-9').search(unicode('abc')) == None
        assert CharSet('0-9').search(unicode('123abc')) == 0
        assert CharSet('0-9').search(unicode('abc123')) == 3
        assert CharSet('^0-9').match(unicode('abc')) == 3
        assert CharSet('^0-9').match(unicode('123abc')) == 0
        assert CharSet('^0-9').match(unicode('abc123')) == 3
        assert CharSet('^0-9').search(unicode('abc')) == 0
        assert CharSet('^0-9').search(unicode('123abc')) == 3
        assert CharSet('^0-9').search(unicode('abc123')) == 0
        assert CharSet(unicode('0-9')).contains(unicode('a')) == 0
        assert CharSet(unicode('^0-9')).contains(unicode('a')) == 1
        assert CharSet(unicode('0-9')).match(unicode('abc')) == 0
        assert CharSet(unicode('0-9')).match(unicode('123abc')) == 3
        assert CharSet(unicode('0-9')).match(unicode('abc123')) == 0
        assert CharSet(unicode('0-9')).search(unicode('abc')) == None
        assert CharSet(unicode('0-9')).search(unicode('123abc')) == 0
        assert CharSet(unicode('0-9')).search(unicode('abc123')) == 3
        assert CharSet(unicode('^0-9')).match(unicode('abc')) == 3
        assert CharSet(unicode('^0-9')).match(unicode('123abc')) == 0
        assert CharSet(unicode('^0-9')).match(unicode('abc123')) == 3
        assert CharSet(unicode('^0-9')).search(unicode('abc')) == 0
        assert CharSet(unicode('^0-9')).search(unicode('123abc')) == 3
        assert CharSet(unicode('^0-9')).search(unicode('abc123')) == 0

    print 'CharSet() pickling'
    cs = CharSet('abc')
    pcs = pickle.dumps(cs)
    cs1 = pickle.loads(pcs)
    assert cs.match('abc') == cs1.match('abc')
    assert cs.match('') == cs1.match('')
    assert cs.match('eee') == cs1.match('eee')
    assert cs.match('   abc') == cs1.match('   abc')
    assert cs.match('abc...d') == cs1.match('abc...d')
    assert cs.search('xxxabc') == cs1.search('xxxabc')

    ###

    htmltag = (
        (None,Is,'<'),
        # is this a closing tag ?
        ('closetag',Is,'/',+1),
        # a coment ?
        ('comment',Is,'!','check-xmp-tag'),
         (None,Word,'--',+4),
         ('text',WordStart,'-->',+1),
         (None,Skip,3),
         (None,Jump,To,MatchOk),
         # a SGML-Tag ?
         ('other',AllNotIn,'>',+1),
          (None,Is,'>'),
         (None,Jump,To,MatchOk),
        # XMP-Tag ?
        'check-xmp-tag',
        ('tagname',Word,'xmp','get-tagname'),
         (None,Is,'>'),
         ('text',WordStart,'</xmp>'),
         (None,Skip,len('</xmp>')),
         (None,Jump,To,MatchOk),
        # get the tag name
        'get-tagname',
        ('tagname',AllInCharSet,tagname_charset),
        # look for attributes
        'get-attributes',
        (None,AllInCharSet,white_charset,'incorrect-attributes'),
         (None,Is,'>',+1,MatchOk),
         ('tagattr',Table,tagattr),
         (None,Jump,To,-3),
         (None,Is,'>',+1,MatchOk),
        # handle incorrect attributes
        'incorrect-attributes',
        (error,AllNotIn,'> \n\r\t'),
        (None,Jump,To,'get-attributes')
        )

    print 'TagTable()'
    htmltable_tt = TagTable(htmltable)
    htmltag_tt = TagTable(htmltag)

    if HAVE_UNICODE:
        print 'UnicodeTagTable()'
        utt = UnicodeTagTable(htmltag)

    print 'TagTable() pickling'
    ptt = pickle.dumps(htmltable_tt)
    tt1 = pickle.loads(ptt)

    print 'TextSearch() pickling'
    pts = pickle.dumps(TextSearch('test'))
    ts1 = pickle.loads(pts)

    if 0:
        print 'HTML Table:'
        pprint.pprint(htmltable)
        print 'TagTable .dump() version of the HTML table:'
        pprint.pprint(htmltable_tt.dump())

    ###

    print 'TextSearch() object (Boyer-Moore)'
    ts = TextSearch('test')
    ts = TextSearch('test', None)
    ts = TextSearch('test', 'x'*256)
    ts = TextSearch('test', None, BOYERMOORE)
    
    ts = TextSearch('test')
    assert ts.search('    test') == (4, 8), ts.search('    test')
    assert ts.search('    test   ') == (4, 8)
    assert ts.search('    abc   ') == (0, 0)
    assert ts.find('    test') == 4, ts.find('    test')
    assert ts.find('    test   ') == 4
    assert ts.find('    abd   ') == -1
    assert ts.findall('    test  test  ') == [(4, 8), (10, 14)]
    assert ts.findall('   abc def  ') == []
    if HAVE_UNICODE:
        try:
            ts.search(unicode('    test'))
        except TypeError:
            pass
        else:
            raise AssertionError,'Boyer-Moore does not work with Unicode'
        try:
            ts.find(unicode('    test'))
        except TypeError:
            pass
        else:
            raise AssertionError,'Boyer-Moore does not work with Unicode'
        try:
            ts.findall(unicode('    test  test  '))
        except TypeError:
            pass
        else:
            raise AssertionError,'Boyer-Moore does not work with Unicode'

    try:
        ts = TextSearch('test', None, FASTSEARCH)
    except ValueError:
        pass
    else:
        print 'TextSearch() object (FastSearch)'
        assert ts.search('    test') == (4, 8)
        assert ts.search('    test   ') == (4, 8)
        assert ts.search('    abc   ') == (0, 0)
        assert ts.find('    test') == 4
        assert ts.find('    test   ') == 4
        assert ts.find('    abd   ') == -1
        assert ts.findall('    test  test  ') == [(4, 8), (10, 14)]
        assert ts.findall('   abc def  ') == []

    print 'TextSearch() object (Trivial)'
    ts = TextSearch('test', algorithm=TRIVIAL)
    assert ts.search('    test') == (4, 8)
    assert ts.search('    test   ') == (4, 8)
    assert ts.search('    abc   ') == (0, 0)
    assert ts.find('    test') == 4
    assert ts.find('    test   ') == 4
    assert ts.find('    abd   ') == -1
    assert ts.findall('    test  test  ') == [(4, 8), (10, 14)]
    assert ts.findall('   abc def  ') == []
    if HAVE_UNICODE:
        print 'TextSearch() object (Trivial; Unicode)'
        assert ts.search(unicode('    test')) == (4, 8)
        assert ts.search(unicode('    test   ')) == (4, 8)
        assert ts.search(unicode('    abc   ')) == (0, 0)
        assert ts.find(unicode('    test')) == 4
        assert ts.find(unicode('    test   ')) == 4
        assert ts.find(unicode('    abd   ')) == -1
        assert ts.findall(unicode('    test  test  ')) == [(4, 8), (10, 14)]
        assert ts.findall(unicode('   abc def  ')) == []
        ts = TextSearch(unicode('test'), algorithm=TRIVIAL)
        assert ts.search('    test') == (4, 8)
        assert ts.search('    test   ') == (4, 8)
        assert ts.search('    abc   ') == (0, 0)
        assert ts.find('    test') == 4
        assert ts.find('    test   ') == 4
        assert ts.find('    abd   ') == -1
        assert ts.findall('    test  test  ') == [(4, 8), (10, 14)]
        assert ts.findall('   abc def  ') == []
        assert ts.search(unicode('    test')) == (4, 8)
        assert ts.search(unicode('    test   ')) == (4, 8)
        assert ts.search(unicode('    abc   ')) == (0, 0)
        assert ts.find(unicode('    test')) == 4
        assert ts.find(unicode('    test   ')) == 4
        assert ts.find(unicode('    abd   ')) == -1
        assert ts.findall(unicode('    test  test  ')) == [(4, 8), (10, 14)]
        assert ts.findall(unicode('   abc def  ')) == []
        ts = TextSearch(unicode('test'))
        assert ts.algorithm == TRIVIAL

    print 'is_whitespace()'
    assert is_whitespace('   \t\r') == 1
    assert is_whitespace(' 123  ') == 0
    if HAVE_UNICODE:
        assert is_whitespace(unicode('   \t\r')) == 1
        assert is_whitespace(unicode(' 123  ')) == 0

    print 'collapse()'
    assert collapse('a\nb\nc') == 'a b c'
    assert collapse('a\nb\nc', '-') == 'a-b-c'
    if HAVE_UNICODE:
        assert collapse(unicode('a\nb\nä','latin-1')) == unicode('a b ä','latin-1')
        assert collapse(unicode('a\nb\nä','latin-1'), '-') == unicode('a-b-ä','latin-1')

    print 'splitwords()'
    assert splitwords('a b c') == ['a', 'b', 'c']
    if HAVE_UNICODE:
        assert splitwords(unicode('a b ä','latin-1')) == [ua, ub, unicode('ä','latin-1')]

    print 'countlines()'
    assert countlines('a\nb\nc') == 3
    assert countlines('a\nb\nc\n') == 3
    if HAVE_UNICODE:
        assert countlines(unicode('a\nb\nä','latin-1')) == 3

    print 'splitlines()'
    assert splitlines('a\nb\r\nc') == ['a', 'b', 'c']
    assert splitlines('a\nb\r\nc\r') == ['a', 'b', 'c']
    if HAVE_UNICODE:
        assert splitlines(unicode('a\nb\r\nä\r','latin-1')) == [ua, ub, unicode('ä','latin-1')]

    print 'replace()'
    assert replace('a\nb\nc', '\n', ' ') == 'a b c'
    assert replace('a\nb\nc', '\n', '-') == 'a-b-c'
    if HAVE_UNICODE:
        assert replace(unicode('a\nb\nä','latin-1'), '\n', ' ') == unicode('a b ä','latin-1')
        assert replace(unicode('a\nb\nä','latin-1'), '\n', '-') == unicode('a-b-ä','latin-1')

    print 'multireplace()'
    assert multireplace('a\nb\nc', [(' ', 1, 2)]) == 'a b\nc'
    assert multireplace('a\nb\nc', [('-', 1, 2), ('-', 3, 4)]) == 'a-b-c'
    if HAVE_UNICODE:
        assert multireplace(unicode('a\nb\nä','latin-1'), [(' ', 1, 2)]) == unicode('a b\nä','latin-1')
        assert multireplace(unicode('a\nb\nä','latin-1'), [('-', 1, 2), ('-', 3, 4)]) == unicode('a-b-ä','latin-1')

    print 'quoted_split()'
    assert quoted_split('  a, b  ,\t c,d ,e ,"ab,cd,de" ,\'a,b\'', ',') == \
           ['a', 'b', 'c', 'd', 'e', 'ab,cd,de', 'a,b']
    # twice to test table cache
    assert quoted_split('  a, b  ,\t c,d ,e ,"ab,cd,de" ,\'a,b\'', ',') == \
           ['a', 'b', 'c', 'd', 'e', 'ab,cd,de', 'a,b']
    assert quoted_split('  a b  \t c d e "ab cd de" \'a b\'') == \
           ['a', 'b', 'c', 'd', 'e', 'ab cd de', 'a b']
    assert quoted_split(',,a', ',') == ['', '', 'a']
    assert quoted_split(',,a,', ',') == ['', '', 'a', '']
    if HAVE_UNICODE:
        assert quoted_split(unicode('  a, b  ,\t c,d ,e ,"ab,cd,de" ,\'a,b\''), ',') == \
               [ua, ub, uc, ud, ue, unicode('ab,cd,de'), unicode('a,b')]
        assert quoted_split(unicode(',,a'), ',') == [uempty, uempty, ua]
        assert quoted_split(unicode(',,a,'), ',') == [uempty, uempty, ua, uempty]

    # Clear the TagTable cache
    tagtable_cache.clear()

    break

print
print 'Works.'
