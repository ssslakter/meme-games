from ...shared import *

w, h = 280, 300
LABEL_WIDTH, LABEL_HEIGHT = int2css(w/2), int2css(h/4)
CARD_WIDTH, CARD_HEIGHT = int2css(w), int2css(h)

def PlayerCardBase(*args, cls=(), **kwargs):
    return Card(*args, 
                cls=f"w-[{CARD_WIDTH}] h-[{CARD_HEIGHT}] group {stringify(cls)} flex justify-center items-center flex-col", 
                **kwargs)
