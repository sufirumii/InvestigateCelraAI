// Hand-rolled SVG charting. No chart library: the shapes here are specific
// (Apple-Stocks scrubbing, a signal dial) and cheaper to draw directly.

import { h, svgEl, num, pct, dir } from './util.js';

const RISE = '#0f7d55';
const FALL = '#bf2d47';
const FLAT = '#8b8996';

const smooth = (points, tension = 0.22) => {
  if (points.length < 2) return '';
  let d = `M${points[0][0]},${points[0][1]}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] || points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] || p2;
    const c1x = p1[0] + (p2[0] - p0[0]) * tension;
    const c1y = p1[1] + (p2[1] - p0[1]) * tension;
    const c2x = p2[0] - (p3[0] - p1[0]) * tension;
    const c2y = p2[1] - (p3[1] - p1[1]) * tension;
    d += ` C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} ${p2[0].toFixed(2)},${p2[1].toFixed(2)}`;
  }
  return d;
};

// ---------------------------------------------------------------- sparkline
export function sparkline(values, { width = 64, height = 24, colour } = {}) {
  const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, width, height, 'aria-hidden': 'true' });
  if (!values || values.length < 2) return svg;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => [
    (i / (values.length - 1)) * width,
    height - 2 - ((v - min) / span) * (height - 4),
  ]);
  const stroke = colour || (values.at(-1) >= values[0] ? RISE : FALL);
  svg.append(svgEl('path', { d: smooth(pts), fill: 'none', stroke, 'stroke-width': 1.6,
    'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
  return svg;
}

// ---------------------------------------------------------------- big chart
/**
 * Apple Stocks style chart: gradient area under a smoothed line, a dashed
 * baseline at the opening value, and a scrubber that follows pointer or touch.
 */
export function stockChart(series, { height = 260, onScrub, label = 'Index' } = {}) {
  const W = 1000;
  const H = height;
  const padTop = 18;
  const padBottom = 20;

  const wrap = h('div', { class: 'chart-wrap' });
  if (!series || series.length < 2) {
    wrap.append(h('div', { class: 'empty', text: 'Not enough history to plot yet.' }));
    return wrap;
  }

  const values = series.map(p => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = span * 0.12;
  const lo = min - pad;
  const hi = max + pad;

  const padX = 3;
  const x = i => padX + (i / (series.length - 1)) * (W - padX * 2);
  const y = v => padTop + (1 - (v - lo) / (hi - lo)) * (H - padTop - padBottom);

  const pts = series.map((p, i) => [x(i), y(p.value)]);
  const rising = values.at(-1) >= values[0];
  const stroke = rising ? RISE : FALL;
  const gid = `g${Math.random().toString(36).slice(2, 8)}`;

  const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'none',
    style: `height:${H}px`, role: 'img', 'aria-label': `${label} chart` });

  const defs = svgEl('defs');
  const grad = svgEl('linearGradient', { id: gid, x1: 0, y1: 0, x2: 0, y2: 1 });
  grad.append(svgEl('stop', { offset: '0%', 'stop-color': stroke, 'stop-opacity': 0.20 }));
  grad.append(svgEl('stop', { offset: '100%', 'stop-color': stroke, 'stop-opacity': 0 }));
  defs.append(grad);
  svg.append(defs);

  // opening baseline
  const base = y(values[0]);
  svg.append(svgEl('line', { x1: 0, x2: W, y1: base, y2: base, stroke: '#cfccdd',
    'stroke-width': 1, 'stroke-dasharray': '2 6', 'vector-effect': 'non-scaling-stroke' }));

  const line = smooth(pts);
  svg.append(svgEl('path', { d: `${line} L${W},${H - padBottom} L0,${H - padBottom} Z`, fill: `url(#${gid})` }));

  const path = svgEl('path', { d: line, fill: 'none', stroke, 'stroke-width': 2,
    'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'vector-effect': 'non-scaling-stroke' });
  svg.append(path);

  // event markers — days where something actually happened
  const busiest = [...series].filter(p => p.events > 0).sort((a, b) => b.events - a.events).slice(0, 8);
  busiest.forEach(p => {
    const i = series.indexOf(p);
    svg.append(svgEl('circle', { cx: x(i), cy: y(p.value), r: 3.2,
      fill: '#fff', stroke, 'stroke-width': 1.6, 'vector-effect': 'non-scaling-stroke' }));
  });

  // scrubber
  const cursor = svgEl('line', { y1: padTop - 8, y2: H - padBottom, stroke: '#1e1e26',
    'stroke-width': 1, opacity: 0, 'vector-effect': 'non-scaling-stroke' });
  const knob = svgEl('circle', { r: 4.5, fill: stroke, stroke: '#fff', 'stroke-width': 2, opacity: 0 });
  svg.append(cursor, knob);

  const badge = h('div', { class: 'scrub-badge' });
  wrap.append(svg, badge);

  const rect = () => svg.getBoundingClientRect();
  const move = clientX => {
    const box = rect();
    const raw = ((clientX - box.left) / box.width) * W;
    const ratio = Math.min(1, Math.max(0, (raw - padX) / (W - padX * 2)));
    const i = Math.round(ratio * (series.length - 1));
    const p = series[i];
    cursor.setAttribute('x1', x(i)); cursor.setAttribute('x2', x(i));
    cursor.setAttribute('opacity', 0.35);
    knob.setAttribute('cx', x(i)); knob.setAttribute('cy', y(p.value)); knob.setAttribute('opacity', 1);
    badge.textContent = `${num(p.value, 2)}  ·  ${new Date(p.date).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}`;
    badge.style.left = `${ratio * 100}%`;
    badge.classList.add('show');
    onScrub?.(p, i);
  };
  const end = () => {
    cursor.setAttribute('opacity', 0);
    knob.setAttribute('opacity', 0);
    badge.classList.remove('show');
    onScrub?.(null, -1);
  };

  wrap.addEventListener('pointermove', e => move(e.clientX));
  wrap.addEventListener('pointerdown', e => { wrap.setPointerCapture?.(e.pointerId); move(e.clientX); });
  wrap.addEventListener('pointerleave', end);
  wrap.addEventListener('pointerup', end);

  return wrap;
}

export function rangeSelector(ranges, active, onPick) {
  return h('div', { class: 'range-row' },
    ranges.map(r => h('button', {
      class: r === active ? 'on' : '', type: 'button',
      onclick: () => onPick(r), text: r,
    })));
}

// ---------------------------------------------------------------- dial
export function signalDial(value, band) {
  const r = 38;
  const c = 2 * Math.PI * r;
  const filled = c * Math.min(1, value / 100);
  const svg = svgEl('svg', { viewBox: '0 0 92 92', 'aria-label': `Signal ${value} of 100` });
  svg.append(svgEl('circle', { cx: 46, cy: 46, r, fill: 'none', stroke: '#eeecf6', 'stroke-width': 6 }));
  const arc = svgEl('circle', {
    cx: 46, cy: 46, r, fill: 'none', stroke: 'currentColor', 'stroke-width': 6,
    'stroke-linecap': 'round', 'stroke-dasharray': `${filled} ${c}`,
    transform: 'rotate(-90 46 46)',
  });
  svg.append(arc);
  const wrap = h('div', { class: `dial band-${band}` },
    h('div', { style: 'color:var(--band)' }, svg),
    h('div', {},
      h('div', { class: 'score', text: num(value, 1) }),
      h('div', { class: 'band-name', text: `${band} signal` }),
      h('div', { class: 'caption', text: 'Weighted sum of six bounded components. Breakdown below.' }),
    ));
  return wrap;
}

export function componentBars(components) {
  const rows = Object.entries(components).map(([, c]) =>
    h('div', { class: 'bar-row' },
      h('span', { text: c.label }),
      h('div', { class: 'bar-track' },
        h('div', { class: 'bar-fill', style: `width:${Math.round(c.raw * 100)}%` })),
      h('span', { class: 'v', text: c.contribution.toFixed(1) }),
    ));
  return h('div', { class: 'bars' }, rows);
}

export function deltaText(value) {
  const d = dir(value);
  return h('span', { class: d, text: pct(value) });
}
