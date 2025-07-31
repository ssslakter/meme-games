
function formatTime(time) {
  if (time < 0) return "0d 0h 0m 0s";
  let total = Math.floor(time/1000),
      d = Math.floor(total/(24*3600));
  total %= 24*3600;
  let h = Math.floor(total/3600);
  total %= 3600;
  let m = Math.floor(total/60),
      s = total % 60;
  return `${d}d ${h}h ${m}m ${s}s`;
}



function walkTimers(renderType, fn) {
  const now = Date.now();
  for (const el of htmx.findAll(document, `[timer][data-render="${renderType}"]`)) {
    const target   = new Date(el.dataset.target).getTime();
    const diff     = target - now;
    const duration = parseFloat(el.dataset.duration);
    fn(el, diff, duration);

    if (diff <= 0) {
        // TODO remove this
      el.closest('li')?.remove();
    }
  }
}

const renderers = {
  text: (el, diff) => {
    el.textContent = formatTime(diff);
  },

  circle: (el, diff, duration) => {
    const ratio = Math.max(0, diff) / duration;
    const fg    = htmx.find(el, '[ring-fg]');
    const C     = parseFloat(fg.getAttribute('stroke-dasharray'));
    fg.setAttribute('stroke-dashoffset', (C * (1 - ratio)).toFixed(2));

    const label = htmx.find(el, '[timer-text]');
    const secs  = Math.ceil(diff / 1000);
    label.textContent = secs > 0 ? secs + 's' : '0s';
  }
};

function renderTextTimers() {
  walkTimers('text', renderers.text);
}

setInterval(renderTextTimers, 2000);

function animateVisuals() {
  walkTimers('circle', (el, diff, duration) => {
    renderers.circle(el, diff, duration);
  });
  requestAnimationFrame(animateVisuals);
}
requestAnimationFrame(animateVisuals);
