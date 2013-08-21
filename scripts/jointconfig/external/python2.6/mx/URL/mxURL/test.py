import mx.URL
from mx.URL import *

print 'Testing URL version %s ...' % mx.URL.__version__

#
# Join tests adapted from Python 1.5 urlparse.py:
#
print ' Join tests.'
a = URL('http://a/b/c/d')
tests = (
    (a+URL('http:h'),'http://a/b/c/h'),
    (a+URL('http:g'),'http://a/b/c/g'),
    (a+URL('http:'),'http://a/b/c/d'),
    (a+URL('g'),'http://a/b/c/g'),
    (a+URL('./g'),'http://a/b/c/g'),
    (a+URL('g/'),'http://a/b/c/g/'),
    (a+URL('/g'),'http://a/g'),
    (a+URL('//g'),'http://g'),
    (a+URL('?y'),'http://a/b/c/d?y'),
    (a+URL('g?y'),'http://a/b/c/g?y'),
    (a+URL('g?y/./x'),'http://a/b/c/g?y/./x'),
    (a+URL('.'),'http://a/b/c/'),
    (a+URL('./'),'http://a/b/c/'),
    (a+URL('..'),'http://a/b/'),
    (a+URL('../'),'http://a/b/'),
    (a+URL('../g'),'http://a/b/g'),
    (a+URL('../..'),'http://a/'),
    (a+URL('../../g'),'http://a/g'),
    (a+URL('../../../g'),'http://a/g'),
    (a+URL('./../g'),'http://a/b/g'),
    (a+URL('./g/.'),'http://a/b/c/g/'),
    (a+URL('/./g'),'http://a/g'),
    (a+URL('g/./h'),'http://a/b/c/g/h'),
    (a+URL('g/../h'),'http://a/b/c/h'),
    (URL('..') + URL('file:a/b/'),'file:../a/b/'),
    (URL('a/..') + URL('b/..'),'./'),
    (URL('/') + URL('a/..') + URL('b/.'),'/b/'),
    (URL('file:abc') + URL('http:abc'),'http:abc'),
    (URL('//www.test.com'),'//www.test.com'),
    (URL('http://www.test.com') + URL('a/b/c'),'http://www.test.com/a/b/c'),
    ((URL('http://www.test.com') + URL('a/b/c')).netloc,'www.test.com'),
    )

#
# More tests adapated from SF bug report #450225: "urljoin fails RFC tests"
#
# XXX The commented tests currently fail.
#
base = URL('http://a/b/c/d;p?q')
tests = tests + (
    (base + URL('ftp:h'), 'ftp:h'),
    (base + URL('g'),   'http://a/b/c/g'),
    (base + URL('./g'), 'http://a/b/c/g'),
    (base + URL('g/'),  'http://a/b/c/g/'),
    (base + URL('/g'),  'http://a/g'),
    (base + URL('//g'), 'http://g'),
#    (base + URL('?y'),  'http://a/b/c/?y'),
#    Why not http://a/b/c/d;phttp://a/b/c/d;p?y ?
    (base + URL('g?y'), 'http://a/b/c/g?y'),
    (base + URL('#s'),  'http://a/b/c/d;p?q#s'),
    (base + URL('g#s'), 'http://a/b/c/g#s'),
    (base + URL('g?y#s'), 'http://a/b/c/g?y#s'),
#    (base + URL(';x'), 'http://a/b/c/;x'),
#    Why not http://a/b/c/d;phttp://a/b/c/d;x ?
    (base + URL('g;x'),  'http://a/b/c/g;x'),
    (base + URL('g;x?y#s'), 'http://a/b/c/g;x?y#s'),
    (base + URL('.'),  'http://a/b/c/'),
    (base + URL('./'),  'http://a/b/c/'),
    (base + URL('..'),  'http://a/b/'),
    (base + URL('../'),  'http://a/b/'),
    (base + URL('../g'),  'http://a/b/g'),
    (base + URL('../..'),  'http://a/'),
    (base + URL('../../'),  'http://a/'),
    (base + URL('../../g'),  'http://a/g'),
    (base + URL(''), base.url),
#    (base + URL('../../../g')   ,  'http://a/../g'),
#    (base + URL('../../../../g'),  'http://a/../../g'),
#    (base + URL('/./g'),  'http://a/./g'),
#    (base + URL('/../g')        ,  'http://a/../g'),
#    Why should the additional ..'s be preserved ?
    (base + URL('g.')           ,  'http://a/b/c/g.'),
    (base + URL('.g')           ,  'http://a/b/c/.g'),
    (base + URL('g..')          , 'http://a/b/c/g..'),
    (base + URL('..g')          , 'http://a/b/c/..g'),
    (base + URL('./../g')       ,  'http://a/b/g'),
    (base + URL('./g/.')        ,  'http://a/b/c/g/'),
    (base + URL('g/./h')        ,  'http://a/b/c/g/h'),
    (base + URL('g/../h')       ,  'http://a/b/c/h'),
#    (base + URL('g;x=1/./y')    ,  'http://a/b/c/g;x=1/y'),
#    (base + URL('g;x=1/../y')   ,  'http://a/b/c/y'),
#    Parameters in other locations that the last path part are
#    currently not supported.
    (base + URL('g?y/./x')      ,  'http://a/b/c/g?y/./x'),
    (base + URL('g?y/../x')     ,  'http://a/b/c/g?y/../x'),
    (base + URL('g#s/./x')      ,  'http://a/b/c/g#s/./x'),
    (base + URL('g#s/../x')     ,  'http://a/b/c/g#s/../x'),
)

