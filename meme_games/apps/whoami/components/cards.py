from ...shared import *
from meme_games.apps.user import *
from ..domain import *
from .notes import *
from .basic import *


def PlayerLabelText(r: WhoAmIPlayer | User, owner: WhoAmIPlayer):
    label_text_classes = "text-center border-none w-full h-full shadow-none scrollbar-hide resize text-black"
    style = (
        f"width: {int2px(owner.label_tfm.width)}; height: {int2px(owner.label_tfm.height)};"
        if owner.label_tfm
        else ""
    )
    print(style)
    if r.uid != owner.uid:
        return TextArea(
            owner.label_text,
            placeholder="enter label",
            ws_send=True,
            name="label",
            _="on wsMessage(label) set me.value to label",
            data_label_text=owner.uid,
            hx_vals={"owner_uid": owner.uid, "type": "label_text"},
            style=style,
            value=owner.label_text,
            cls=label_text_classes,
            hx_trigger="input changed delay:100ms",
        )
    else:
        label_hidden_classes = "absolute text-4xl left-0 top-0 flex items-center justify-center bottom-0 right-0 text-gray-500 pointer-events-none"
        return (
            TextArea(readonly=True, style=style, cls=label_text_classes),
            Div(
                "?" if owner.label_text else "",
                cls=label_hidden_classes,
                data_label_text=owner.uid,
            ),
        )


def PlayerLabelFT(r: WhoAmIPlayer | User, owner: WhoAmIPlayer):
    fields = ["x", "y", "width", "height", "owner_uid"]
    event_details = ", ".join(
        [f"{field}: event.detail.transform.{field}" for field in fields]
    )
    if owner.label_tfm:
        style = f"left: {int2px(owner.label_tfm.x)}; top: {int2px(owner.label_tfm.y)};"
    else:
        style = f"left: calc(50%-{LABEL_WIDTH}/2);"
    style += "background-color: rgba(239, 255, 200, 0.6);"
    return Div(
        PlayerLabelText(r, owner),
        Div(
            hx_trigger="moved",
            ws_send=True,
            hx_vals=f'js:{{{event_details}, type: "label_position"}}',
        ),
        style=style,
        data_label=owner.uid,
        cls="absolute z-5 top-0 p-3 cursor-grab shadow-lg border-2 rounded-lg",
        _=f"""
                init call initLabel(me)
                on mousedown call onLabelMouseDown(event)
                on mousemove from document call onDocumentMouseMove(event)
                on mouseup from document call onDocumentMouseUp(event)
                on wsMessage call onLabelWsMessage(event)
               """.strip(),
    )


def PlayerCard(reciever: WhoAmIPlayer | User, p: WhoAmIPlayer, lobby: Lobby):
    if not p.is_player:
        return
    controls_classes = "absolute top-0 right-0 z-10 group-hover:block hidden cursor-pointer p-1 bg-white/60 dark:bg-gray-900/60"
    notes_classes = f"w-[{CARD_WIDTH}] h-[{CARD_HEIGHT}] absolute top-0 left-0 z-50 hidden p-3"


    if reciever == p:
        edit = (
            UkIcon(
                "pencil",
                width=30,
                height=30,
                cls=controls_classes,
                _="on click set x to next <form input/> then x.click()",
            ),
            Form(
                Input(type="file", name="file", accept="image/*"),
                style="display: none;",
                hx_trigger="change",
                hx_post=edit_avatar,
                hx_swap="none",
            ),
        )
    else:
        edit = UkIcon("file-text", width=30, height=30, cls=f"{controls_classes} peer",
                      _=f'on mouseover get first <[data-notes="{p.uid}"]/> then remove .hidden from it'
                      )

    return PlayerCardBase(
        edit,
        AvatarBig(p.user),
        footer=Div(
            MemberName(reciever, p),
            " ✪" if lobby.host == p else None,
        ),
        footer_cls="p-0 backdrop-blur-sm text-xl justify-center flex rounded-lg w-full truncate",
        data_user=p.uid,
        body_cls="flex-1 relative p-0 overflow-hidden w-full rounded-t-lg",
    )(PlayerLabelFT(reciever, p), Notes(reciever, p, 
                                        text_cls='flex-1 box-border',
                                        cls=notes_classes,
                                        _='on mouseleave add .hidden to me') if reciever!=p else None)


def NewPlayerCard():
    from ..routes import play

    icon_classes = "text-center text-[120px] text-gray-400 transition-all duration-300 ease-in-out group-hover:scale-[1.2] group-hover:text-black dark:group-hover:text-white"
    return PlayerCardBase(
        "+",
        body_cls=icon_classes,
        cls="group opacity-50 cursor-pointer",
        id='new-player-card',
        hx_post=play,
        hx_swap="outerHTML",
    )
