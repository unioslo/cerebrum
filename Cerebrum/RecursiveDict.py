"""A variant of dict supporting recursive updates"""

class RecursiveDict(dict):
    """A variant of dict supporting recursive updates"""
    def update(self, other):
        """D.update(E) -> None. Update D from E recursive.
           Any dicts that exists in both D and E are updated recursive
           instead of being replaced.
           Note that items that are UserDicts are not updated recursive.
           """
        for (key, value) in other.items():
            if (key in self and 
                isinstance(self[key], Profile) and 
                isinstance(value, dict)):
                self[key].update(value)
            else:
                self[key] = value    
    def __setitem__(self, key, value):
            if isinstance(value, dict):
                # Wrap it, make sure it follows our rules
                value = Profile(value)
            dict.__setitem__(self, key, value)    
                      
                
