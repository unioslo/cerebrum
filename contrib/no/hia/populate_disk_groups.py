#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-
                                                                                                                                            
# Copyright 2004 University of Oslo, Norway
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

"""
Usage: python2.2 populate_disk_groups.py --spread=<spread> --delete_all

--delete_all delete all internal groups for that spread.

--spread (without delete_all) updates and creates internal groups. 

Without spread, it will make groups for all disk with any spread.

Create group based on homedirectories. 
Head for this group:
    'internal:<institution-name>:disk_group'
If spread, head will be:
    ':<institution-name>:disk_group:spread'
Include servers, full name, disks are members of server:
    ':<institution-name>:'disk_group':spread:server'
Disks with members that has homedirectory:
    ':<institution-name>:'disk_group':spread:server:disk'
    
"""
from __future__ import generators

import sre, sys, locale, getopt

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum import Disk
from Cerebrum import Constants
#from __future__ import generators

# Hent ut spread 
# Hent host og samle antall disker bak host_id.



def init_module():
    global db, const, account, del_grp ,logger
    db = Factory.get('Database')()
    db.cl_init(change_program='pop_server_grps')
    const = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    logger = Factory.get_logger("cronjob")
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))
    del_grp = None


def get_account(name):
    account.clear()
    account.find_by_name(name)
    return account
                                                                                                                                
def get_group(id):
    get_grp = Factory.get('Group')(db)
    if isinstance(id, str):
        get_grp.find_by_name(id)
    else:
        get_grp.find(id)
    return get_grp

def get_host(host_id):
    host = Disk.Host(db)
    if isinstance(host_id,str):
	 host.find_by_name(host_id)
    elif isinstance(host_id, int):
	host.find(host_id)
    else:
	logger.warn("Host-id colud not be resolved %s" % host_id)
	host = None
    return(host)

def get_disk(disk_id):
    dsk = Factory.get('Disk')(db)
    if isinstance(disk_id,str):
         dsk.find_by_path(disk_id)
    elif isinstance(disk_id, int):
        dsk.find(disk_id)
    else:
        logger.warn("Host-id colud not be resolved %s" % host_id)
        dsk = None
    return(dsk)

def safe_join(elements, sep=' '):
    """As string.join(), but ensures `sep` isn't part of any element."""
    for i in range(len(elements)):
        if elements[i].find(sep) <> -1:
            raise ValueError, \
                  "Join separator %r found in element #%d (%r)" % (
                sep, i, elements[i])
    return sep.join(elements)

    
def get_host_disks():
    disk_d = {}
    dsk = Factory.get('Disk')(db)
    for disks in dsk.list(spread=u_spread):
	if disks.count == 0:
	    continue
	if disk_d.has_key(int(disks.host_id)):
            disk_d[int(disks.host_id)].append(int(disks.disk_id))
	else:
            disk_d[int(disks.host_id)] = [int(disks.disk_id),]
    return(disk_d)

def remove_memb_parent(group_id, op, member):
    """ Remove membership in parent group"""
    parent = get_group(group_id)
    parent.remove_member(member, op)
    

def destroy_group(group_id):
    del_grp = get_group(group_id)
    u, i, d = del_grp.list_members(member_type=const.entity_group)
    for subg in u:
        destroy_group(subg[1])
    logger.debug("destroy_group(%s) [After get_group]" \
                 % del_grp.group_name)
    #print "destroy_group(%s) [After get_group]" % del_grp.group_name
    for r in del_grp.list_groups_with_entity(del_grp.entity_id):
	logger.debug("Parent id:",r['group_id'],"group-id:", del_grp.entity_id)
	remove_memb_parent(r['group_id'], r['operation'],del_grp.entity_id)
    logger.debug("Removed group:",del_grp.group_name, "group-id:", 
						del_grp.entity_id)
    #print "Removed group:",del_grp.group_name, "group-id:",del_grp.entity_id
    del_grp.delete()
                                                                                                                                                                    


