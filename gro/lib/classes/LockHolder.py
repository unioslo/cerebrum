class LockHolder:
    """
    This class defines the interface required by clients who
    want to use the Locking class to get locks on objects.
    """
    def __init__(self):
        self.lost_locks = []

    def get_database(self):
        raise NotImplementedError('not implemented')

# arch-tag: 7e151021-6fd6-45e9-8204-929c2d73f6f3
