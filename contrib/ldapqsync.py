import string,ldap,ldif,sys,ldapurl,locale,base64,sys,getopt,os,re,time
import cerebrum_path
import cereconf
from ldap import modlist
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum import Disk
from Cerebrum import Entity
from Cerebrum import QuarantineHandler 
from Cerebrum.Utils import Factory,latin1_to_iso646_60
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum.Constants import _SpreadCode
from Cerebrum.extlib import logging
from Cerebrum.modules import CLHandler
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
const = Factory.get('CLConstants')(db)
co = Factory.get('Constants')(db)
cltype = {}
cl_entry = {'group_mod' : 'pass', 				
	'group_add' : 'group_mod(cll.change_type_id,cll.subject_entity,\
							cll.dest_entity)',
	'group_rem' : 'group_mod(cll.change_type_id,cll.subject_entity,\
							cll.dest_entity)',
	'account_mod' : 'mod_account(cll.subject_entity,i)',
	'spread_add' : 'change_spread(cll.subject_entity,cll.change_type_id,\
							cll.change_params)',
	'spread_del' : 'change_spread(cll.subject_entity,cll.change_type_id,\
							cll.change_params)',
	'quarantine_add' : 'change_quarantine(cll.subject_entity,\
							cll.change_type_id)',
	'quarantine_mod' : 'change_quarantine(cll.subject_entity,\
							cll.change_type_id)',
	'quarantine_del' : 'change_quarantine(cll.subject_entity,\
							cll.change_type_id)'}
ldapfiles = []
global user_dn, person_dn, group_dn, ngroup_dn
bas = cereconf.LDAP_BASE
org_att = cereconf.LDAP_ORG_ATTR
user_dn = "%s=%s,%s" % (org_att,cereconf.LDAP_USER_DN,bas)
person_dn = "%s=%s,%s" % (org_att,cereconf.LDAP_PERSON_DN,bas)
group_dn = "%s=%s,%s" % (org_att,cereconf.LDAP_GROUP_DN,bas)
ngroup_dn = "%s=%s,%s" % (org_att,cereconf.LDAP_NETGROUP_DN,bas) 

def mod_ldap(ldap_mod,attr,attr_value,dn_value,list=None):
    if list:
	ldif_list = [(ldap_mod,attr,attr_value)]
    else:
    	ldif_list = [(ldap_mod,attr,(attr_value,))]
    result_ldap_mod = l.modify(dn_value,ldif_list)
    log_str = '\n' + ldif.CreateLDIF(dn_value,ldif_list)
    if result_ldap_mod:
	log_diff.write(log_str)
    else:
	log_fail.write(log_str)
    return

def add_ldap(dn_value,ldif_list):
    result_add_ldap = l.add(dn_value,ldif_list)
    log_str = '\n' + ldif.CreateLDIF(dn_value,ldif_list)
    if result_add_ldap:
	log_diff.write(log_str)
    else:
        log_fail.write(log_str)

def delete_ldap(dn_value):
    result_del_ldap = l.delete(dn_value)
    log_str = ldif.CreateLDIF(dn_value,{'changetype': ('delete',)})
    if result_del_ldap:
        log_diff.write(log_str)
    else:
        log_fail.write(log_str)

def mod_account(dn_id,i):
    j = i + 1
    account = Account.Account(db)
    account.clear()
    account.find(dn_id)
    if (j < len(ch_log_list)):
	try:
	    if ((ch_log_list[j]['change_type_id']) == \
			int(const.account_password)):
		change_passwd(dn_id)
	except: pass 
    else:
	  for entry in cereconf.LDAP_USER_SPREAD:
	    if not account.has_spread(getattr(co,entry)):
		continue
	    search_str = "%s=%s" % (cereconf.LDAP_USER_ATTR,
					account.account_name)
	    ldap_entry = get_ldap_value(user_dn,search_str,None)
	    dn_str,ldap_entry_u = ldap_entry[0][0]
	    base_entry = get_user_info_dict(dn_id)
	    for entry in base_entry.keys():
		if (ldap_entry_u[entry] <> base_entry[entry]):
		    value =  (str(base_entry[entry]))[2:-2]
		    mod_ldap(ldap.MOD_REPLACE,entry,value,dn_str)

