import sys
import getopt

try:
    set
except NameError:
    from sets import Set as set


def read(file):
    l=[i[0:-1].split(':') for i in open(file).readlines()]
    s=set([i[0] for i in l])
    #print len(l), len(s)
    #assert len(l) == len(s)
    d={}
    for i in l:
        if d.has_key(i[0]):
            print "Duplikate %s in %s" % (i[0], file)
        d[i[0]]=i
    return l, s, d

def diff(file1, file2, verbose=False):
    l1, s1, d1 = read(file1)
    l2, s2, d2 = read(file2)
    common = s1.intersection(s2)
    deleted = s1.difference(s2)
    added = s2.difference(s1)  
    print "Users %d deleted %d added" % (len(deleted), len(added))
    if verbose:
        for i in deleted:
            print "-" + ":".join(d1[i])
        for i in added:
            print "+" + ":".join(d2[i])
    for field in range(1, 7):
        chkfield(field, common, d1, d2, verbose=verbose)

def chkfield(field, l, d1, d2, verbose=False):
    count=0
    for i in l:
        if d1[i][field] != d2[i][field]:
            count+=1
            if verbose:
                print " %s field %d '%s' -> '%s'" % (
                    i, field, d1[i][field], d2[i][field])
    print "Field %d: %d differ" % (field, count)


def usage():
    print """Usage: %s PASSWDFILE1 PASSWDFILE2
    -v | --verbose : be verbose
    """ % sys.argv[0]
    sys.exit(1)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'v', ['verbose'])
    except getopt.GetoptError:
        usage()

    verbose=False
    for opt,val in opts:
        if opt in ('-v','--verbose'):
            verbose = True

    diff(args[0], args[1], verbose=verbose)


if __name__ == '__main__':
    main()