class group_tree(object):

    # Dersom destroy_group() kalles med max_recurse == None, aborterer
    # programmet.
    #max_recurse = None

    # De fleste automatisk opprettede gruppene skal ikke ha noen
    # spread.
    #spreads = ()

    def __init__(self):
	self.subnodes = {}
	self.users = {}

    def name_prefix(self):
	prefix = ()
	parent = getattr(self, 'parent', None)
	if parent is not None:
	    prefix += parent.name_prefix()
	prefix += getattr(self, '_prefix', ())
	return prefix

    def name(self):
	name_elements = self.name_prefix()
	name_elements += getattr(self, '_name', ())
	return safe_join(name_elements, ':').lower()

    def description(self):
	pass

    def list_matches(self, gtype, data, category):
	if self.users:
	    raise RuntimeError, \
		"list_matches() not overriden for user-containing group."
	for subg in self.subnodes.itervalues():
	    for match in subg.list_matches(gtype, data, category):
		yield match

    def list_matches_1(self, *args, **kws):
	ret = [x for x in self.list_matches(*args, **kws)]
	if len(ret) == 1:
	    return ret
	logger.error("Matchet for mange: self=%r, args=%r, kws=%r, ret=%r",
						self, args, kws, ret)
	#print "Matchet for mange: self=%r, args=%r, kws=%r, ret=%r", self, args, kws, ret
	return ()

    def sync(self):
	logger.debug("Start: group_tree.sync(), name = %s", self.name())
	#print "Start: group_tree.sync(), name = %s", self.name()
	db_group = self.maybe_create()
	sub_ids = {}
	if self.users:
	    for acc in self.users.iterkeys():
		sub_ids[int(acc)] = const.entity_account
	else:
            # Gruppa har ikke noen medlemmer, og skal dermed
            # populeres med *kun* evt. subgruppemedlemmer.  Vi sørger
            # for at alle subgrupper synkroniseres først (rekursivt),
            # og samler samtidig inn entity_id'ene deres i 'sub_ids'.
	    for subg in self.subnodes:
		sub_ids[int(subg.sync())] = const.entity_group
        # I 'sub_ids' har vi nå en oversikt over hvilke entity_id'er
        # som skal bli gruppens medlemmer.  Foreta nødvendige inn- og
        # utmeldinger.
	db_group = self.maybe_create()
	membership_ops = (const.group_memberop_union,
				const.group_memberop_intersection,
				const.group_memberop_difference)
	for members_with_op, op in zip(db_group.list_members(),membership_ops):
	    for member_type, member_id in members_with_op:
		member_id = int(member_id)
		if member_id in sub_ids:
		    del sub_ids[member_id]
		else:
		    if member_type == const.entity_account:
			db_group.remove_member(member_id, op)
                    elif member_type == const.entity_group:
                        destroy_group(member_id)
        for member_id in sub_ids.iterkeys():
	    if db_group.entity_id <> member_id:
	    	db_group.add_member(member_id, sub_ids[member_id],
                                const.group_memberop_union)
        #print "Finished: group_tree.sync(), name = %s", self.name()
	logger.debug("Finished: group_tree.sync(), name = %s", self.name()) 
	return db_group.entity_id

    def maybe_create(self):
        try:
            return get_group(self.name())
        except Errors.NotFoundError:
            gr = Factory.get('Group')(db)
            gr.populate(self.group_creator(),
                        const.group_visibility_internal,
                        self.name(),
                        description=self.description())
            gr.write_db()
            return gr

    def group_creator(self):
        acc = get_account(cereconf.INITIAL_ACCOUNTNAME)
        return acc.entity_id

    def __eq__(self, other):
        if type(other) is type(self):
            return (self.name() == other.name())
        return False

    def __ne__(self, other):
        return (not self.__eq__(other))

    def __hash__(self):
        return hash(self.name())




