from Cerebrum.Utils import RecursiveDict
import default_profile

def get_profile(req):
    profile = RecursiveDict(default_profile.profile)
    return profile

# arch-tag: 72620efc-1668-4701-9820-180b48326902
