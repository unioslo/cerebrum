from popen2 import Popen3
import unittest

def stedkode_string_to_tuple(stedkode):
    """
    Converts a stedkode string to a tuple representing
    (landkode, institusjon, fakultet, institutt, avdeling).
    """
    assert len(stedkode) == 9
    landkode = 0
    institusjon = int(stedkode[:3])
    fakultet = int(stedkode[3:5])
    institutt = int(stedkode[5:7])
    avdeling = int(stedkode[7:])
    return (landkode, institusjon, fakultet, institutt, avdeling)

def find_ou_by_stedkode(stedkode, transaction):
    """
    Searches for the OU with the given stedkode string in Spine, and returns
    the found OU.
    """
    landkode, institusjon, fakultet, institutt, avdeling = stedkode_string_to_tuple(stedkode)
    ou_searcher = transaction.get_ou_searcher()
    ou_searcher.set_landkode(landkode)
    ou_searcher.set_institusjon(institusjon)
    ou_searcher.set_fakultet(fakultet)
    ou_searcher.set_institutt(institutt)
    ou_searcher.set_avdeling(avdeling)
    return ou_searcher.search()

if __name__ == '__main__':
    unittest.main()
