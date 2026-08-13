from meme_games.core import *


TOASTS_KEY = 'toasts'
TOASTS_ID = 'mg-toast-container'


def AppToast(message: str, kind: str = 'info', dismiss: bool = False, duration: int = 3000):
    icon = {'info': 'info', 'success': 'circle-check', 'warning': 'triangle-alert', 'error': 'circle-x'}[kind]
    return Div(
        UkIcon(icon, width=22, height=22),
        Span(message, cls='flex-1'),
        Button(UkIcon('x', width=18, height=18), cls=(ButtonT.ghost, 'mg-toast-dismiss'),
               type='button', aria_label='Dismiss', onclick='this.closest(".mg-toast").remove()') if dismiss else None,
        cls=f'mg-toast mg-toast-{kind}', data_ui='toast', data_kind=kind,
        _=f'init wait {duration}ms then transition opacity to 0 over 180ms then remove me')


def render_toasts(sess):
    duration = sess.get('toast_duration', 3000)
    toasts = [AppToast(message, kind, dismiss, duration)
              for message, kind, dismiss in sess.pop(TOASTS_KEY, [])]
    return Div(*toasts, id=TOASTS_ID, hx_swap_oob=f'beforeend:#{TOASTS_ID}')


def toast_after(resp, req, sess):
    if TOASTS_KEY in sess and (not resp or isinstance(resp, (tuple, FT, FtResponse))):
        sess['toast_duration'] = req.app.state.toast_duration
        req.injects.append(render_toasts(sess))


def setup_app_toasts(app, duration=3000):
    app.state.toast_duration = duration
    app.hdrs += [Style('''
      .mg-toast-container {
        position: fixed; top: 5.5rem; left: 50%; z-index: 1090;
        display: flex; width: min(32rem, calc(100vw - 2rem)); transform: translateX(-50%);
        flex-direction: column; gap: .75rem; pointer-events: none;
      }
      .mg-toast {
        display: flex; align-items: center; gap: .75rem; width: 100%; padding: .9rem 1rem;
        border: 1px solid hsl(var(--border)); border-left-width: 4px; border-radius: var(--radius);
        background: hsl(var(--card)); color: hsl(var(--card-foreground));
        box-shadow: 0 10px 30px rgb(0 0 0 / .18); pointer-events: auto;
      }
      .mg-toast-info { border-left-color: #38bdf8; }
      .mg-toast-success { border-left-color: #22c55e; }
      .mg-toast-warning { border-left-color: #f59e0b; }
      .mg-toast-error { border-left-color: #ef4444; }
      .mg-toast-dismiss { min-width: auto; padding: .2rem; }
    '''), Script(f'''htmx.onLoad(() => {{
      if (!document.getElementById('{TOASTS_ID}')) {{
        const container = document.createElement('div');
        container.id = '{TOASTS_ID}';
        container.className = 'mg-toast-container';
        container.dataset.ui = 'toast-container';
        document.body.appendChild(container);
      }}
    }});''')]
    app.after.append(toast_after)
