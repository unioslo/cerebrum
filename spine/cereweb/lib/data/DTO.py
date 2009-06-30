class DTO(object):
    def __repr__(self):
        return str(self.__dict__)

    def __eq__(self, other):
        if other is None: return False
        return self.__dict__ == other.__dict__