def get_user_info_dict(dn_id):
    return_dict = {}
    for entry in get_user_info(dn_id):
	return_dict[entry[0]] = entry[1]
    return(return_dict)


def change_passwd(dn_id):
    acc = Account.Account(db)
    acc.find(int(dn_id))
    search_str = "%s=%s" % (cereconf.LDAP_USER_ATTR,acc.account_name)
    search_dn = "%s,%s" % (search_str,user_dn)
    passwd_attr = 'userPassword'
    attr_list = []
    try:
    	new_passwd = "{crypt}%s" % \
		acc.get_account_authentication(co.auth_type_md5_crypt)
    except Errors.NotFoundError: 
	try:
	    new_passwd = "{crypt}%s" % \
		acc.get_account_authentication(co.auth_type_crypt3_des)
	except Errors.NotFoundError:
	    new_passwd = "{crypt}*Invalid"
    try:
	quarant = acc.get_entity_quarantine()
    except Errors.NotFoundError: pass
    try:
	valid_spread = False
	for spreads in cereconf.LDAP_USER_SPREAD:
	    if acc.has_spread(getattr(co,spreads)):
		valid_spread = True
    except Errors.NotFoundError: pass
    attr_list.append(passwd_attr)
    ldap_res = get_ldap_value(user_dn,search_str,attr_list)
    if ldap_res:
	old_passwd = str(ldap_res[0][0][1]['userPassword'])
	if (re.sub('\W','',old_passwd)) == (re.sub('\W','',new_passwd)):
	    pass_ch = False
	else: 
	    pass_ch = True
    ldap_people_res = get_ldap_value(person_dn,search_str,None)
    if pass_ch and valid_spread and not quarant:
	mod_ldap(ldap.MOD_REPLACE,passwd_attr,new_passwd,search_dn)
    if ldap_people_res and not quarant:
	pers_dn = "%s,%s" % (search_str,person_dn)	
	mod_ldap(ldap.MOD_REPLACE,passwd_attr,new_passwd,pers_dn)

def change_quarantine(dn_id,ch_type):
    acc = Account.Account(db)
    posixuser = PosixUser.PosixUser(db)
    try:
	acc.find(dn_id)
    except Errors.NotFoundError: 
	log_fail.write("\n#ID:%s was no account!" % dn_id)
    search_str = "%s=%s" % (cereconf.LDAP_USER_ATTR,acc.account_name)
    search_dn = "%s,%s" % (search_str,user_dn)
    try:
	for spreads in cereconf.LDAP_USER_SPREAD:
	    if acc.has_spread(getattr(co,spreads)):
		posixuser.find(dn_id)
		valid_spread = True
    except Errors.NotFoundError: pass
    user = {}
    passwd = 'userPassword'
    shells = 'loginShell'
    try:
	user[passwd] = "{crypt}%s" % \
		acc.get_account_authentication(co.auth_type_md5_crypt)
    except Errors.NotFoundError:
        try:
	    user[passwd] = "{crypt}%s" % \
		acc.get_account_authentication(co.auth_type_crypt3_des)
	except Errors.NotFoundError: 
		user[passwd] = '{crypt}*Invalid'
    ldap_people_res = get_ldap_value(person_dn,search_str,None)
    pers_string = '%s,%s' % (search_str,person_dn)
    quaran = eval_quarantine(dn_id)
    if (int(ch_type) == int(co.quarantine_del)) and \
		valid_spread and quaran is None:
	mod_ldap(ldap.MOD_REPLACE,shells,
			posixuser.shell,search_dn)
	mod_ldap(ldap.MOD_REPLACE,passwd,
			user[passwd],search_dn)
	if ldap_people_res:
	    mod_ldap(ldap.MOD_REPLACE,passwd,user[passwd],pers_string)
    elif valid_spread and quaran is not None:
	for attr,value in quaran.items():
	    mod_ldap(ldap.MOD_REPLACE,attr,value,search_dn)
        if ldap_people_res:
            mod_ldap(ldap.MOD_REPLACE,passwd,quaran[passwd],pers_string)
    elif ldap_people_res and not valid_spread:
	if (int(ch_type) == int(co.quarantine_del)) and quaran is not None:
	    mod_ldap(ldap.MOD_REPLACE,passwd,new_passwd,pers_string)
	elif quaran:
	    new_passwd = '{crypt}*Locked'
	    mod_ldap(ldap.MOD_REPLACE,passwd,quaran[passwd],pers_string)
    else: pass

