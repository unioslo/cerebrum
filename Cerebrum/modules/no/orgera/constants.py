from Cerebrum.Constants import ConstantsBase, _GroupTypeCode


class OrgEraConstants(ConstantsBase):

    group_type_orgera_assignment = _GroupTypeCode(
        'orgera-assignment-group',
        'Automatic group - periodically generated from ORG-ERA assignments',
    )
