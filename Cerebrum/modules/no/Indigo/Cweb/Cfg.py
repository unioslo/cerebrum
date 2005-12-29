# TBD: Where should we put these variables.  Is cereconf sufficient,
# or do we need more dynamic behaviour?
import cerebrum_path
import cereconf

__root_dir = cereconf.CWEB_LOG_DIR
template_dir = cereconf.CWEB_TPL_DIR+'/templates'
state_file = __root_dir+'/state.db'
log_file = __root_dir+'/www.log'
bofh_server_url = 'http://127.0.0.1:8008'

# arch-tag: cd6a5124-7155-11da-92f6-35a466ba9df2
