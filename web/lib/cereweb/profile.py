from Cerebrum.Utils import RecursiveDict
import default_profile

def get_profile(req):
    profile = RecursiveDict(default_profile.profile)
    return profile

def get_last_error_message(req):
    try:
        msg = req.session['profile']['various']['last_error_message']
        req.session['profile']['various']['last_error_message'] = ''
    except:
        return None

    return msg
