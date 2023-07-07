=============================
Testoppsett for virthome-db
=============================


Følgende skritt må tas for å gå fra 0 til en fungerende
VirtHome-database. "Fungerende" til testing, om ikke annet.


cereconf-variablene
--------------------
Disse variablene blir nevnt, på en eller annen måte, i virthomekoden:

* BOFHD_SUPERUSER_GROUP, navnet på gruppen med superbrukere
* BOFHD_SUDOERS_GROUP, navnet på gruppen med de som kan su-e til andre brukere
  (typisk bare webapp)
* 




Testprosedyren
----------------
Så, i rekkefølge:

  #. Lage en tom database. For produksjonsmiljøet blir dette annerledes, men
     for testformål er det enkleste å koble seg inn mot default-databasen til
     brukeren cerebrum og lage en database til virthome, la oss kalle den
     "cerebrum_virthome":: 

       $ hostname
       cere-utv01.uio.no
       $ psql -h dbpg-cere-utv.uio.no -U cerebrum  
       Password for user cerebrum: 
       <...>
       cerebrum=> create database cerebrum_virthome with encoding 'unicode' ;
       CREATE DATABASE
  
  #. Lage en passordfil til denne db-en::

        $ whoami
        cerebrum
        $ cp /cerebrum/etc/passwords/passwd-cerebrum\@cerebrum_nmh_ivr\@dbpg-cereutv.uio.no \
             '/cerebrum/etc/passwords/passwd-cerebrum@cerebrum_virthome@dbpg-cereutv.uio.no'

  #. Sette opp de nødvendige konstant-variablene. VirtHome hanskes primært med
     konti og grupper, og derfor må vi sette minst disse cereconf-variablene::

       # Provide defaults for all settings.
       from Cerebrum.default_config import *
       
       # database
       CEREBRUM_DATABASE_NAME="cerebrum_virthome"
       CLASS_DBDRIVER = ['Cerebrum.database.postgres/PsycoPG2']
       CEREBRUM_DATABASE_CONNECT_DATA["host"] = "dbpg-cereutv.uio.no"
       CEREBRUM_DATABASE_CONNECT_DATA["user"] = "cerebrum"
       DB_AUTH_DIR="/cerebrum/etc/passwords"
       CEREBRUM_DDL_DIR="/hom/ivr/work/cerebrum-virthome/design"
       
       # logging
       LOGGING_CONFIGFILE="/hom/ivr/work/cerebrum-virthome/design/logging.ini"
       AUTOADMIN_LOG_DIR="/hom/ivr/work/cerebrum-virthome/logs/"
       
       #
       # Names for Virt/FED accounts' human owners.
       ENTITY_TYPE_NAMESPACE["virthome_untrusted"] = "v_untrust_names"
       ENTITY_TYPE_NAMESPACE["virthome"] = "v_names"
       
       # core classes setup
       CLASS_CONSTANTS = (# this one ought to be obvious...
                   'Cerebrum.modules.virthome.Constants/VirtHomeMiscConstants',
                   # vh bofhd specific constants
                   'Cerebrum.modules.virthome.bofhd_auth/BofhdVirtHomeAuthConstants',          
                   # changelog events
                   'Cerebrum.modules.CLConstants/CLConstants',
                   # bofhd events (auth-constants)
                   'Cerebrum.modules.bofhd.utils/Constants',
                   # we use traits to confirm certain actions (account create)
                   'Cerebrum.modules.EntityTrait/TraitConstants',)
       
       # This capture the common traits of Virt/FED accounts. When a distinction is
       # important, grab the proper class manually. Since we have to types of
       # accounts in virthome, CLASS_ACCOUNT on its own is a bit useless.
       CLASS_ACCOUNT = ('Cerebrum.modules.virthome.VirtAccount/BaseVirtHomeAccount',)
       CLASS_GROUP = ('Cerebrum.modules.virthome.VirtGroup/VirtGroup',)
       CLASS_CHANGELOG = ('Cerebrum.modules.virthome.ChangeLogVH/ChangeLogVH',)

       # misc cerebrum tidbits -- which ones do we need?
       SYSTEM_LOOKUP_ORDER=("system_virthome",)

       # Some of the jobs need to send e-mails
       SMTP_HOST = "smtp.uio.no"

       # BOFH-magic
       BOFHD_MOTD_FILE = None
       BOFHD_SUDOERS_GROUP = "sudoers"
       BOFHD_NEW_GROUP_SPREADS = ("group@ldap",)
       BOFHD_NEW_USER_SPREADS = ("account@ldap",)

       # Realm for virtaccounts
       VIRTHOME_REALM = "VH"

       # Quarantines
       QUARANTINE_RULES = {'nologin': {'lock': 1, },
                           'autopassword': {'lock': 1},
			   'pending': {'lock': 1},
			   'disabled': {'lock': 1},
                          }

       # 
       # LDAP-related configuration
       LDAP = {
           'dump_dir': './',
	   'container_attrs': {'objectClass': ('top', 'uioUntypedObject')},
       }

       LDAP_ORG = {
           'dn': 'cn=virthome,dc=usit,dc=uio,dc=no',
       }

       LDAP_USER = {
           'dn': 'cn=users,' + LDAP_ORG['dn'],
           'spreads': ('account@ldap',),
           'objectClass': ('top', 'person', 'organizationalPerson', 
	                   'inetOrgPerson', 'uioPersonObject',),
       }
      
       LDAP_GROUP = {
           'dn': 'cn=groups,' + LDAP_ORG['dn'],
           'spreads': ('group@ldap',),
           'objectClass': ('top', 'groupOfNames',),
       }


  #. Sørg for at denne cereconf-en er på rett sted (PYTHONPATH må peke et sted
     der det finnes en cereconf.py som inneholder punktet over)::

       $ python -c 'import cereconf; print cereconf.CEREBRUM_DATABASE_NAME'

  #. Så kan vi populere databasen med tomme tabeller. Det enkleste er å
     begynne fra scratch og bruke cere-utv01 / dbpg-cereutv.uio.no til
     formålet::

       $ python makedb.py --extra-file design/mod_changelog.sql \
                          --extra-file design/mod_entity_trait.sql \
                          --extra-file design/mod_virthome.sql \
                          --extra-file design/bofhd_tables.sql \
                          --extra-file design/bofhd_auth.sql \
                          --extra-file design/mod_password_history.sql \
                          --extra-file design/mod_job_runner.sql 

  #. Sette passord på boostrap_account, slik at vi har en bruker med
     rettigheter til å tildele andre rettigheter gjennom bofhd. Dette gjøres
     gjennom API-et::

        import cereconf
        from Cerebrum.Utils import Factory
        db = Factory.get("Database")()
        db.cl_init(change_program='manual hack')
        acc = Factory.get("Account")(db)
        acc.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        acc.set_password("let-me-in")
        acc.write_db()
        db.commit()

  #. Lage webapp-brukeren, de nødvendige opsets og tildele opsets::

        $ python contrib/virthome/assign_permissions.py -w webapp 

     Hvis alt ser fint ut, kjør skriptet med commit::

        $ python contrib/virthome/assign_permissions.py -w webapp -c

     deretter må passordet settes for webapp-brukeren::

        import cereconf
        from Cerebrum.Utils import Factory
        db = Factory.get("Database")()
        db.cl_init(change_program='manual hack')
        acc = Factory.get("Account")(db)
        acc.find_by_name('webapp')
        acc.set_password("let-me-in")
        acc.write_db()
        db.commit()

  #. Under en ekte installasjon bør passordene for bootstrap og webapp legges
     under ``cereconf.DB_AUTH_DIR`` -- det kan være nyttig ved senere
     anledninger. 

  #. Lage konfigurasjonsfilen til bofhd: Trenger egentlig kun virthome sine
     kommandoer (den bofhd-en arver alle de andre)::

        $ cat design/config.dat

        Cerebrum.modules.virthome.bofhd_virthome_cmds/BofhdVirthomeCommands
        Cerebrum.modules.virthome.bofhd_virthome_cmds/BofhdVirthomeMiscCommands

  #. Starte bofhd::

        $ python servers/bofhd/bofhd.py -c design/config.dat \
                 --logger-name console --port 8958

     Hva porten er er nokså uvesentlig, men det må være en port som det er
     mulig å koble til fra w3utv-ws01 som webappen er på (8957/8958 skal være
     åpne (jfr
     <URL:msgid:Pine.LNX.4.64-L.0910061119220.20367@fruktkurv.uio.no>).

  #. 

