from flask.ext.restful import Resource, abort, reqparse, marshal_with
from api import db, auth, fields

from Cerebrum.Utils import Factory
from Cerebrum import Errors


class Account(Resource):
    def __init__(self):
        super(Account, self).__init__()
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('name', type=str)
        self.reqparse.add_argument('entity_id', type=int)
        self.args = self.reqparse.parse_args()
        self.ac = Factory.get('Account')(db.connection)

    @auth.require()
    @marshal_with(fields.account_fields)
    def get(self):
        if self.args.name:
            lookup = self.ac.find_by_name
            identifier = self.args.name
        elif self.args.entity_id:
            lookup = self.ac.find
            identifier = self.args.entity_id
        else:
            abort(404, message=u"Missing identifier")

        try:
            lookup(identifier)
        except Errors.NotFoundError:
            abort(404, message=u"No such account {}".format(identifier))

        return self.ac