def eval_quarantine(dn_id):
    account = Account.Account(db)
    account.find(dn_id)
    now = db.DateFromTicks(time.time())
    quarantines = []
    for row in account.get_entity_quarantine():
	if (row['start_date'] <= now
                    and (row['end_date'] is None or row['end_date'] >= now)
                    and (row['disable_until'] is None
                         or row['disable_until'] < now)):
	    quarantines.append(row['quarantine_type'])
    if quarantines == []:
	return(None)
    else:
	params = {}
	qh = QuarantineHandler.QuarantineHandler(db, quarantines)
	if qh.should_skip():
	    pass #raise UserSkipQuarantine
	if qh.is_locked():
	    params['userPassword'] = '[crypt]*locked'
	qshell = qh.get_shell()
	if qshell is not None:
	   params['loginShell'] = qshell
	return(params)


def change_spread(dn_id,ch_type,ch_params):
    """Spread can be users, filegroup or netgroup. Since e_account.create 
    not necesary include spread to posix, creation of user-,filegroup- and
    netgroup-record will be based on add/mod/del spread"""
    entity = Entity.Entity(db)
    entity.find(int(dn_id))
    """What to do with ch_param"""
    if entity.entity_type == int(co.entity_account):
	change_user_spread(dn_id,ch_type,ch_params)
    elif entity.entity_type == int(co.entity_group):
	change_group_spread(dn_id,ch_type,ch_params)
    else:
	log_fail.write("\n# Change_spread did not resolve request (%s,%s)" 
					% (dn_id,ch_type)) 

def change_user_spread(dn_id, ch_type, ch_params):
    account = Account.Account(db)
    posixuser = PosixUser.PosixUser(db)
    param_list = []
    param_list = string.split(ch_params,'\n')
    u_spread = int(re.sub('\D','',param_list[3]))
    for entry in cereconf.LDAP_USER_SPREAD:
	if not (u_spread == int(getattr(co,entry))):
	    continue
	try:
            account.find(dn_id)
	except Errors.NotFoundError:
            log_fail.write("\n# ID:%s was no account!" % dn_id)
            break
    	uname = account.get_name(co.account_namespace)
    	valid_spread = False
    	for entry in cereconf.LDAP_USER_SPREAD:
	    if account.has_spread(getattr(co,entry)):
		valid_spread = True
    	search_str = "%s=%s" % (cereconf.LDAP_USER_ATTR,account.account_name)
    	search_dn = "%s,%s" % (search_str,user_dn)
    	ldap_res = get_ldap_value(user_dn,search_str,None)
    	if ldap_res and int(ch_type) == int(co.spread_add):
	    log_fail.write("\n# Cant create user, exist in LDAP(%s,%s)" % \
							(dn_id,ch_type))
	elif not ldap_res and int(ch_type) == int(co.spread_del):
	    log_fail.write("\n# Cant delete user, doesnt exist(%s,%s)" % \
							(dn_id,ch_type)) 
	elif not ldap_res and (int(ch_type) == int(co.spread_add)) and \
							valid_spread:
	    ldif_list = get_user_info(dn_id)
	    if ldif_list:
		add_ldap(search_dn,ldif_list)
	    else:
		log_fail.write("\n# Add_spread didn't res request(%s,%s)" % \
							(dn_id, ch_type))
	elif ldap_res and (int(ch_type) == int(co.spread_del)):
	    result_del_ldap = delete_ldap(search_dn)
	else:
	    log_fail.write("\n# Spread-change could not be processed(%s,%s)" %\
							(dn_id, ch_type))
	    
