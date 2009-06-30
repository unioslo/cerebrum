from lib.data.DTO import DTO

class ConstantsDTO(DTO):
    def __init__(self, constant=None):
        if constant is not None:
            self.id = constant.int
            self.name = constant.str
            self.description = constant.description

