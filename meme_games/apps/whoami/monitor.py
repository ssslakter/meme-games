from meme_games.core import *
from meme_games.domain import GAME_REGISTRY, Lobby, LobbyService
from ..shared import *

lobby_service = DI.get(LobbyService)


def elapsed_text(started_at: dt.datetime) -> str:
    seconds = max(0, int((dt.datetime.now() - started_at).total_seconds()))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours}h {minutes:02d}m {seconds:02d}s' if hours else f'{minutes}m {seconds:02d}s'


def LobbyInfo(lobby: Lobby) -> FT:
    return Article(
        Div(
            H3(lobby.id, cls='mg-monitor-lobby-title'),
            Span(f'{len(lobby.members)} members', cls='mg-monitor-members'),
            cls='flex items-center justify-between gap-3'),
        Div(
            Span('Game', cls='mg-monitor-label'),
            Span(GAME_REGISTRY[lobby.current_game].name.title(), cls='mg-monitor-game'),
            cls='mg-monitor-detail'),
        Div(
            Span('Playing for', cls='mg-monitor-label'),
            Span(elapsed_text(lobby.game_started_at), data_elapsed=lobby.game_started_at.isoformat(),
                 cls='mg-monitor-duration'),
            cls='mg-monitor-detail'),
        A('Open lobby', href=game_url(lobby.current_game, lobby.id) or '/', hx_boost='false',
          cls=(ButtonT.primary, 'uk-btn')),
        cls='mg-monitor-lobby', data_ui='monitor-lobby')


@settings_rt
def monitor() -> FT:
    lobbies = sorted(lobby_service.lobbies.values(), key=lambda lobby: lobby.game_started_at, reverse=True)
    return LobbyPage(
        Main(
            H1('Lobby monitor', cls='mg-monitor-title'),
            P('All active lobbies and the games currently in progress.', cls='mg-monitor-description'),
            Div(*[LobbyInfo(lobby) for lobby in lobbies], cls='mg-monitor-list') if lobbies
            else P('No active lobbies.', cls='mg-monitor-empty'),
            _='init renderElapsedTimers()',
            cls='mg-monitor'),
        no_image=True,
        page='monitor')
