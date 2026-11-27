/* Shared presentation helpers: escaping, dates, badges, toasts, modals. */

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

export function icon(name, className = '') {
  return `<svg class="icon ${className}" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
}

export function initials(name) {
  return String(name || '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();
}

export function hueFor(value) {
  let hash = 0;
  for (const char of String(value || 'user')) hash = (hash * 31 + char.charCodeAt(0)) % 360;
  const palette = [152, 168, 188, 24, 204, 96, 272, 44];
  return palette[hash % palette.length];
}

export function avatar(userOrName, size = '') {
  const name = typeof userOrName === 'string' ? userOrName : userOrName?.full_name;
  const hue = hueFor(typeof userOrName === 'string' ? userOrName : userOrName?.email || name);
  return `<span class="avatar ${size}" style="--avatar-hue:${hue}" aria-hidden="true">${escapeHtml(initials(name))}</span>`;
}

export function formatDate(value, options = {}) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const { year, ...rest } = options;
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: year === false ? undefined : (year || 'numeric'),
    ...rest,
  }).format(date);
}

export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function timeAgo(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const seconds = Math.max(1, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.round(days / 7)}w ago`;
  return formatDate(value, { year: false });
}

export function dueLabel(report) {
  if (report.status === 'resolved' || report.status === 'closed') return 'Closed';
  if (!report.sla_due_at) return '';
  const due = new Date(report.sla_due_at);
  const diff = due.getTime() - Date.now();
  if (diff <= 0) return 'SLA breached';
  const hours = Math.round(diff / 36e5);
  if (hours < 1) return 'Due soon';
  if (hours < 24) return `Due in ${hours}h`;
  return `Due in ${Math.round(hours / 24)}d`;
}

export function statusBadge(status) {
  const label = String(status || '').replaceAll('_', ' ');
  return `<span class="badge status-${escapeHtml(status)}">${escapeHtml(label)}</span>`;
}

export function priorityLabel(priority) {
  return `<span class="priority priority-${escapeHtml(priority)}">${escapeHtml(priority)}</span>`;
}

export function conditionBadge(condition) {
  const cls = String(condition || '').split(' ')[0];
  return `<span class="condition condition-${escapeHtml(cls)}">${escapeHtml(condition)}</span>`;
}

export function stars(rating, className = '') {
  if (!rating) return '';
  const full = Math.round(Number(rating));
  return `<span class="stars ${className}" title="${rating} out of 5">${Array.from({ length: 5 }, (_, i) =>
    `<svg class="icon star ${i < full ? 'filled' : ''}" style="width:12px;height:12px;fill:${i < full ? 'currentColor' : 'none'};color:${i < full ? 'var(--accent)' : '#ccd4cf'};stroke:${i < full ? 'var(--accent)' : '#ccd4cf'}"><use href="#i-star"></use></svg>`
  ).join('')}</span>`;
}

export function pageHead({ kicker, title, subtitle, actions = '', kickerIcon = 'sparkles' }) {
  return `
    <div class="page-head">
      <div>
        <span class="page-kicker">${icon(kickerIcon)}${escapeHtml(kicker)}</span>
        <h1 class="page-title">${title}</h1>
        ${subtitle ? `<p class="page-subtitle">${subtitle}</p>` : ''}
      </div>
      ${actions ? `<div class="page-actions">${actions}</div>` : ''}
    </div>`;
}

export function emptyState({ title, text, action = '', iconName = 'clipboard' }) {
  return `
    <div class="empty-state">
      <div class="empty-icon">${icon(iconName)}</div>
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(text)}</p>
      ${action}
    </div>`;
}

export function panel({ title, subtitle = '', iconName = '', body, link = '', className = '', headClass = '' }) {
  return `
    <section class="panel ${className}">
      <div class="panel-head ${headClass}">
        <div>
          <h2 class="panel-title">${iconName ? icon(iconName) : ''}${escapeHtml(title)}</h2>
          ${subtitle ? `<p class="panel-sub">${escapeHtml(subtitle)}</p>` : ''}
        </div>
        ${link}
      </div>
      ${body}
    </section>`;
}

