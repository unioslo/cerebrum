


import os
import re
import sys
import string

from Cerebrum.Utils import Factory
from Cerebrum import Disk

local_uio_domain = {}
home2spool = {}

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
no_uio = '\.uio\.no$'

def list_machines():
    disk = Disk.Disk(db)
    res = []
    pat = r'\/(\S+)\/(\S+)\/'
    for d in disk.list():
        path = d['path']
        r = re.search(pat, path)
        res.append([r.group(1), r.group(2)])
    return res

def make_home2spool():
    spoolhost = {}
    cname_cache = {}
    # Define domains in zone uio.no whose primary MX is one of our
    # mail servers as "local domains".
    out = os.popen("/local/bin/host -t mx -l uio.no. nissen.uio.no")
    res = out.readlines()
    out.close()

    curdom, lowpri, primary = "", "", ""
    pat = r'^(\S+) mail is handled by (\d+) (\S+)\.'
    for line in res:
        m = re.search(pat, line)
        if m:
            dom = string.lower(m.group(1))
            pri = int(m.group(2))
            mx = string.lower(m.group(3))
            dom = re.sub(no_uio, '', dom)
            mx = re.sub(no_uio, '', mx)
            if dom == "platon" and mx == 33:
                print dom, mx
            if not curdom:
                curdom = dom
            if curdom == "" and curdom != dom:
                # validate_prim
                curdom = dom
                lowpri, primary = "", ""
            if not lowpri or pri < lowpri:
                lowpri, primary = pri, mx
            if int(pri) == 33:
                spoolhost[dom] = mx

    if curdom and primary:
        # validate_prim
        pass

    # We have now defined all "proper" local domains (i.e. ones that
    # have explicit MX records).  We also want to accept mail for any
    # CNAME in the uio.no zone pointing to any of these local domains.

    out = os.popen("/local/bin/host -t cname -l uio.no. nissen.uio.no")
    res = out.readlines()
    out.close()

    pat = r'^(\S+) is an alias for (\S+)\.'
    for line in res:
        m = re.search(pat, line)
        if m:
            alias, real = string.lower(m.group(1)), string.lower(m.group(2))
            alias = re.sub(no_uio, '', alias)
            real = re.sub(no_uio, '', real)
            if local_uio_domain.has_key(real):
                local_uio_domain[alias] = local_uio_domain[real]
            if spoolhost.has_key(real):
                spoolhost[alias] = spoolhost[real]

    # Define domains in zone ifi.uio.no whose primary MX is one of our
    # mail servers as "local domains".  Cache CNAMEs at the same time.

    out = os.popen("/local/bin/dig \@bestemor.ifi.uio.no ifi.uio.no. axfr")
    res = out.readlines()
    out.close()

    pat = r'^(\S+)\.\s+\d+\s+IN\s+MX\s+(\d+)\s+(\S+)\.'
    pat2 = r'^(\S+)\.\s+\d+\s+IN\s+CNAME\s+(\S+)\.'
    for line in res:
        m = re.search(pat, line)
        if m:
            dom = string.lower(m.group(1))
            pri = int(m.group(2))
            mx = string.lower(m.group(3))
            dom = re.sub(no_uio, '', dom)
            mx = re.sub(no_uio, '', mx)
            if not curdom:
                curdom = dom
            if curdom == "" and curdom != dom:
                #validate_prim
                curdom = dom
                lowpri, primary = "", ""
            if not lowpri or pri < lowpri:
                lowpri, primary = pri, mx
            if pri == 33:
                spoolhost[dom] = mx
        else:
            m = re.search(pat2, line)
            if m:
                alias = string.lower(m.group(1))
                real = string.lower(m.group(2))
                alias = re.sub(no_uio, '', alias)
                real = re.sub(no_uio, '', real)
                cname_cache[alias] = real

    if curdom and primary:
        # validate_prim
        pass

    # Define CNAMEs for domains whose primary MX is one of our mail
    # servers as "local domains".

    for alias in cname_cache.keys():
        real = cname_cache[alias]
        if local_uio_domain.has_key(real):
            local_uio_domain[alias] = local_uio_domain[real]
        if spoolhost.has_key(real):
            spoolhost[alias] = spoolhost[real]

    for faculty, host in list_machines():
        host = string.lower(host)
        if host == '*':
            continue
        if faculty == "ifi":
            if spoolhost.has_key(host):
                print "MX 33 of host %s.ifi implies spoolhost %s, ignoring." % (
                    host, spoolhost[host])
            spoolhost[host] = "ulrik"
            continue
        elif not spoolhost.has_key(host):
            print "Host '%s' defined in UREG2000, but has no MX" \
                  "-- skipping..." % host
            continue
        if spoolhost[host] == "ulrik":
            continue
        home2spool["/%s/%s" % (faculty, host)] = "/%s/%s/mail" % (
            faculty, spoolhost[host])


if __name__ == '__main__':
    make_home2spool()
