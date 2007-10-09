#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import config
import sys
import cerebrum_path
import cereconf
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.ntnu import access_BDB
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup

import mx
import util
import getopt
import logging
import time
import os
import traceback

import locale
locale.setlocale(locale.LC_ALL,'nb_NO')


"""
Import Groups from a given backend (file or relational backend) 
"""

# Set the client encoding for the Oracle client libraries
os.environ['NLS_LANG'] = config.conf.get('bdb', 'encoding')
verbose = False
dryrun = False
show_traceback = False

def usage():
    print """
    Usage: %s <options>

    Valid options are:
    -f <filename>       Imports from a groupfile. Default /etc/group
    -g                  Imports from NTNUs Gruppesenter
    -k                  Imports from NTNUs Kundesenter
    -v                  Verbose output
    -d                  Dryryn. Don't commit possible changes to database
    --add-missing       Add groups if they don't exists
    """ % sys.argv[0]
    sys.exit(1)

def validate_name(name):
    valid = True
    if name[0] == '#':
        valid = False
    return valid

def validate_members(members):
    valid = True
    return valid

def _is_posix(group):
    res = True
    if not 'unix_gid' in group:
        res = False
    return res

class GroupSync:
    def __init__(self):
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program='import_group')
        self.const = Factory.get('Constants')(self.db)
        self.ac = Factory.get('Account')(self.db)
        self.group = Factory.get('Group')(self.db)
        self.posix_group = PosixGroup.PosixGroup(self.db)
        #self.logger = Factory.get_logger("syslog")
        self.logger = Factory.get_logger("console")
        self.logger.info("Starting import_group")
        self.ac.find_by_name('bootstrap_account')
        self.initial_account = self.ac.entity_id
        self.ac.clear()

        self.ac.clear()
        self.ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        self.default_creator_id = self.ac.entity_id
        self.ac.clear()

    def _get_members(self,group):
        members = []
        ac = self.ac
        for username in group.get('members'):
            ac.clear()
            try:
                ac.find_by_name(username)
            except Errors.NotFoundError:
                self.logger.warning("Member %s of group %s not found in Cerebrum" % (username,group.get('name')))
            else:
                members.append(ac.entity_id)
        return members

    def sync_membership(self,group):
        # Need to get a list of
        # 1. new members
        # 2. members to remove
        self.logger.info("Process membership on group %s" % group.get('name'))
        grp = self.group
        const = self.const
        grp.clear()
        try:
            grp.find_by_name(group.get('name'))
        except Errors.NotFoundError:
            raise Errors.NotFoundError
        else:
            c_members = grp.get_members() # Set
            g_members = self._get_members(group) 
            for member in g_members:
                if member not in c_members:
                    grp.add_member(member,const.entity_account,const.group_memberop_union)


    def clean_name(self,name):
        result = name.replace(' ','_')
        result = result.replace('-','_')
        return result


    def sync_group(self,group,add_missing_group=True):
        """
        @group is groupname
        @members is a list members
        @add_missing_group toggles wether a group should be added if it doesn't exists
        """
        logger = self.logger
        grp = self.group
        pg  = self.posix_group
        grp.clear()
        pg.clear()
        show_all = self.const.group_visibility_all
        name = self.clean_name(group.get('name'))
        try:
            grp.find_by_name(name)
        except Errors.NotFoundError:
            if add_missing_group: 
                creator_id=self.initial_account
                if _is_posix(group):
                    posix_gid = group.get('unix_gid')
                    pg.populate(creator_id=creator_id, visibility=show_all, name=name, 
                                gid=posix_gid )
                    pg.write_db()
                else:
                    grp.populate(creator_id=creator_id, visibility=show_all, name=name)
                    grp.write_db()
            else:
                logger.info("Group %s not exist and not added" % group['name'])
        else:
            self.sync_membership(group)
            return


class GroupCenter(GroupSync):

    def sync_groups(self):
        for group in self.gruppesenter.get_groups():
            try:
                self.sync_group(group)
            except Exception,e:
                self.logger.error("%s failed. Reason: %s" % (group.get('name'),e))
                self.db.rollback()
            else:
                if dryrun:
                    self.db.rollback()
                else:
                    self.db.commit()

class GroupFile(GroupSync):

    def process_file(self,filename):
        groups = []
        if verbose:
            print "Start processing file %s" % filename
        f = open(filename,'r')
        for line in f.readlines():
            name,blapp,gid,members = line.split(':')
            if validate_name(name) and validate_members(members):
                tmp = members.split(',')
                members = []
                for member in tmp:
                    members.append(member.strip()) 
                groups.append({'name': name, 'unix_gid': gid, 'members': members})
                if verbose:
                    print "processing group %s" % name
            else:
                print "Warning! Failed to validate %s with members %s" % (name,members)
                continue
        if verbose:
            print "Done processing file %s" % filename
        return groups
        
    def sync_groups(self,groupfile="/etc/group"):
        groups = self.process_file(groupfile)
        print "File %s processed. Continuing" % groupfile
        for group in groups:
            try:
                self.sync_group(group)
            except Exception,e:
                self.logger.error("%s failed. Reason: %s" % (group.get('name'),e))
                self.db.rollback()
            else:
                if dryrun:
                    self.db.rollback()
                else:
                    self.db.commit()

class KundesenterGroup(GroupSync):
    def sync_groups(self):
        print "Not implemented yet"

def main():
    if len(sys.argv) < 1:
        usage()

    global verbose,dryrun
    opts,args = getopt.getopt(sys.argv[1:],'hdvgkf:',
            ['help','gruppesenter','kundesenter','gruppefil'])
    for opt,val in opts:
        if opt in ('-h','--help'):
            usage()
        elif opt in ('-v',):
            verbose = True
        elif opt in ('-d',):
            dryrun = True
        elif opt in ('-f',):
            filename = val
            group = GroupFile()
            if not filename:
                group.sync_groups()
            else:
                group.sync_groups(filename)
        elif opt in ('-g',):
            group = GroupCenter()
            group.sync_groups()
        elif opt in ('-k',):
            group = KundesenterGroup()
            group.sync_groups()
        else:
            usage()
    
if __name__ == '__main__':
    main()