def change_group_spread(dn_id,ch_type,ch_params):
    posixgroup = PosixGroup.PosixGroup(db)
    posixgroup.find(dn_id)
    group_name = posixgroup.get_name(co.group_namespace)
    param_list = []
    param_list = string.split(ch_params,'\n')
    g_spread = int(re.sub('\D','',param_list[3]))
    for entry in cereconf.LDAP_GROUP_SPREAD:
	if int(getattr(co,entry)) == g_spread:
	    dn_path = group_dn
	    dn_attr = "%s=%s" % (cereconf.LDAP_GROUP_ATTR,group_name) 
	    dn_value = "%s,%s" % (dn_attr,group_dn)
    for entry in cereconf.LDAP_NETGROUP_SPREAD:
	if int(getattr(co,entry)) == g_spread:
	    dn_path = ngroup_dn
	    dn_attr = "%s=%s" % (cereconf.LDAP_NETGROUP_ATTR,group_name)
            dn_value = "%s,%s" % (dn_attr,ngroup_dn)
    if dn_path: #and posixgroup.has_spread(g_spread):
    	ldap_res = get_ldap_value(dn_path,dn_attr,None)
	if (int(ch_type) == int(co.spread_del)) and ldap_res:
	    delete_ldap(dn_value)
	elif (int(ch_type) == int(co.spread_add)) and not ldap_res:
	    if dn_path == group_dn:
		ldif_list = get_group_info(dn_id,group_name)
	    else:
		ldif_list = get_netgroup_info(dn_id,group_name)
	    add_ldap(dn_value,ldif_list)
	else: pass
    else: pass
	

def get_user_info(dn_id):
    pos = PosixUser.PosixUser(db)
    disk = Disk.Disk(db)
    acc = Account.Account(db)
    shells = disks = {}
    for sh in pos.list_shells():
	shells[int(sh['code'])] = sh['shell']
    for hd in disk.list():
        disks[int(hd['disk_id'])] = hd['path']
    objcl_list = []
    objcl_list.append('top')
    for obj in cereconf.LDAP_USER_OBJECTCLASS:
	objcl_list.append(obj)
    try:
	pos.clear()
	pos.find(dn_id)
	acc.find(dn_id)
	if not pos.gecos:
	    cn_name = gecos = pos.get_gecos()
	else:
	    gecos = pos.gecos
	try:
	    user_home = pos.get_home()
	except:
	    user_home = disks[int(acc.disk_id)] + '/' + acc.account_name
	user_shell = shells[int(pos.shell)]
	if not cn_name:
	    cn_name = pos.get_gecos()
	try:
	    passwd = "{crypt}%s" % \
		pos.get_account_authentication(co.auth_type_md5_crypt)
	except Errors.NotFoundError:
	    try:
		passwd = "{crypt}%s" % \
			pos.get_account_authentication(co.auth_type_crypt3_des)
	    except Errors.NotFoundError: passwd = '{crypt}*Invalid'
	quaran = eval_quarantine(dn_id)
	if quaran is not None:
	    try:
	    	passwd = quaran['userPassword']
	    	user_shell = quaran['loginShell']
	    except: pass
	ldif_list = modlist.addModlist({'objectClass': objcl_list,
					'cn': [cn_name],
					'uid': [pos.account_name],
					'uidNumber': [str(pos.posix_uid)],
					'gidNumber': [str(pos.gid_id)],
					'homeDirectory': [user_home],
					'userPassword': [passwd],
					'loginShell': [user_shell],
					'gecos': [gecos]})
	return(ldif_list)
    except: return(None)

def get_group_info(dn_id,group_name):
    posixgroup = PosixGroup.PosixGroup(db)
    account = Account.Account(db)
    group = Group.Group(db)
    try:
	posixgroup.find(dn_id)
	objcl_list = []
	objcl_list.append('top')
	for obj in cereconf.LDAP_GROUP_OBJECTCLASS:
	    objcl_list.append(obj)
	ldif_list = modlist.addModlist({'objectClass': objcl_list})
	ldif_list.append(('cn',[group_name]))
	ldif_list.append(('gidNumber',[str(posixgroup.posix_gid)]))
	if posixgroup.description:
	    ldif_list.append(('description', 
		[latin1_to_iso646_60(posixgroup.description)]))
	member = []
	group.find(dn_id)
	for memb in group.get_members(spread=int(getattr(co,\
					cereconf.LDAP_USER_SPREAD[0]))):
	    account.clear()
	    account.entity_id = int(memb)
	    member.append(account.get_name(co.account_namespace))
	ldif_list.append(('memberUid',member))
    	return(ldif_list)
    except: return(None)

