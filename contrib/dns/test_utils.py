#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Collection of small test-scripts, should be converted to unit-test
# framework.

import re
import sys
import getopt

from Cerebrum.Utils import Factory
#from Cerebrum.modules import Host
from Cerebrum import Errors
from Cerebrum import Group

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
db.cl_init(change_program='test')

test_dta = {
    'name': "testmachine",
    'hinfo': 'autogen',
    'ip': '129.240.2.3',
}

def test_cname(a_rec_id):
    cname = Host.CnameRecord(db)
    if True:
        cname.populate("huba.uio.no", a_rec_id, ttl=50)
        print "W=", cname.write_db()
    if False:
        cname.clear()
        cname.find(223599)
        print "Got: ", cname.cname, cname.a_record_id, cname.ttl
        cname.cname = "kake.iuo.no"
        print "W=", cname.write_db()
    db.commit()
    
def clear_db():
    group = Group.Group(db)
    group2 = Group.Group(db)
    for g in group.search(filter_spread=co.spread_uio_machine_netgroup):
        group.clear()
        group.find(g['group_id'])
        for g2 in group.list_groups_with_entity(g['group_id']):
            group2.clear()
            group2.find(g2['group_id'])
            group2.remove_member(g['group_id'], g2['operation'])
        
        group.delete()
        db.commit()
    entity_types = ", ".join(["%i" % i for i in (co.entity_dns_host,
                                                 co.entity_dns_a_record,
                                                 co.entity_dns_owner)])
    db.execute("delete from entity_info where entity_type in (%s)" % entity_types)
    #print "test.clean_db No longer needed"
##     for tab in ('general_ttl_record', 'override_reversemap',
##                 'cname_record', 'mreg_host_info',  'hinfo_code',
##                 'entity_note',
##                 'a_record', 'srv_record', 'dns_owner', 'ip_number'):
        
##         db.execute("delete from %s" % tab)
#    db.execute("delete from entity_name where value_domain=:vd", {'vd': int(co.dns_owner_namespace)})
#    db.commit()


def test_ttl(id):
    cname = Host.CnameRecord(db)
    cname.clear()
    cname.find(id)
    cname.add_general_dns_record(id, co.FieldTypeCode('TXT'), 11, 'noedata')
    db.commit()

auto_hinfo_num = 0
def get_hinfo(cpu, os):
    # TODO: This should be done a cleaner way atleast so that the
    # code_str is meaningful
    try:
        ret = co.HinfoCode(cpu, os)
    except Errors.NotFoundError:
        global auto_hinfo_num
        auto_hinfo_num += 1
        ret = co.HinfoCode('hinfo_%i' % auto_hinfo_num, cpu, os)
        ret.insert()
    return ret

def test_hinfo_code(testname):
    if testname == 'create':  # Test insert and lookup
        try:
            x = co.HinfoCode('SUNFIRE-480R', 'SOLARIS-8')
        except Errors.NotFoundError:
            x = co.HinfoCode('autogen', 'SUNFIRE-480R', 'SOLARIS-8')
            x.insert()
        print x
        print int(x)
    elif testname == '1':
        print co.hi.os, co.hi.cpu
        print co.hi, int(co.hi)
        print co.HinfoCode("auto1").os
    db.commit()
    
def test_host_info(testname):
    host = Host.HostInfo(db)
    if testname == 'create':
        host.populate(test_dta['name'], co.HinfoCode(test_dta['hinfo']))
        host.write_db()
        print "Created, id=%i" % host.entity_id
        db.commit()
    elif testname == 'find':
        host.find_by_name(test_dta['name'])
        print "Found: ", host.name

def test_ip(testname):
    ip = Host.IPNumber(db)
    if testname == 'create':
        ip.populate(test_dta['ip'])
        ip.write_db()
        print "Created, id=%i" % ip.ip_number_id
        db.commit()
    elif testname == 'find':
        ip.find_by_ip(test_dta['ip'])
        print "Found %s, id=%i " % (ip.a_ip, ip.ip_number_id)

def test_a_record(testname):
    ar = Host.ARecord(db)
    
    if testname == 'create':
        ip = Host.IPNumber(db)
        ip.find_by_ip(test_dta['ip'])
        ar.populate(test_dta['name'], ip.ip_number_id)
        ar.write_db()
        print "Created, id=%i" % ar.entity_id
        db.commit()
    elif testname == 'find':
        ar.find_by_name(test_dta['name'])
        print "Found, ", ar.ip_number_id
    
def usage(exitcode=0):
    print """test.py [options]
    --hinfo [create | 1] : run test_hinfo_code
"""
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['help', 'hinfo=', 'host=', 'ip=', 'a=', 'del'])
    except getopt.GetoptError:
        usage(1)
    for opt, val in opts:
        if opt == '--help':
            usage()
        elif opt == '--hinfo':
            test_hinfo_code(val)
        elif opt == '--host':
            test_host_info(val)
        elif opt == '--ip':
            test_ip(val)
        elif opt == '--a':
            test_a_record(val)
        elif opt == '--del':
            clear_db()
    # test_cname(223594)
    #test_ttl(223601)
    # test_hinfo_code()
    
if __name__ == '__main__':
    main()

# arch-tag: 6801b70e-52f9-4f3e-85e4-508e14fe67e1
