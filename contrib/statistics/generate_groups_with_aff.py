from Cerebrum.Utils import Factory
import Cerebrum.utils.csvutils as csvutils
import argparse
import Cerebrum.logutils




def cachedata(db):
    ac = Factory.get("Account")(db)
    co = Factory.get("Constants")(db)
    ou = Factory.get("OU")(db)

    cache = dict()
    cache['accounts'] = list(account['owner_id'] for account in ac.list())
    cache['status'] = dict((int(r), str(r)) for r in co.fetch_constants(co.PersonAffStatus))
    cache['ou'] = dict(
    (sko["ou_id"],"{:02d}{:02d}{:02d}".format(sko["fakultet"], sko["institutt"], sko["avdeling"]),)
        for sko in ou.get_stedkoder())
    return cache

def get_affiliations():
    db = Factory.get("Database")()
    pe = Factory.get("Person")(db)
    affs = list()
    cache = cachedata(db)
    
    for row in pe.list_affiliations():
        if row['person_id'] in cache['accounts']:
            ou = cache['ou'][row["ou_id"]]
            status = cache['status'][row["status"]]
            affs.append((ou, status))
    return affs


def create_csv(filename, affiliations):
    output = ({'OU': unique[0], 'aff-status': unique[1], 'antall-personer': affiliations.count(unique)} for unique in sorted(set(affiliations)))
    # asdf = dict()
    # for unique in affsunique:
    #     asdf.update({'ou': unique[0], 'status': unique[1], 'count': affiliations.count(unique)})
    header = ["OU", "aff-status", "antall-personer"]
    writer = csvutils.UnicodeDictWriter(filename, fieldnames=header)
    writer.writeheader()
    writer.writerows(output)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        type=argparse.FileType(mode="w"),
        help="CSV file where output is written.",
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf("tee", args)
    affiliations = get_affiliations()
    create_csv(args.output, affiliations)    
    

if __name__ == "__main__":
    main()