def get_netgroup_info(dn_id,group_name):
    posixgroup = PosixGroup.PosixGroup(db)
    account = Account.Account(db)
    group = Group.Group(db)
    try:
        group.find(dn_id)
        objcl_list = []
        objcl_list.append('top')
        for obj in cereconf.LDAP_NETGROUP_OBJECTCLASS:
            objcl_list.append(obj)
        ldif_list = modlist.addModlist({'objectClass': objcl_list})
        ldif_list.append(('cn',[group_name]))
        if group.description:
            ldif_list.append(('description', 
			[latin1_to_iso646_60(group.description)]))
        member = []
	u_spread = int(getattr(co,cereconf.LDAP_USER_SPREAD[0]))
        for memb in group.list_members(u_spread,int(co.entity_account))[0]:
            account.clear()
            account.entity_id = int(memb[1])
	    member_str = "(,%s,)" % \
		account.get_name(co.account_namespace).replace('_','')
            member.append(member_str)
        ldif_list.append(('nisNetgroupTriple',member))
	# list_members method can only resolve one spread. 
	# Spread should not be None.
	groups = []  
	for group_entry in group.list_members(None,int(co.entity_group))[0]:
	    group.clear()
            group.find(int(group_entry[1]))
            groups.append(group.group_name)
	ldif_list.append(('membernisNetgroup',groups))
        return(ldif_list)
    except: return(None)
 
def load_spread(spread):
    sp_table = []
    for entry in spread:
	sp_table.append(int(getattr(co,entry)))
    return(sp_table)

def change_user(dn_id,ch_type):
    account = Account.Account(db)
    
