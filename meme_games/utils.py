from fasthtml.common import *

ext2ft = {
        'js': lambda fname: Script(src=f'/{fname}'),
        '_hs': lambda fname: Script(src=f'/{fname}', type='text/hyperscript'),
        'css': lambda fname: Link(rel="stylesheet", href=f'/{fname}'),
    }

def Statics(ext: str ='css', static_path: str|Path = 'static', wc: str = None):
    '''Returns a list of static files from a directory'''
    static_path = Path(static_path)
    wc = wc or f"*.{ext}"
    return [ext2ft[ext](f.relative_to(static_path.parent).as_posix()) 
            for f in static_path.rglob(wc)]