export function toast(title, message = '', type = 'success') {
  const root = $('#toast-root');
  if (!root) return;
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `
    ${icon(type === 'error' ? 'alert' : 'check')}
    <div><strong>${escapeHtml(title)}</strong>${message ? `<span>${escapeHtml(message)}</span>` : ''}</div>`;
  root.append(el);
  setTimeout(() => {
    el.classList.add('leaving');
    setTimeout(() => el.remove(), 260);
  }, type === 'error' ? 5200 : 3600);
}

let activeModal = null;

export function closeModal() {
  if (!activeModal) return;
  const { backdrop, previousFocus } = activeModal;
  backdrop.remove();
  activeModal = null;
  document.body.style.overflow = '';
  if (previousFocus && document.body.contains(previousFocus)) previousFocus.focus();
}

export function openModal({ title, subtitle = '', body, footer = '', size = '', onMount = null }) {
  closeModal();
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  backdrop.innerHTML = `
    <div class="modal ${size}" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div class="modal-head">
        <div>
          <h2 id="modal-title">${escapeHtml(title)}</h2>
          ${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ''}
        </div>
        <button class="icon-btn modal-close" data-action="close-modal" aria-label="Close dialog">${icon('x')}</button>
      </div>
      <div class="modal-body">${body}</div>
      ${footer ? `<div class="modal-foot">${footer}</div>` : ''}
    </div>`;
  document.body.append(backdrop);
  activeModal = { backdrop, previousFocus: document.activeElement };
  document.body.style.overflow = 'hidden';
  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) closeModal();
  });
  if (onMount) onMount(backdrop);
  requestAnimationFrame(() => {
    const first = backdrop.querySelector('input:not([type=hidden]), select, textarea, button:not([data-action="close-modal"])');
    first?.focus();
  });
  return backdrop;
}

export function confirmDialog({
  title = 'Are you sure?',
  message = '',
  confirmLabel = 'Confirm',
  danger = false,
} = {}) {
  return new Promise((resolve) => {
    const backdrop = openModal({
      title,
      body: `<p style="font-size:12px;line-height:1.7;color:var(--muted)">${escapeHtml(message)}</p>`,
      footer: `
        <button class="btn btn-ghost" data-confirm="no">Cancel</button>
        <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" data-confirm="yes">${escapeHtml(confirmLabel)}</button>`,
    });
    const finish = (answer) => {
      closeModal();
      resolve(answer);
    };
    backdrop.querySelector('[data-confirm="no"]').addEventListener('click', () => finish(false));
    backdrop.querySelector('[data-confirm="yes"]').addEventListener('click', () => finish(true));
    backdrop.querySelector('[data-action="close-modal"]').addEventListener('click', () => finish(false));
  });
}

let activeDrawer = null;

export function closeDrawer() {
  if (!activeDrawer) return;
  activeDrawer.backdrop.remove();
  activeDrawer = null;
  document.body.style.overflow = activeModal ? 'hidden' : '';
}

export function openDrawer(html) {
  closeDrawer();
  const backdrop = document.createElement('div');
  backdrop.className = 'drawer-backdrop';
  backdrop.innerHTML = html;
  document.body.append(backdrop);
  activeDrawer = { backdrop };
  document.body.style.overflow = 'hidden';
  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) closeDrawer();
  });
}

export function debounce(fn, wait = 280) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

export function buttonBusy(button, label = 'Please wait…') {
  if (!button) return () => {};
  const original = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `<span class="spinner"></span>${escapeHtml(label)}`;
  return () => {
    button.disabled = false;
    button.innerHTML = original;
  };
}

export function readFileAsDataUrl(file, maxBytes = 2_000_000) {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith('image/')) {
      reject(new Error('Choose a PNG, JPEG or WebP image.'));
      return;
    }
    if (file.size > maxBytes) {
      reject(new Error('Photo must be 2 MB or smaller.'));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('Could not read that image.'));
    reader.readAsDataURL(file);
  });
}

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    if (activeModal) closeModal();
    else if (activeDrawer) closeDrawer();
  }
});
