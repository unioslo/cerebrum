class DTO(object):
    __slots__ = []

    def _get_dict(self):
        data = {}
        for attr in self.__slots__:
            data[attr] = getattr(self, attr, None)
        return data

    def __repr__(self):
        return repr(self._get_dict())

    def __eq__(self, other):
        if other is None: return False
        return self._get_dict() == other._get_dict()