def group_mod(ch_type,dn_id,dn_dest):
    account = Account.Account(db)
    group = Group.Group(db)
    group.clear()
    account.clear()
    group.entity_id = int(dn_dest)
    account.entity_id = int(dn_id)
    for row in group.get_spread():
	netgroup_spread = load_spread(cereconf.LDAP_NETGROUP_SPREAD)
	group_spread = load_spread(cereconf.LDAP_GROUP_SPREAD)
	user_spread = load_spread(cereconf.LDAP_USER_SPREAD)
	if int(row['spread']) in group_spread:
	    base_dn = "%s=%s,%s" % (cereconf.LDAP_GROUP_ATTR,
				group.get_name(co.group_namespace),group_dn)
	    user = account.get_name(co.account_namespace)
	    memb_attr = "memberUid"
	    member_uid = "%s=%s" % (memb_attr, user)
	    res_ldap_fg = get_ldap_value(base_dn, member_uid, None)
	    if (ch_type == const.group_add) and (res_ldap_fg == []):
		mod_ldap(ldap.MOD_ADD,memb_attr,user,base_dn)
	    elif (ch_type == const.group_rem) and (res_ldap_fg == []):
		text = "\n# User %s cant be deleted from %s."% (user,base_dn)
		log_fail.write(text)
	    elif (ch_type == const.group_add) and (res_ldap_fg[0][0][0]):
		text = "\n# User %s cant be added,already exist in %s" % (user,
								       base_dn)
		log_fail.write(text)
	    elif (ch_type == const.group_rem) and (res_ldap_fg[0][0][0]):
		mod_ldap(ldap.MOD_DELETE,memb_attr,user,base_dn)
	    elif res_ldap_fg is None: 
		if (ch_type == const.group_add):
		    ldif_list = [(ldap.MOD_ADD,membattr,(user,))]
		else:
		    ldif_list = [(ldap.MOD_DELETE,membattr,(user,))]
		log_str = '\n' + ldif.CreateLDIF(base_dn,ldif_list)
		log_fail(log_str)
	    else:
		log_fail.write("Totally wrong with entry ") 
	elif int(row['spread']) in netgroup_spread:
	    base_dn = "ou=%s,%s" % (cereconf.LDAP_NETGROUP_DN,
					cereconf.LDAP_BASE)
	    search_dn = "%s=%s" % (cereconf.LDAP_NETGROUP_ATTR,
					group.get_name(co.group_namespace))
	    full_dn = "%s,%s" % (search_dn,base_dn)
	    valid_group = True
	    for entry in netgroup_spread:
		if account.has_spread(entry):
                    ng_search_attr = 'memberNisNetgroup'
                    nisnetgroup = account.get_name(co.group_namespace)
                    search_dn_group = "(&(%s)(%s=%s))" % (search_dn,
                                        ng_search_attr,nisnetgroup)
		    res_ldap_ng = get_ldap_value(base_dn, search_dn, None)
		    if (res_ldap_ng == []):
			log_fail.write("\n# Group does not exist in LDAP")
			valid_group = False
		    else:
			res_ldap_mem = get_ldap_value(base_dn,
							search_dn_group,None)
			if ((res_ldap_mem == []) and \
				(int(ch_type) == int(const.group_add))):
			    ldap_mod(ldap.MOD_ADD,ng_search_attr,
							nisnetgroup,full_dn)
			elif ((res_ldap_mem <> []) and \
				(int(ch_type) == int(const.group_rem))):
			    ldap_mod(ldap.MOD_DELETE,ng_search_attr,
							nisnetgroup,full_dn)
			else:
			    log_fail.write("\n# Unknown operation")
			break  
	    for entry in user_spread:
		if account.has_spread(entry):
		    # Do "value_domain" search instead beacause of host
		    ng_search_attr = 'nisNetgroupTriple'
		    nisnetgroup_user = account.get_name(co.account_namespace)
		    nisnetgroup = "(,%s,)" % nisnetgroup_user
		    res_ldap_ng = get_ldap_value(base_dn,search_dn,None)
		    if (res_ldap_ng == []):
			#log_failed(ldif,proper_text)
			log_fail.write("\n# Group does not exist in LDAP")
			valid_group = False
		    else:
			ng_entry_exist = False
			for xx in res_ldap_ng[0][0][1][ng_search_attr]:
			    x,y,z = string.split(xx,',',3)
			    if y == nisnetgroup_user:
				ng_entry_exist = True
	    if valid_group and (ng_search_attr == 'nisNetgroupTriple'):
		if (ng_entry_exist and (ch_type == const.group_add)):  
		    log_fail.write("\n# User exist, can't add user %s" % \
							nisnetgroup_user)
		elif (not ng_entry_exist and (ch_type == const.group_rem)):  
		    log_fail.write("\n# User doesnt exist, can't del(%s,%s)"\
							 % (dn_dest,dn_id))
		elif (ng_entry_exist and (ch_type == const.group_rem)):
		    res_l = res_ldap_ng[0][0][1]
		    ldap_mod(ldap.MOD_DELETE,ng_search_attr,
			res_l[ng_search_attr],full_dn,list=True)
		    res_l[ng_search_attr].remove(nisnetgroup)
		    ldap_mod(ldap.MOD_ADD,ng_search_attr,
			res_l[ng_search_attr],full_dn,list=True)
		elif (not ng_entry_exist and (ch_type == const.group_add)):
		    res_l = res_ldap_ng[0][0][1]
		    mod_ldap(ldap.MOD_DELETE,ng_search_attr,
			(res_l[ng_search_attr]),full_dn,list=True)
		    res_l[ng_search_attr].append(nisnetgroup)
		    mod_ldap(ldap.MOD_ADD,ng_search_attr,
			(res_l[ng_search_attr]),full_dn,list=True)
		else: log_fail.write("\n# Operation not supported")


def get_ldap_value(search_id,dn,retrieveAttributes=None):
    searchScope = ldap.SCOPE_SUBTREE
    try:
	ldap_result_id = l.search(search_id,searchScope,dn,retrieveAttributes)
	result_set = []
	while 1:
	    result_type, result_data = l.result(ldap_result_id, 0)
	    if (result_data == []):
		break
	    else:
		if result_type == ldap.RES_SEARCH_ENTRY:
		    result_set.append(result_data)
		else:
		    pass
	return(result_set)
    except ldap.LDAPError, e:
        log_fail.write('\n# ' + e) #log problem in problem-file
	return(None) 


