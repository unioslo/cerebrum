
import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.modules.no.fodselsnr import personnr_ok, InvalidFnrError
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.no.uit.bofhd_uit_cmds import BofhdExtension

class BofhdUiTExtension(BofhdExtension):


    def _uit_list_legacy_user(self,personid):
        self.logger.debug("Var personid:"+personid)
        db_row = self.db.query( """
        SELECT user_name,ssn,source,type,name,comment
        FROM [:table schema=cerebrum name=legacy_users]
        WHERE
        user_name=:uname OR
        ssn=:ssn""",{'uname': personid, 'ssn':personid})
        ret = []
        for element in db_row:
            ret.append({'user_name': element[0], 'ssn':element[1],
                        'source': element[2],'type':element[3],
                        'name': element[4], 'comment': element[5]})
        return ret

    
    #
    # Uito special table for reserved usernames. Usernames that is reserved due
    # to being used in legacy systems
    #
    all_commands = {}
    all_commands['misc_list_legacy_user'] = Command(
        ("misc", "legacy_user"), PersonId(),
        fs=FormatSuggestion("%-6s %11s %6s %4s ", ('user_name', 'ssn', 'source', 'type'),
                            hdr="%-6s %-11s %6s %4s" % ('UserID', 'Personnr', 'Source', 'Type')))
    def misc_list_legacy_user(self,operator,personid):
        return self._uit_list_legacy_user(personid)
                                             
    all_commands['misc_uit_check_ad_password'] = Command(
        ("misc", "ad_auth"), AccountName(),AccountPassword())
    def misc_uit_check_ad_password(self,operator,username,password):
        return "Checking password in domain AD for '%s' with password '%s'" % (username, password)

    
    all_commands['misc_get_primary_account'] = Command(
        ("misc", "get_account"), PersonId(),
        fs=FormatSuggestion("%s",('user_name'), hdr="%s" % ('Person NR')))        
    def misc_get_primary_account(self,operator,ssn):
        pass


    def uit_legacy_user_func(self, session, *args):
        return self._uit_legacy_user_func_helper(session, *args)


    def _uit_legacy_user_func_helper(self, session, *args):
        """A prompt_func on the command level should return
        {'prompt': message_string, 'map': dict_mapping}
        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list."""
        all_args = list(args[:])
        print "ALL: %s" % all_args
        person = Utils.Factory.get('Person')(self.db)
        if not all_args:
            return {'prompt': "Personnummer",
                    'help_ref': "user_create_person_id"
                    }    
        ssn = all_args.pop(0)
        # do a sanity check on ssn
        try:
            new_ssn = personnr_ok(ssn)
        except InvalidFnrError,m:
            raise CerebrumError, "Invalid SSN! %s" % m

        person_ok = False
        yes_no = 'n'
        try:
            # first try to find person in BAS
            person.clear()
            person.find_by_external_id(
                self.const.externalid_fodselsnr, ssn)
            person_ok = True
        except Errors.NotFoundError:
            # Person not found in BAS. Check legacy.
            legacy = self._uit_list_legacy_user(ssn)
            if len(legacy) == 1:
                person_ok = True
                return {'last_arg': True}
            
            elif len(legacy) >1:
                raise CerebrumError, "SSN '%s' has more than one entry in legacy. Contact BAS admin to fix" % ssn
            else:
                # person does not exist in legacy either.
                # Ask for more info and reserve...
                pass

        if not person_ok:
            if not all_args:
                return {'prompt': "Person first name",
                        'help_ref': "kano_1"
                        }
            first_name = all_args.pop(0)
            
            if not all_args:
                return {'prompt': "Person last name",
                        'help_ref': "kano_2"
                        }
            last_name = all_args.pop(0)
            info = "Reserve AD user for %s %s (ssn=%s)? (y/n)\n" % (first_name, last_name,ssn)
            if not all_args:
                return {'prompt': "%sContinue? (y/n)" % info}
            yes_no = all_args.pop(0)
            if not yes_no == 'y':
                raise CerebrumError, "Command aborted at user request"

            return {'last_arg': True}
        
        elif (person_ok):
            ac = person.get_primary_account()
            if (ac):
                account =  Utils.Factory.get('Account')(self.db)
                account.clear()
                account.find(ac)
                return {'last_arg': True}         
        raise CerebrumError, "prompt_func called with too many arguments"


    all_commands['misc_find_potenial_username'] = Command(
        ('misc', 'ad'), prompt_func=uit_legacy_user_func,
        fs=FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')
    def misc_find_potenial_username(self,operator,*args):
        all_args = list(args)
        NoAccounts = False
        if len(all_args) >= 1 and (len(all_args)<=4): 
            ssn = all_args.pop(0)
            try:
                # search BAS
                accounts = self.person_accounts(operator,ssn)
            except Exception,m:
                # not found in BAS, must then be in legacy!
                legacy = self._uit_list_legacy_user(ssn)
                if len(legacy) < 1:
                    NoAccounts=True
                elif len(legacy)==1:
                    legacy = legacy[0]
                    return "SSN='%s' has info only in legacy. Name=%s, username=%s" % (ssn, legacy['name'],legacy['user_name'])
                elif len(legacy) >1:
                    acclist = []
                    for x in legacy:
                        acclist.append(x['user_name'])
                    accts = ",".join(acclist)                
                    raise CerebrumError, "SSN '%s' has more than username in legacy: %s.  Contact BAS admin to fix" % (ssn,accts)
                else:
                    raise CerebrumError, "Programming error. ssn should be found"
            else:
                if (len(accounts)==1):
                    return "Account for %s is %s" % (ssn,accounts[0]['name'])
                else:
                    acclist = []
                    for x in accounts:
                        acclist.append(x['name'])
                    accts = ",".join(acclist)                
                    return "got %s accounts for person: %s " % (len(accounts), accts)

            if NoAccounts and (len(all_args) == 3):
                first_name, last_name, answer = all_args
                name = "%s %s" % (first_name,last_name)
                account =  Utils.Factory.get('Account')(self.db)
                new_username = account.get_uit_uname(ssn,name,Regime='ONE')
                query ="""
                INSERT INTO [:table schema=cerebrum name=legacy_users]  
                (user_name, ssn, name, source, type, comment) 
                VALUES (:user_name, :ssn, :name, :source, :type, :comment)"""
                params = {'user_name': new_username,
                          'ssn': ssn,
                          'source':'AD',
                          'type': 'P',
                          'name':name,
                          'comment': 'Reserved AD username via bofh'
                          }
                try:
                    self.db.execute(query, params)
                    self.db.commit()
                except Exception,m:
                    raise CerebrumError, m
                else:
                    return "Reserved username for %s %s (ssn=%s): username=%s" % (first_name, last_name,ssn,new_username)  
        else:
            raise CerebrumError, "ProgrammingError: invalid args length from prompt_func: %d" % len(all_args)            



    all_commands['misc_find_potenial_username'] = Command(
        ('misc', 'view_changelog'), prompt_func=uit_legacy_user_func,
        fs=FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')


    # user history
    all_commands['user_history'] = Command(
        ("user", "history"), AccountName()) 
    def user_history(self, operator, accountname):
        account = self._get_account(accountname)
        self._check_group_membership(operator.get_entity_id(),cereconf.ORAKEL_GROUP)
        ret = []
        for r in self.db.get_log_events(0, subject_entity=account.entity_id):
            ret.append(self._format_changelog_entry(r))
        return "\n".join(ret)


    def _check_group_membership(self,entity_id,gname):
        if self.ba.is_group_member(entity_id,gname):
            return True        
        else:
            raise  PermissionDenied("Access denied")
        

# arch-tag: 85db404e-b4f2-11da-8c86-8173ccfa4bd5
