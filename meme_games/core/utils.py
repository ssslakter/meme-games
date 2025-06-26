from starlette.routing import compile_path
from .imports import *

__all__ = ['random_id', 'dict_inverse']


def random_id(size=5): return ''.join(random.choices(string.ascii_lowercase+string.digits, k=size))

def dict_inverse(d: dict): 
    """Inverts the keys and values of a dictionary."""
    return {v: k for k, v in d.items()}