def iso2utf(s):
  new = ''
  for ch in s:
    c=ord(ch)
    if (c & 0x80) == 0:
      new = new+ch
    else:
      new = new+chr(0xC0 | (0x03 & (c >> 6)))+chr(0x80 | (0x3F & c))
  return new

def modify():
    pass

def start_tls_channel():
    global l
    try:
	l = ldap.open(cereconf.LDAP_SERVER)
	l.protocol_version = ldap.VERSION3
	try:
	    if cereconf.TLS_CACERT_FILE is not None:
		l.OPT_X_TLS_CACERTFILE = cereconf.TLS_CACERT_FILE
	except:  pass
	try:
	    if cereconf.TLS_CACERT_DIR is not None:
		l.OPT_X_TLS_CACERTDIR = cereconf.TLS_CACERT_DIR
	except:  pass
    	# Evaluate more LDAP-properties(tls,version,timeout,servercontrol etc)
	#print "Opening TLS-connection to %s ......" % cereconf.LDAP_SERVER
	l_start = l.start_tls_s()
	l_bind = l.simple_bind_s(cereconf.LDAP_ROOTDN,cereconf.LDAP_PWD)
	if l_bind and l_start:
	    log_diff.write("\n# TLS-channel open to %s" % cereconf.LDAP_SERVER)
	return(l)
    except ldap.LDAPError, e:
	logg_fail.write(e)
	return(None)

def file_exist(filename):
    if os.path.isfile(filename):
	return(1)
    else: return(None)
    
def load_cltype_table(cltype):
    for clt,proc in cl_entry.items():
	# make if-entry to list in cereconf to remove dynamic service
	cltype[int(getattr(co,clt))] = proc	

def end_session(log_fail,log_diff,l):
    l.unbind()
    log_diff.write("\n# Closed TLS-connection to server")
    log_fail.close()
    log_diff.close()


def main():
    # Recieve info from CLhandler or started by job_runner
    # and fetch entry in a tupple. 5 type of changes:
    # add, delete and mod DN and add and delete attributes in DN
    # add and delete 
    clh = CLHandler.CLHandler(db)
    global log_fail, log_diff, ch_log_list
    load_cltype_table(cltype)
    if not os.path.isdir(cereconf.LDAP_DUMP_DIR + '/log'):
	os.makedirs(cereconf.LDAP_DUMP_DIR + '/log', mode = 0770)
    file_path_str = cereconf.LDAP_DUMP_DIR + '/log/'
    if not os.path.isfile(file_path_str + cereconf.LDAP_PID_FILE):
	valid_sync_mode = True
    else: valid_sync_mode = False
    if os.path.isfile(file_path_str + cereconf.LDAP_SYNC_LOG):
	log_diff = file(file_path_str + cereconf.LDAP_SYNC_LOG,'a')
    else:
	log_diff = file(file_path_str + cereconf.LDAP_SYNC_LOG,'w')
    if os.path.isfile(file_path_str + cereconf.LDAP_SYNC_FAULT):
	log_fail = file(file_path_str + cereconf.LDAP_SYNC_FAULT,'a')
    else:
	log_fail = file(file_path_str + cereconf.LDAP_SYNC_FAULT,'w')
    start_tls_channel()
    if valid_sync_mode and log_diff and log_fail:
	i = 0
	ch_log_list = clh.get_events('LDAP',(const.account_mod,\
		const.account_password,const.group_add,const.group_rem,\
		const.group_mod,const.spread_add,const.spread_del,\
		const.quarantine_add,const.quarantine_mod,\
		const.quarantine_del))
	for cll in ch_log_list:
	    try:
		exec cltype[int(cll.change_type_id)]
		clh.confirm_event(cll)
	    except: pass 
	    i += 1
    clh.commit_confirmations()
    end_session(log_fail,log_diff,l)
    


if __name__ == '__main__':
        main()


# Get CLdata. Activate elseif on entry_type (modify-,delete- or add-user, same 
# for filegroups and netgroups
# user_modify: check datebase and ldap -> generate ldif, do ldap_mod (exception 
# password, check if dn exist in ou=people and change passwd.) 
