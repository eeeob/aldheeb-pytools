class UtilError(Exception):
    pass

class ValidationError(UtilError, ValueError):
    pass



__all__ = (
    "UtilError", 
    "ValidationError", 

)