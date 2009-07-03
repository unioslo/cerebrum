from lib.data.DTO import DTO

class ConstantsDTO(DTO):
    def __init__(self, constant=None):
        if constant is not None:
            self.id = int(constant)
            self.name = str(constant)
            self.description = constant.description