class create_superservgrp(group_tree):
 
    #max_recurse = None
 
    def __init__(self):
	super(create_superservgrp, self).__init__()
	self._prefix = ('internal', cereconf.INSTITUTION_DOMAIN_NAME,
					'disk_group')
	if u_spread:
	     self._prefix += (str(u_spread),)
	
	self._name = ('{supergroup}',)
 
    def description(self):
	return "Group of users at %s based on homedirectory on server" \
					% (cereconf.INSTITUTION_DOMAIN_NAME,)
 
    def add(self, attrs):
        #if gtype == 'host':
	subg = server_grp(self, attrs)
	#if gtype == 'disk':
	#    subg = disk_grp(self, attrs)   
        children = self.subnodes
        if children.has_key(subg):
            subg = children[subg]
        else:
            children[subg] = subg
        subg.add(attrs)


class srv_grp(group_tree):
	
                                                                                                                            
    def __init__(self, parent):
        super(srv_grp, self).__init__()
        self.parent = parent
        self.child_class = None
                                                                                                                                
    def add(self,ue):
        new_child = self.child_class(self, ue)
        children = self.subnodes
        if new_child in children:
            new_child = children[new_child]
        else:
            children[new_child] = new_child
        new_child.add(ue)


class server_grp(srv_grp):
                   
    #max_recurse = 2                                                                                                           
                                                                                                                                
    def __init__(self, parent, ue):
        super(server_grp, self).__init__(parent)
        self._prefix = ((ue.name + '.' + cereconf.INSTITUTION_DOMAIN_NAME),)
        self.child_class = disk_grp
                                                                                                                                
    def description(self):
        return ("Server in %s " % cereconf.INSTITUTION_DOMAIN_NAME)

    #def add(self,ue):
	


class disk_grp(srv_grp):

    #max_recurse = 1

    def __init__(self, parent, ue):
        super(disk_grp, self).__init__(parent)
	self._prefix = (ue.path,)
        self.child_class = None
                                                                                                                                            
    def description(self):
        return ("Disk in %s " %
                cereconf.INSTITUTION_DOMAIN_NAME)

    def add(self, ue):
	self.users = {}
	for acc in [x['account_id'] for x in account.list_account_home(\
                                                        account_spread=u_spread,
                                                        disk_id=ue.entity_id)]:
	    self.users[int(acc)] = const.entity_account

                                                                                                                                

def usage(err=0):
    if err:
        print >>sys.stderr, err
    print >>sys.stderr, __doc__
    sys.exit(bool(err))

def add_disk(s_grp):
    for host_id, disk_list in get_host_disks().items():
	host = get_host(host_id)
	for disk_id in disk_list:
	    disk = get_disk(disk_id)
	    disk.name = host.name
	    s_grp.add(disk)


def main():
    opt_s = del_all = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hs:d",
                                   ("help", "spread=","delete_all"))
    except getopt.GetoptError, e:
        usage(str(e))
    if args:
        usage("Invalid arguments: " + " ".join(args))
    for opt, val in opts:
	if opt in ("-s", "--spread"):
            opt_s = val
	elif opt in ("-d","--delete_all"):
	    del_all = True
    global u_spread
    u_spread = None
    init_module()
    if opt_s:
	try:
	    u_spread = Constants._SpreadCode(int(opt_s))
	except ValueError:
	    try:
		u_spread = getattr(const,opt_s)
	    except AttributeError:
		u_spread = Constants._SpreadCode(opt_s)
	    except:
		usage(1)
    s_grp = create_superservgrp()
    if del_all:
	try:
	    grp_name = safe_join((s_grp._prefix + s_grp._name), ':').lower()
	    del_tree = get_group(grp_name)
	except Errors.NotFoundError:
	    logger.warn("Supergroup %s could not be found" % grp_name)	    
	    #print "Supergroup %s could not be found" % grp_name
	destroy_group(del_tree.entity_id)
    else:	
	add_disk(s_grp)
	s_grp.sync()
    logger.debug("Start commit to database")
    db.commit()
    db.close()
    # db.close() Because of local setup in postgres, remove after test
    

if __name__ == '__main__':
    main()


# arch-tag: 52d78168-b120-4533-959f-6573e8597f76
