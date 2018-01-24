# -*- coding: utf-8 -*-
from Cerebrum.modules.bofhd import errors

class DNSError(errors.CerebrumError):
    """A DNSError is thrown when an operation is illegal for DNS"""
    pass

class SubnetError(DNSError):
    """Subnet-specific errors."""
    pass
