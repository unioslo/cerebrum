
import config
import SpineClient

class Sync:
    def __init__(self, incr=False, id=-1, auth_type="MD5-crypt"):
        self.incr=incr
        connection = SpineClient.SpineClient(config=config.conf).connect()
        session = connection.login(config.conf.get('spine', 'login'),
                                   config.conf.get('spine', 'password'))
        self.tr = session.new_transaction()
        self.cmd = self.tr.get_commands()
        self.view = self.tr.get_view()
        account_spread=config.conf.get('sync', 'account_spread')
        group_spread=config.conf.get('sync', 'group_spread')
        
        self.view.set_account_spread(self.tr.get_spread(account_spread))
        self.view.set_group_spread(self.tr.get_spread(group_spread))
        self.view.set_authentication_method(self.tr.get_authentication_type(auth_type))
        self.view.set_changelog(id)


    def _do_get(self, objtype, incr):
        if incr is None:
            incr=self.incr
        if incr:
            m = "get_%ss_cl" % objtype
        else:
            m = "get_%ss" % objtype
        for obj in getattr(self.view, m)():
            obj.type=objtype
            config.apply_override(obj, objtype)
            config.apply_default(obj, obj.type)
            #config.apply_quarantine(obj, obj.type)
            yield obj
    
    def get_accounts(self, incr=None):
        return self._do_get("account", incr)
        
    def get_groups(self, incr=None):
        return self._do_get("group", incr)

    def get_persons(self, incr=None):
        return self._do_get("person", incr)        

    def get_ous(self, incr=None):
        return self._do_get("ou", incr)
