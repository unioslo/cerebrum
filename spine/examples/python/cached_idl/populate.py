
import Spine

def mult(a, b):
    r=[]
    for i in a:
        for j in b:
            r.append(i+j)
    return r



name_m = ["ole", "jens", "gunnar", "frode", "jørgen", "kristian",
          "knut", "steinar", "stian", "carl", "thomas", "erik",
          "marius", "lars", "martin", "leiv", "arild", "johan",
          "sverre" ]
name_f  = ["lise", "mari", "gro", "anne", "kristin", "jenny", "hanne",
	"ida", "marit", "maria", "siv", "silje", "tine", "tina",
	"idunn", "hege", "marte", "gry", "vigdis" ]
name_g  = ["myr", "teig", "skog", "fjell", "vass"]
name_s  = ["set", "stad", "sæter", "by", "voll", "eng", "sjø",
        "vatn", "å", "skog", "ås", "vik", "nes"]
name_p  = [ "lille", "stor", "lang", "kort", "brå" ]

name_1 = name_m + name_f
name_2 = mult(name_m, ["sen"]) * 4 + mult(name_m, ["son"]) \
         + mult(name_g, name_s) + mult(name_p, name_g) + mult(name_p, name_s)

import random
def get_name_first(g):
    if g:
	if g=="M":
	    return name_m[random.randrange(len(name_m))].capitalize()
	else:
	    return name_f[random.randrange(len(name_f))].capitalize()
    else:
	return name_1[random.randrange(len(name_1))].capitalize()

def get_name_last():
    return name_2[random.randrange(len(name_2))].capitalize()

t=Spine.connect().login("admin", "password").new_transaction()
comm=t.get_commands()
accountnamevaluedomain=t.get_value_domain("account_names")
sourcesystem=t.get_source_system('Manual') #it's not
lastnametype=t.get_name_type("LAST")
firstnametype=t.get_name_type("FIRST")
fullnametype=t.get_name_type("FULL")

def create_random():
   gd=random.choice(("M","F"))
   p=comm.create_person(comm.get_date_now(), t.get_gender_type(gd))
   fn=get_name_first(gd)
   ln=get_name_last()
   p.add_name("%s %s" % (fn, ln), fullnametype, sourcesystem)
   p.add_name(fn, firstnametype, sourcesystem)
   p.add_name(ln, lastnametype, sourcesystem)
   names=comm.suggest_unames(accountnamevaluedomain, fn, ln)
   a=comm.create_account(names[0], p, comm.get_date(2010, 12, 31))
   # spread?
   g=comm.create_group(names[0])  # noen grupper også
   # gruppeeier?

import time

def create_many(n):
    t=time.time()
    for i in range(n):
	create_random()
    dt=time.time()-t
    print "Created %d persons/users/groups in %f seconds %f/s\n" % (n, dt, n/dt)



if __name__=="__main__":
    create_many(100)
    t.commit()

# arch-tag: c05b814d-9d58-4b63-b467-25f3bb4b4307
