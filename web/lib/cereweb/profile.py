from Cerebrum.Utils import RecursiveDict
import default_profile

def get_profile(req):
    profile = RecursiveDict(default_profile.profile)
    return profile
