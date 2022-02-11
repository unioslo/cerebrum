from copy import deepcopy

from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.orgreg.constants import OrgregConstants
from Cerebrum.modules.no.Stedkode import OuCache
from Cerebrum.Utils import Factory
db = Factory.get("Database")()

pe = Factory.get("Person")(db)
ou = Factory.get("OU")(db)
ou_cache = OuCache(db)

personer = pe.query("""SELECT person_id FROM [:table schema=cerebrum name=person_info]""")

amountDict = {}
#testIndex = 0

for person in personer:
    #testIndex = testIndex + 1
    #if(testIndex > 11000):
    #    break
    pe.find(person[0])
    affiliations = pe.get_affiliations()
    for affiliation in affiliations:
        if(amountDict.get(affiliation[1]) == None):
            amountDict[affiliation[1]] = 1
        else:
            amountDict[affiliation[1]] = amountDict[affiliation[1]]+1
    pe.clear()
run = 1
while(run > 0):
    run = 0
    copyDict = deepcopy(amountDict)
    for place in copyDict:
        ou.find(place)
	try:
	    parent = ou.get_parent(OrgregConstants.perspective_orgreg)
        except NotFoundError:
            parent = None
        if(parent != None and parent != 677):
            run = 1
            if(amountDict.get(parent) == None):
                amountDict[parent] = amountDict.pop(place)
            else:
                amountDict[parent] = amountDict[parent]+amountDict.pop(place)
        ou.clear()

for place in amountDict:
    print(ou_cache.get_name(place))
    print(amountDict[place])

print(amountDict)
