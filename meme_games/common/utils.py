from starlette.routing import compile_path
from .imports import *


def random_id(size=5): return ''.join(random.choices(string.ascii_lowercase+string.digits, k=size))


def matches_template(path, template):
    path_regex, _, _ = compile_path(template)
    return path_regex.match(path) is not None