works = 1
for i in range(len(tests)):
    test,result = tests[i]
    try:
        assert str(test) == result
    except:
        print 'Test',i,'failed:',test,'!=',result
        works = 0
assert works

### Component tests

print ' Component tests.'
url = URL('ftp://mal:passwd@myhost:123/myfile.tgz')
assert url.scheme == 'ftp'
assert url.user == 'mal'
assert url.passwd == 'passwd'
assert url.host == 'myhost'
assert url.port == 123
assert url.path == '/myfile.tgz'
assert url.ext == 'tgz'
assert url.file == 'myfile.tgz'

url = url + './abc/abc.html'
assert url.path == '/abc/abc.html'
assert url.ext == 'html'
assert url.file == 'abc.html'

print 'Works.'
print

### Benchmarking

import time
import urlparse
basestr = 'http://a/b/c/d'
relstr = '../../g'
print 'Benchmark: basestr=%s relstr=%s' % (repr(basestr),repr(relstr)) 

loops = range(10000)

# Calibration
t = time.clock()
for i in loops:
    urljoin
    basestr
    relstr
calibration = time.clock() - t

urljoin = urlparse.urljoin
t = time.clock()
for i in loops:
    urljoin(basestr,relstr)
print ' urlparse.urljoin(basestr,relstr):',(time.clock() - t - calibration)/len(loops)*1000.0,'msec.'

loops = range(50000)

urljoin = mx.URL.urljoin
t = time.clock()
for i in loops:
    urljoin(basestr,relstr)
print ' URL.urljoin(basestr,relstr):',(time.clock() - t - calibration)/len(loops)*1000.0,'msec.'

t = time.clock()
baseurl = URL(basestr)
for i in loops:
    baseurl + URL(relstr)
print ' baseurl+URL(relstr):',(time.clock() - t - calibration)/len(loops)*1000.0,'msec.'

t = time.clock()
baseurl = URL(basestr)
for i in loops:
    baseurl + RawURL(relstr)
print ' baseurl+RawURL(relstr):',(time.clock() - t - calibration)/len(loops)*1000.0,'msec.'

t = time.clock()
baseurl = URL(basestr)
for i in loops:
    baseurl + relstr
print ' baseurl+relstr:',(time.clock() - t - calibration)/len(loops)*1000.0,'msec.'

t = time.clock()
for i in loops:
    basestr + '/' + relstr
print ' basestr + "/" + relstr:',(time.clock() - t - calibration)/len(loops)*1000.0,'msec.'

urlstr = basestr + relstr
t = time.clock()
for i in loops:
    URL(urlstr)
print ' URL(basestr+relstr):',(time.clock() - t - calibration)/len(loops)*1000.0,'msec.'

