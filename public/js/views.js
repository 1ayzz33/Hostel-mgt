/* View templates. All user-provided strings pass through escapeHtml(). */
import {
  avatar,
  conditionBadge,
  dueLabel,
  emptyState,
  escapeHtml,
  formatDate,
  formatDateTime,
  icon,
  initials,
  openModal,
  pageHead,
  panel,
  priorityLabel,
  readFileAsDataUrl,
  stars,
  statusBadge,
  timeAgo,
} from './ui.js';

const CATEGORY_ICON = {
  Electrical: 'bolt',
  Plumbing: 'droplet',
  Furniture: 'sofa',
  'Internet / ICT': 'wifi',
  Sanitation: 'trash',
  Security: 'shield',
  'HVAC / Ventilation': 'fan',
  Other: 'box',
};

const CATEGORY_TINT = {
  Electrical: 'var(--warning-soft);color:var(--warning)',
  Plumbing: 'var(--info-soft);color:var(--info)',
  Furniture: 'var(--accent-soft);color:var(--accent-deep)',
  'Internet / ICT': 'var(--purple-soft);color:var(--purple)',
  Sanitation: 'var(--green-soft);color:var(--green)',
  Security: 'var(--danger-soft);color:var(--danger)',
  'HVAC / Ventilation': '#e8f4f1;color:#2d7b73',
  Other: 'var(--surface-tint);color:var(--brand)',
};

const ROLE_LABEL = { student: 'Student', staff: 'Maintenance', admin: 'Administrator' };
const AUDIENCE_LABEL = { all: 'Everyone', students: 'Students', staff: 'Staff', admin: 'Admins' };
const ACTION_LABEL = {
  created: 'Report submitted',
  assigned: 'Assigned to maintenance',
  in_progress: 'Work started',
  resolved: 'Marked resolved',
  closed: 'Report closed',
  reopened: 'Report reopened',
  comment: 'Comment added',
  feedback: 'Service rated',
};

function catIcon(category) {
  return CATEGORY_ICON[category] || 'wrench';
}

function catIconStyle(category) {
  const value = CATEGORY_TINT[category] || CATEGORY_TINT.Other;
  return `style="background:${value.split(';')[0]};${value.includes(';') ? value.split(';')[1] : ''}"`;
}

function selectOptions(options, selected, placeholder = '') {
  const head = placeholder ? `<option value="">${escapeHtml(placeholder)}</option>` : '';
  return head + options.map((option) => {
    const value = typeof option === 'string' ? option : option.value;
    const label = typeof option === 'string' ? option : option.label;
    return `<option value="${escapeHtml(value)}" ${String(value) === String(selected) ? 'selected' : ''}>${escapeHtml(label)}</option>`;
  }).join('');
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

function firstName(name) {
  return String(name || '').split(' ')[0];
}

function statCard({ label, value, iconName, sub = '', tone = '', small = '' }) {
  return `
    <article class="stat-card ${tone}">
      <div class="stat-top">
        <span class="stat-icon">${icon(iconName)}</span>
        <span class="stat-label">${escapeHtml(label)}</span>
      </div>
      <div class="stat-value">${value}${small ? `<small>${escapeHtml(small)}</small>` : ''}</div>
      <div class="stat-bottom">${sub}</div>
    </article>`;
}

function reportRow(report, { showStudent = false } = {}) {
  return `
    <button class="report-row" data-action="open-report" data-id="${report.id}">
      <span class="report-icon" ${catIconStyle(report.category)}>${icon(catIcon(report.category))}</span>
      <span class="report-main">
        <span class="report-title">${escapeHtml(report.title)}</span>
        <span class="report-meta">
          <span class="mono">${escapeHtml(report.ref)}</span>
          <span class="report-meta-dot"></span>
          <span>${escapeHtml(report.hostel_name)}</span>
          ${showStudent ? `<span class="report-meta-dot"></span><span>${escapeHtml(report.student_name)}</span>` : ''}
          ${report.is_overdue ? `<span class="overdue-flag">${icon('alert')} SLA</span>` : ''}
        </span>
      </span>
      <span class="report-side">
        <span class="report-date">${timeAgo(report.created_at)}</span>
        ${statusBadge(report.status)}
        <span class="report-chevron">${icon('chevron')}</span>
      </span>
    </button>`;
}

function announcementItems(items, limit = 3) {
  if (!items.length) {
    return emptyState({
      title: 'No announcements yet',
      text: 'Notices from the hostel office will appear here.',
      iconName: 'megaphone',
    });
  }
  return `<div class="announcement-list">${items.slice(0, limit).map((item) => `
    <article class="announcement-item">
      <h4>${item.is_pinned ? icon('star', 'pin') : ''}${escapeHtml(item.title)}</h4>
      <p>${escapeHtml(item.body)}</p>
      <div class="ann-meta"><span class="audience">${escapeHtml(AUDIENCE_LABEL[item.audience] || item.audience)}</span><span>${timeAgo(item.created_at)}</span></div>
    </article>`).join('')}</div>`;
}

/* ==========================================================================
   Authentication
   ========================================================================== */
export function renderAuth(mode = 'login', hostels = []) {
  if (mode === 'register') {
    return `
      <h2>Create your student account.</h2>
      <p class="auth-lede">Report a fault in under a minute and follow every step until it is fixed.</p>
      <form class="auth-form" data-form="register" novalidate>
        <div class="form-grid">
          <div class="field span-2">
            <label for="reg-name">Full name <span class="req">*</span></label>
            <input class="input" id="reg-name" name="full_name" autocomplete="name" placeholder="e.g. Sarah Adamu" required>
          </div>
          <div class="field span-2">
            <label for="reg-email">Email address <span class="req">*</span></label>
            <div class="field-with-icon">${icon('mail')}<input class="input" type="email" id="reg-email" name="email" autocomplete="email" placeholder="you@student.edu.ng" required></div>
          </div>
          <div class="field">
            <label for="reg-matric">Matric number <span class="req">*</span></label>
            <input class="input" id="reg-matric" name="student_id" placeholder="NSUK/CSC/21/041" required>
          </div>
          <div class="field">
            <label for="reg-hostel">Hostel</label>
            <select class="select" id="reg-hostel" name="hostel_id">
              ${selectOptions(hostels.map((h) => ({ value: h.id, label: `${h.name} (${h.code})` })), '', 'Choose later')}
            </select>
          </div>
          <div class="field">
            <label for="reg-room">Room number</label>
            <input class="input" id="reg-room" name="room_number" placeholder="e.g. 204">
          </div>
          <div class="field">
            <label for="reg-dept">Department</label>
            <input class="input" id="reg-dept" name="department" placeholder="e.g. Computer Science">
          </div>
          <div class="field span-2">
            <label for="reg-password">Password <span class="req">*</span></label>
            <div class="field-with-icon">${icon('lock')}
              <input class="input" type="password" id="reg-password" name="password" autocomplete="new-password" placeholder="At least 8 characters" minlength="8" required>
              <button class="password-toggle" type="button" data-action="toggle-password" data-target="reg-password" aria-label="Show password">${icon('eye')}</button>
            </div>
          </div>
        </div>
        <div id="auth-error" class="auth-error hidden" role="alert"></div>
        <button class="btn btn-primary btn-lg btn-block" type="submit">Create my account ${icon('arrow-right')}</button>
        <p class="auth-hint">By creating an account you agree to use the platform only for genuine hostel facility reports.</p>
      </form>`;
  }

  return `
    <h2>Welcome back.</h2>
    <p class="auth-lede">Sign in to report a fault, manage maintenance or review hostel operations.</p>
    <form class="auth-form" data-form="login" novalidate>
      <div class="field">
        <label for="login-email">Email address</label>
        <div class="field-with-icon">${icon('mail')}<input class="input" type="email" id="login-email" name="email" autocomplete="email" placeholder="you@hostelhub.edu.ng" required></div>
      </div>
      <div class="field">
        <label for="login-password">Password</label>
        <div class="field-with-icon">${icon('lock')}
          <input class="input" type="password" id="login-password" name="password" autocomplete="current-password" placeholder="Enter your password" required>
          <button class="password-toggle" type="button" data-action="toggle-password" data-target="login-password" aria-label="Show password">${icon('eye')}</button>
        </div>
      </div>
      <div id="auth-error" class="auth-error hidden" role="alert"></div>
      <button class="btn btn-primary btn-lg btn-block" type="submit">Sign in ${icon('arrow-right')}</button>
    </form>
    <div class="demo-block">
      <div class="demo-label">Explore the demo</div>
      <div class="demo-buttons">
        <button class="demo-btn" type="button" data-action="fill-demo" data-role="student">${icon('user')}Student</button>
        <button class="demo-btn" type="button" data-action="fill-demo" data-role="staff">${icon('wrench')}Maintenance</button>
        <button class="demo-btn" type="button" data-action="fill-demo" data-role="admin">${icon('shield')}Administrator</button>
      </div>
    </div>`;
}

/* ==========================================================================
   Navigation
   ========================================================================== */
export function renderNav(user, unread = 0, activeView = 'dashboard') {
  const isAdmin = user.role === 'admin';
  const items = [
    { view: 'dashboard', label: 'Dashboard', iconName: 'grid' },
    { view: 'reports', label: user.role === 'staff' ? 'My queue' : 'Reports', iconName: 'clipboard' },
    { view: 'notifications', label: 'Notifications', iconName: 'bell', badge: unread },
  ];
  if (isAdmin) {
    items.push(
      { view: 'users', label: 'People', iconName: 'users' },
      { view: 'hostels', label: 'Hostels', iconName: 'building' },
      { view: 'announcements', label: 'Announcements', iconName: 'megaphone' },
    );
  }
  return items.map((item) => `
    <button class="nav-item ${item.view === activeView ? 'active' : ''}" data-action="go" data-view="${item.view}">
      ${icon(item.iconName)}<span>${item.label}</span>
      ${item.badge ? `<span class="nav-badge">${item.badge > 9 ? '9+' : item.badge}</span>` : ''}
    </button>`).join('');
}

export function renderMobileNav(user, unread = 0, activeView = 'dashboard') {
  const items = [
    { view: 'dashboard', label: 'Home', iconName: 'grid' },
    { view: 'reports', label: user.role === 'staff' ? 'Queue' : 'Reports', iconName: 'clipboard' },
    { view: 'notifications', label: 'Alerts', iconName: 'bell', badge: unread },
  ];
  if (user.role === 'admin') items.push({ view: 'users', label: 'People', iconName: 'users' });
  return items.map((item) => `
    <button class="mobile-nav-item ${item.view === activeView ? 'active' : ''}" data-action="go" data-view="${item.view}">
      ${icon(item.iconName)}<span>${item.label}</span>
      ${item.badge ? `<span class="nav-badge">${item.badge > 9 ? '9+' : item.badge}</span>` : ''}
    </button>`).join('');
}

export function renderSidebarUser(user) {
  const subtitle = user.role === 'admin' ? 'Facilities administrator' : user.role === 'staff' ? 'Maintenance team' : (user.student_id || 'Student resident');
  return `
    ${avatar(user)}
    <div class="sidebar-user-copy"><strong>${escapeHtml(user.full_name)}</strong><small>${escapeHtml(subtitle)}</small></div>
    <button class="icon-btn" data-action="logout" title="Sign out" aria-label="Sign out">${icon('logout')}</button>`;
}

export function renderSidebarNote(user) {
  if (user.role === 'admin') {
    return `${icon('trending', 'note-icon')}<strong>Operations at a glance</strong><p>Track SLA breaches, staff workload and resident satisfaction from one place.</p>`;
  }
  if (user.role === 'staff') {
    return `${icon('clock', 'note-icon')}<strong>Priority-first queue</strong><p>Urgent reports have a 6-hour target. Start work as soon as you accept a job.</p>`;
  }
  return `${icon('shield', 'note-icon')}<strong>Your report is tracked</strong><p>Every update is time-stamped, so you always know who is working on the issue.</p>`;
}

/* ==========================================================================
   Dashboard
   ========================================================================== */
export function renderDashboard({ data, analytics, meta, user }) {
  if (user.role === 'admin') return renderAdminDashboard(data, analytics, meta, user);
  if (user.role === 'staff') return renderStaffDashboard(data, meta, user);
  return renderStudentDashboard(data, meta, user);
}

function renderStudentDashboard(data, meta, user) {
  const stats = data.stats;
  const hostel = meta.hostels.find((h) => h.id === user.hostel_id);
  const recent = data.recent || [];
  return `
    ${pageHead({
      kicker: 'Resident workspace',
      kickerIcon: 'home',
      title: `${greeting()}, ${escapeHtml(firstName(user.full_name))}.`,
      subtitle: 'See what is happening in your hall, report a fault and follow the repair from start to finish.',
      actions: `<button class="btn btn-primary" data-action="new-report">${icon('plus')} Report an issue</button>`,
    })}
    ${data.stats.overdue ? `
      <div class="attention-banner">
        <span class="attention-icon">${icon('alert')}</span>
        <div><strong>${data.stats.overdue} report${data.stats.overdue > 1 ? 's' : ''} past the response target</strong><p>The maintenance team has been notified. You can add more detail to help them respond.</p></div>
        <button class="btn btn-sm btn-ghost" data-action="go" data-view="reports">Review</button>
      </div>` : ''}
    <div class="stats-grid">
      ${statCard({ label: 'Open reports', value: stats.open, iconName: 'clipboard', sub: `<strong>${stats.total}</strong> submitted in total` })}
      ${statCard({ label: 'In progress', value: stats.in_progress, iconName: 'wrench', tone: 'purple', sub: 'Maintenance is working on it' })}
      ${statCard({ label: 'Resolved', value: stats.resolved, iconName: 'check', tone: 'info', sub: 'Closed or awaiting your rating' })}
      ${statCard({ label: 'Your rating', value: stats.average_rating ? stats.average_rating.toFixed(1) : '—', small: stats.average_rating ? '/5' : '', iconName: 'star', sub: stats.average_rating ? 'Average service score' : 'Rate a completed repair' })}
    </div>
    <div class="layout-2col">
      <div class="stack">
        ${panel({
          title: 'Recent reports',
          subtitle: 'Your latest submissions and their progress',
          iconName: 'clipboard',
          link: `<button class="panel-link" data-action="go" data-view="reports">View all ${icon('arrow-right')}</button>`,
          body: recent.length
            ? `<div class="report-list">${recent.map((report) => reportRow(report)).join('')}</div>`
            : emptyState({
                title: 'No reports yet',
                text: 'Spotted a leaking tap, a faulty socket or a broken chair? Report it and the maintenance team will take it from there.',
                action: `<button class="btn btn-primary btn-sm" data-action="new-report">${icon('plus')} Report your first issue</button>`,
                iconName: 'wrench',
              }),
        })}
        <section class="panel">
          <div class="panel-head"><div><h2 class="panel-title">${icon('sparkles')}How reporting works</h2><p class="panel-sub">A simple, transparent repair loop</p></div></div>
          <div class="panel-body">
            <div class="how-it-works">
              <div class="how-step"><span class="how-num">1</span><strong>Tell us what is wrong</strong><p>Pick a category, add a location and attach a photo if you can.</p></div>
              <div class="how-step"><span class="how-num">2</span><strong>We assign the right team</strong><p>The facilities desk triages and assigns your report by priority.</p></div>
              <div class="how-step"><span class="how-num">3</span><strong>Track it to resolution</strong><p>Follow updates, comment, then rate the repair when it is done.</p></div>
            </div>
          </div>
        </section>
      </div>
      <div class="stack">
        ${panel({
          title: 'Announcements',
          subtitle: 'From the hostel office',
          iconName: 'megaphone',
          body: announcementItems(data.announcements || []),
        })}
        ${hostel ? `
          <section class="panel hostel-mini">
            <div class="hostel-mini-cover"><span class="building-mark">${icon('building')}</span></div>
            <div class="hostel-mini-body">
              <h3>${escapeHtml(hostel.name)}</h3>
              <p>${escapeHtml(hostel.code)} · ${escapeHtml(hostel.gender)} hostel · Room ${escapeHtml(user.room_number || '—')}</p>
              <div class="warden-line">
                ${avatar(hostel.warden_name || 'Warden', 'avatar-sm')}
                <div class="warden-copy"><strong>${escapeHtml(hostel.warden_name || 'Hostel warden')}</strong><small>Hall warden</small></div>
                <span class="warden-phone">${escapeHtml(hostel.warden_phone || '')}</span>
              </div>
            </div>
          </section>` : ''}
      </div>
    </div>`;
}

function renderStaffDashboard(data, meta, user) {
  const stats = data.stats;
  const queue = data.recent || [];
  const announcements = data.announcements || [];
  return `
    ${pageHead({
      kicker: 'Maintenance workspace',
      kickerIcon: 'wrench',
      title: `${greeting()}, ${escapeHtml(firstName(user.full_name))}.`,
      subtitle: 'Your assigned jobs, priority-first. Keep residents informed with a short update as you work.',
      actions: `<button class="btn btn-primary" data-action="go" data-view="reports">${icon('clipboard')} Open my queue</button>`,
    })}
    ${data.stats.overdue ? `
      <div class="attention-banner">
        <span class="attention-icon">${icon('alert')}</span>
        <div><strong>${data.stats.overdue} assigned job${data.stats.overdue > 1 ? 's have' : ' has'} breached the SLA target</strong><p>Review the queue and add an update so the resident and facilities desk can see the status.</p></div>
        <button class="btn btn-sm btn-ghost" data-action="go" data-view="reports">Review queue</button>
      </div>` : ''}
    <div class="stats-grid">
      ${statCard({ label: 'Active jobs', value: stats.active, iconName: 'clipboard', sub: `<strong>${stats.assigned}</strong> assigned in total` })}
      ${statCard({ label: 'In progress', value: stats.in_progress, iconName: 'wrench', tone: 'purple', sub: 'Currently on your bench' })}
      ${statCard({ label: 'Overdue', value: stats.overdue, iconName: 'clock', tone: 'danger', sub: 'Past the response target' })}
      ${statCard({ label: 'Resolved this month', value: stats.resolved_this_month, iconName: 'check', tone: 'info', sub: stats.average_rating ? `Average rating <strong>${stats.average_rating}/5</strong>` : 'No ratings yet' })}
    </div>
    <div class="layout-2col">
      <div class="stack">
        ${panel({
          title: 'Your queue',
          subtitle: 'Assigned reports, newest first',
          iconName: 'clipboard',
          link: `<button class="panel-link" data-action="go" data-view="reports">Full queue ${icon('arrow-right')}</button>`,
          body: queue.length ? `<div class="queue-list">${queue.map(queueItem).join('')}</div>` : emptyState({
            title: 'Your queue is clear',
            text: 'When the facilities desk assigns you a report it will appear here with its priority and response target.',
            iconName: 'check',
          }),
        })}
      </div>
      <div class="stack">
        ${panel({
          title: 'Your service score',
          subtitle: 'Based on resident feedback',
          iconName: 'star',
          body: `
            <div style="display:flex;align-items:flex-end;gap:12px;margin-bottom:10px">
              <div style="font-size:42px;font-weight:650;letter-spacing:-.06em;line-height:1">${stats.average_rating ? stats.average_rating.toFixed(1) : '—'}<span style="font-size:15px;color:var(--muted);letter-spacing:0">/5</span></div>
              <div style="padding-bottom:5px">${stars(stats.average_rating || 0)}<div style="font-size:9px;color:var(--muted-2);margin-top:3px">Resident satisfaction</div></div>
            </div>
            <div style="font-size:10px;color:var(--muted);line-height:1.65">A clear resolution note and a timely update are the biggest drivers of a good rating. Residents can rate a repair once it is marked resolved.</div>`,
        })}
        ${panel({
          title: 'Announcements',
          subtitle: 'Team and hostel notices',
          iconName: 'megaphone',
          body: announcementItems(announcements, 2),
        })}
      </div>
    </div>`;
}

function queueItem(report) {
  return `
    <button class="queue-item" data-action="open-report" data-id="${report.id}">
      <span class="queue-priority ${report.priority}"></span>
      <span class="queue-main">
        <h4>${escapeHtml(report.title)}</h4>
        <span class="queue-meta">
          <span class="mono">${escapeHtml(report.ref)}</span>
          <span>${escapeHtml(report.hostel_name)}</span>
          <span>${escapeHtml(report.location)}</span>
          ${report.is_overdue ? `<span class="overdue-flag">${icon('alert')} ${dueLabel(report)}</span>` : `<span>${dueLabel(report)}</span>`}
        </span>
        <span class="queue-actions">${statusBadge(report.status)} ${priorityLabel(report.priority)}</span>
      </span>
      <span class="report-chevron" style="align-self:center">${icon('chevron')}</span>
    </button>`;
}

function renderAdminDashboard(data, analytics, meta, user) {
  const stats = data.stats;
  const recent = data.recent || [];
  const staff = data.staff || [];
  const statuses = analytics?.by_status || [];
  const totalReports = statuses.reduce((sum, item) => sum + item.count, 0);
  const openCount = statuses.filter((s) => ['submitted', 'assigned', 'in_progress', 'reopened'].includes(s.status)).reduce((sum, s) => sum + s.count, 0);
  const statusPalette = {
    submitted: '#1f7a63',
    assigned: '#e79a4d',
    in_progress: '#9b88c4',
    reopened: '#bf3f45',
    resolved: '#7fa892',
    closed: '#d5ddd7',
  };
  let cursor = 0;
  const segments = statuses.filter((s) => s.count > 0).map((s) => {
    const start = cursor;
    cursor += totalReports ? (s.count / totalReports) * 100 : 0;
    return `${statusPalette[s.status] || '#d5ddd7'} ${start}% ${cursor}%`;
  });
  const donutStyle = segments.length ? `background: conic-gradient(${segments.join(', ')})` : '';

  return `
    ${pageHead({
      kicker: 'Facilities command centre',
      kickerIcon: 'shield',
      title: `${greeting()}, ${escapeHtml(firstName(user.full_name))}.`,
      subtitle: 'A live view of hostel conditions, maintenance workload and the resident experience.',
      actions: `
        <button class="btn btn-ghost" data-action="go" data-view="users">${icon('users')} People</button>
        <button class="btn btn-primary" data-action="new-announcement">${icon('megaphone')} New announcement</button>`,
    })}
    ${stats.overdue ? `
      <div class="attention-banner">
        <span class="attention-icon">${icon('alert')}</span>
        <div><strong>${stats.overdue} report${stats.overdue > 1 ? 's are' : ' is'} past the SLA target</strong><p>Review the oldest breaches first, then reassign or update the resident.</p></div>
        <button class="btn btn-sm btn-ghost" data-action="go" data-view="reports">Review breaches</button>
      </div>` : ''}
    <div class="stats-grid">
      ${statCard({ label: 'Open reports', value: stats.open, iconName: 'clipboard', sub: `<strong>${stats.total}</strong> reports all time` })}
      ${statCard({ label: 'SLA breaches', value: stats.overdue, iconName: 'clock', tone: 'danger', sub: 'Open and past target' })}
      ${statCard({ label: 'Resolved this month', value: stats.resolved_this_month, iconName: 'check', tone: 'info', sub: stats.avg_resolution_hours ? `<strong>${stats.avg_resolution_hours}h</strong> average resolution` : 'No resolutions yet' })}
      ${statCard({ label: 'Satisfaction', value: stats.average_rating ? stats.average_rating.toFixed(1) : '—', small: stats.average_rating ? '/5' : '', iconName: 'star', sub: `${analytics?.totals?.ratings || 0} resident ratings` })}
    </div>
    <div class="dashboard-charts">
      ${panel({
        title: 'Reporting volume',
        subtitle: 'Submitted vs resolved over the last six months',
        iconName: 'trending',
        className: 'chart-panel',
        link: `<div class="trend-legend"><span class="legend-item"><span class="legend-dot submitted"></span>Submitted</span><span class="legend-item"><span class="legend-dot resolved"></span>Resolved</span></div>`,
        body: `<div class="panel-body">${trendChart(analytics?.trend || [])}</div>`,
      })}
      ${panel({
        title: 'Fault categories',
        subtitle: 'Where maintenance demand comes from',
        iconName: 'wrench',
        className: 'chart-panel',
        body: `<div class="panel-body">${categoryChart(analytics?.by_category || [])}</div>`,
      })}
    </div>
    <div class="layout-2col">
      <div class="stack">
        ${panel({
          title: 'Latest reports',
          subtitle: 'Every new submission across the four halls',
          iconName: 'clipboard',
          link: `<button class="panel-link" data-action="go" data-view="reports">All reports ${icon('arrow-right')}</button>`,
          body: recent.length ? `<div class="report-list">${recent.map((report) => reportRow(report, { showStudent: true })).join('')}</div>` : emptyState({ title: 'No reports yet', text: 'New resident reports will appear here.', iconName: 'clipboard' }),
        })}
      </div>
      <div class="stack">
        ${panel({
          title: 'Report status',
          subtitle: `${totalReports} reports in the system`,
          iconName: 'grid',
          body: `
            <div class="donut-flex">
              <div class="donut" style="${donutStyle}">
                <div class="donut-center"><strong>${openCount}</strong><span>open</span></div>
              </div>
              <div class="donut-legend">
                ${statuses.filter((s) => s.count > 0).map((s) => `
                  <div class="donut-legend-item"><span class="legend-dot ${s.status}" style="background:${statusPalette[s.status]}"></span>${escapeHtml(s.status.replaceAll('_', ' '))}<strong>${s.count}</strong></div>`).join('')}
              </div>
            </div>`,
        })}
        ${panel({
          title: 'Team workload',
          subtitle: 'Active jobs per maintenance officer',
          iconName: 'users',
          link: `<button class="panel-link" data-action="go" data-view="users">Manage ${icon('arrow-right')}</button>`,
          body: `<div class="table-wrap"><table class="data-table"><thead><tr><th>Officer</th><th>Active load</th></tr></thead><tbody>
            ${staff.slice(0, 4).map((member) => {
              const load = Number(member.active || 0);
              const cls = load >= 4 ? 'over' : load >= 2 ? 'high' : '';
              return `<tr><td><div class="table-user">${avatar(member.full_name, 'avatar-sm')}<div><strong>${escapeHtml(member.full_name)}</strong><small>${escapeHtml((member.department || '').split('&')[0].trim())}</small></div></div></td>
                <td class="load-cell"><div class="load-top"><span>${load} active</span><strong>${member.assigned || 0} total</strong></div><div class="load-track"><div class="load-fill ${cls}" style="width:${Math.min(100, load * 22)}%"></div></div></td></tr>`;
            }).join('')}
          </tbody></table></div>`,
        })}
      </div>
    </div>`;
}

function trendChart(trend) {
  const data = trend.length ? trend : [{ month: '—', submitted: 0, resolved: 0 }];
  const width = 620, height = 190, left = 30, right = 12, top = 16, bottom = 30;
  const innerW = width - left - right;
  const innerH = height - top - bottom;
  const max = Math.max(4, ...data.map((d) => Math.max(d.submitted, d.resolved)));
  const step = data.length > 1 ? innerW / (data.length - 1) : innerW;
  const x = (i) => left + i * step;
  const y = (value) => top + innerH - (value / max) * innerH;
  const submittedPoints = data.map((d, i) => `${x(i)},${y(d.submitted)}`).join(' ');
  const resolvedPoints = data.map((d, i) => `${x(i)},${y(d.resolved)}`).join(' ');
  const area = `${left},${top + innerH} ${submittedPoints} ${x(data.length - 1)},${top + innerH}`;
  const grid = [0, 0.5, 1].map((fraction) => {
    const gy = top + innerH * fraction;
    return `<line class="trend-grid-line" x1="${left}" y1="${gy}" x2="${width - right}" y2="${gy}"/>`;
  }).join('');
  return `
    <svg class="trend-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Line chart of reports submitted and resolved by month">
      <defs>
        <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#2f8f73" stop-opacity=".22"/>
          <stop offset="1" stop-color="#2f8f73" stop-opacity="0"/>
        </linearGradient>
      </defs>
      ${grid}
      <path class="trend-area" d="M${area.replaceAll(' ', ' L')} Z"/>
      <polyline class="trend-line-submitted" points="${submittedPoints}"/>
      <polyline class="trend-line-resolved" points="${resolvedPoints}"/>
      ${data.map((d, i) => `<circle class="trend-point" cx="${x(i)}" cy="${y(d.submitted)}" r="3" stroke="#2f8f73"/>`).join('')}
      ${data.map((d, i) => `<circle class="trend-point" cx="${x(i)}" cy="${y(d.resolved)}" r="3" stroke="#e79a4d"/>`).join('')}
      ${data.map((d, i) => `<text class="trend-axis-label" x="${x(i)}" y="${height - 8}" text-anchor="middle">${escapeHtml(d.month)}</text>`).join('')}
    </svg>`;
}

function categoryChart(categories) {
  const items = categories.filter((item) => item.total > 0).sort((a, b) => b.total - a.total).slice(0, 6);
  if (!items.length) return emptyState({ title: 'No category data', text: 'Reports will populate this chart.', iconName: 'wrench' });
  const max = Math.max(...items.map((item) => item.total));
  return `<div class="bar-chart">${items.map((item) => `
    <div class="bar-row">
      <span class="bar-label" title="${escapeHtml(item.category)}">${escapeHtml(item.category)}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(4, (item.total / max) * 100)}%"></div></div>
      <span class="bar-value">${item.total}</span>
    </div>`).join('')}</div>`;
}

/* ==========================================================================
   Reports
   ========================================================================== */
export function renderReports({ data, meta, user, filters }) {
  const reports = data.items || [];
  const canCreate = user.role === 'student';
  const statusOptions = meta.statuses.map((status) => ({ value: status, label: status.replaceAll('_', ' ') }));
  const categoryOptions = meta.categories;
  const hostelOptions = meta.hostels.map((h) => ({ value: h.id, label: `${h.name} (${h.code})` }));
  const activeFilters = ['status', 'priority', 'category', 'hostel_id'].filter((key) => filters[key]);
  return `
    ${pageHead({
      kicker: user.role === 'staff' ? 'Assigned maintenance' : user.role === 'admin' ? 'All facility reports' : 'My reports',
      kickerIcon: 'clipboard',
      title: user.role === 'staff' ? 'Your maintenance queue.' : user.role === 'admin' ? 'Facility reports.' : 'Your reports.',
      subtitle: user.role === 'staff'
        ? 'Prioritised jobs and their response targets. Open a report to start work or add an update.'
        : user.role === 'admin'
          ? 'Search, filter and assign every report across the hostel portfolio.'
          : 'Every fault you have reported, with its current status and the team handling it.',
      actions: canCreate
        ? `<button class="btn btn-primary" data-action="new-report">${icon('plus')} New report</button>`
        : `<button class="btn btn-ghost" data-action="refresh">${icon('refresh')} Refresh</button>`,
    })}
    <section class="panel">
      <div class="toolbar">
        <div class="search-field">${icon('search')}<input class="input" id="report-search" placeholder="Search reference, title, location${user.role === 'admin' ? ' or student' : ''}…" value="${escapeHtml(filters.q || '')}" autocomplete="off"></div>
        <select class="filter-select" data-filter="status" aria-label="Filter by status">
          ${selectOptions(statusOptions, filters.status, 'All statuses')}
        </select>
        <select class="filter-select" data-filter="priority" aria-label="Filter by priority">
          ${selectOptions(meta.priorities, filters.priority, 'All priorities')}
        </select>
        <select class="filter-select" data-filter="category" aria-label="Filter by category">
          ${selectOptions(categoryOptions, filters.category, 'All categories')}
        </select>
        ${user.role === 'admin' ? `<select class="filter-select" data-filter="hostel_id" aria-label="Filter by hostel">${selectOptions(hostelOptions, filters.hostel_id, 'All hostels')}</select>` : ''}
        <button class="filter-toggle ${filters.overdue ? 'active' : ''}" data-action="toggle-overdue">${icon('alert')} SLA only</button>
      </div>
      <div class="results-meta">
        <span><strong>${data.total}</strong> report${data.total === 1 ? '' : 's'} ${activeFilters.length || filters.overdue ? 'matching your filters' : 'in this view'}</span>
        ${activeFilters.length || filters.overdue || filters.q ? `<button class="btn-link" data-action="clear-filters">${icon('x')} Clear filters</button>` : `<span>Sorted by newest first</span>`}
      </div>
      ${reports.length ? `
        <div class="table-wrap">
          <table class="data-table report-table">
            <thead><tr><th>Report</th><th>Hostel / location</th>${user.role === 'admin' ? '<th>Student</th>' : ''}<th>Priority</th><th>Status</th><th>Assigned</th><th>Updated</th><th></th></tr></thead>
            <tbody>${reports.map((report) => reportTableRow(report, user)).join('')}</tbody>
          </table>
        </div>
        <div class="mobile-cards">${reports.map((report) => reportCard(report, user)).join('')}</div>
      ` : emptyState({
        title: 'No reports found',
        text: activeFilters.length || filters.q ? 'Try clearing one or more filters to see more reports.' : canCreate ? 'You have not reported a facility issue yet. It only takes a minute.' : 'There are no reports in this view yet.',
        action: activeFilters.length || filters.q ? `<button class="btn btn-soft btn-sm" data-action="clear-filters">Clear filters</button>` : canCreate ? `<button class="btn btn-primary btn-sm" data-action="new-report">${icon('plus')} Report an issue</button>` : '',
        iconName: 'search',
      })}
    </section>`;
}

function reportTableRow(report, user) {
  return `
    <tr>
      <td class="report-title-cell">
        <button class="table-link" data-action="open-report" data-id="${report.id}">${escapeHtml(report.title)}</button>
        <small class="mono">${escapeHtml(report.ref)}</small>
      </td>
      <td>${escapeHtml(report.hostel_name)}<span class="cell-sub">${escapeHtml(report.location)}</span></td>
      ${user.role === 'admin' ? `<td>${escapeHtml(report.student_name)}<span class="cell-sub">${escapeHtml(report.student_room || '')}</span></td>` : ''}
      <td>${priorityLabel(report.priority)}${report.is_overdue ? `<span class="overdue-flag">${icon('alert')} SLA</span>` : ''}</td>
      <td>${statusBadge(report.status)}</td>
      <td>${report.staff_name ? `<div class="table-user">${avatar(report.staff_name, 'avatar-sm')}<div><strong>${escapeHtml(report.staff_name)}</strong><small>Maintenance</small></div></div>` : '<span style="color:var(--muted-2);font-size:9.5px">Unassigned</span>'}</td>
      <td>${timeAgo(report.updated_at)}</td>
      <td><button class="icon-btn" style="width:28px;height:28px" data-action="open-report" data-id="${report.id}" aria-label="Open ${escapeHtml(report.ref)}">${icon('chevron')}</button></td>
    </tr>`;
}

function reportCard(report, user) {
  return `
    <button class="report-card" data-action="open-report" data-id="${report.id}">
      <span class="report-card-top">${statusBadge(report.status)} ${priorityLabel(report.priority)} <span class="mono" style="margin-left:auto;color:var(--muted-2);font-size:8.5px">${escapeHtml(report.ref)}</span></span>
      <h4>${escapeHtml(report.title)}</h4>
      <span class="report-card-meta">${icon(catIcon(report.category))} ${escapeHtml(report.category)} <span class="report-meta-dot"></span> ${escapeHtml(report.hostel_name)} <span class="report-meta-dot"></span> ${escapeHtml(report.location)}</span>
      <span class="report-card-foot"><span style="font-size:8.5px;color:var(--muted-2)">${user.role === 'admin' ? escapeHtml(report.student_name) : ''} ${timeAgo(report.created_at)}</span><span style="font-size:8.5px;color:${report.is_overdue ? 'var(--danger)' : 'var(--muted-2)'}">${report.is_overdue ? 'SLA breached' : dueLabel(report)}</span></span>
    </button>`;
}

/* ==========================================================================
   Notifications
   ========================================================================== */
export function renderNotifications(data) {
  const items = data.items || [];
  return `
    ${pageHead({
      kicker: 'Activity feed',
      kickerIcon: 'bell',
      title: 'Notifications.',
      subtitle: 'Report updates, assignments, comments and service ratings in one feed.',
      actions: items.length ? `<button class="btn btn-ghost" data-action="mark-all-read">${icon('check')} Mark all as read</button>` : '',
    })}
    <section class="panel">
      ${items.length ? `<div class="notif-list">${items.map((item) => `
        <button class="notif-item ${item.is_read ? '' : 'unread'}" data-action="${item.report_id ? 'open-notification' : 'noop'}" data-id="${item.report_id || ''}">
          <span class="notif-icon">${icon(item.title.toLowerCase().includes('resolved') ? 'check' : item.title.toLowerCase().includes('assigned') ? 'wrench' : item.title.toLowerCase().includes('comment') ? 'message' : 'bell')}</span>
          <span class="notif-body">
            <strong>${escapeHtml(item.title)}</strong>
            <p>${escapeHtml(item.message)}</p>
            <span class="notif-time">${timeAgo(item.created_at)} ${item.report_id ? `<span class="report-meta-dot"></span><span class="mono" style="font-size:8px">Open report</span>` : ''}</span>
          </span>
          ${item.is_read ? '' : '<span class="notif-dot"></span>'}
        </button>`).join('')}</div>` : emptyState({
        title: 'You are all caught up',
        text: 'Updates about your reports and assignments will appear here.',
        iconName: 'bell',
      })}
    </section>`;
}

/* ==========================================================================
   People (admin)
   ========================================================================== */
export function renderUsers({ users, filters }) {
  const roleOptions = [
    { value: 'student', label: 'Students' },
    { value: 'staff', label: 'Maintenance staff' },
    { value: 'admin', label: 'Administrators' },
  ];
  return `
    ${pageHead({
      kicker: 'People directory',
      kickerIcon: 'users',
      title: 'People.',
      subtitle: 'Manage students, maintenance officers and administrators. Deactivated accounts lose access immediately.',
      actions: `<button class="btn btn-primary" data-action="new-user">${icon('plus')} Add person</button>`,
    })}
    <section class="panel">
      <div class="toolbar">
        <div class="search-field">${icon('search')}<input class="input" id="user-search" placeholder="Search name, email or matric number…" value="${escapeHtml(filters.q || '')}" autocomplete="off"></div>
        <select class="filter-select" data-filter="user_role" aria-label="Filter by role">${selectOptions(roleOptions, filters.role, 'All roles')}</select>
      </div>
      <div class="results-meta"><span><strong>${users.length}</strong> people</span><span>Roles control access across the platform</span></div>
      ${users.length ? `<div class="table-wrap"><table class="data-table">
        <thead><tr><th>Person</th><th>Role</th><th>Hostel / department</th><th>Activity</th><th>Status</th><th></th></tr></thead>
        <tbody>${users.map((person) => `
          <tr style="${person.is_active ? '' : 'opacity:.62'}">
            <td><div class="table-user">${avatar(person)}<div><strong>${escapeHtml(person.full_name)}</strong><small>${escapeHtml(person.email)}${person.student_id ? ` · ${escapeHtml(person.student_id)}` : ''}</small></div></div></td>
            <td><span class="role-badge role-${person.role}">${escapeHtml(ROLE_LABEL[person.role])}</span></td>
            <td>${escapeHtml(person.hostel_name || person.department || '—')}${person.room_number ? `<span class="cell-sub">Room ${escapeHtml(person.room_number)}</span>` : ''}</td>
            <td>${person.role === 'student' ? `${person.reports_count} reports` : person.role === 'staff' ? `${person.active_load} active jobs` : 'System access'}</td>
            <td><span class="badge ${person.is_active ? 'status-resolved' : 'status-closed'}">${person.is_active ? 'Active' : 'Inactive'}</span></td>
            <td><button class="btn btn-sm btn-ghost" data-action="edit-user" data-id="${person.id}">${icon('edit')} Edit</button></td>
          </tr>`).join('')}</tbody>
      </table></div>` : emptyState({ title: 'No people found', text: 'Try a different search term or role filter.', iconName: 'users' })}
    </section>`;
}

/* ==========================================================================
   Hostels (admin)
   ========================================================================== */
export function renderHostels({ hostels, facilities }) {
  return `
    ${pageHead({
      kicker: 'Hostel portfolio',
      kickerIcon: 'building',
      title: 'Hostels & facilities.',
      subtitle: 'Keep the physical register current. Facility conditions help the maintenance team plan preventive work.',
      actions: `<button class="btn btn-primary" data-action="new-hostel">${icon('plus')} Add hostel</button>`,
    })}
    ${hostels.length ? `<div class="hostel-grid">${hostels.map((hostel) => {
      const hostelFacilities = facilities.filter((facility) => facility.hostel_id === hostel.id);
      return `
        <section class="panel hostel-card">
          <div class="hostel-card-head">
            <span class="hostel-code">${escapeHtml(hostel.code)}</span>
            <h3>${escapeHtml(hostel.name)}</h3>
            <p>${icon('pin')}${escapeHtml(hostel.address || 'Campus residence')}</p>
            <div class="hostel-head-stats">
              <div><strong>${hostel.total_rooms}</strong><span>Rooms</span></div>
              <div><strong>${hostelFacilities.length}</strong><span>Facilities</span></div>
              <div><strong>${escapeHtml(hostel.gender)}</strong><span>Residents</span></div>
            </div>
          </div>
          <div class="hostel-card-body">
            <div class="hostel-detail-line">${icon('user')} Warden: <strong style="color:var(--ink-soft)">${escapeHtml(hostel.warden_name || 'Not assigned')}</strong></div>
            <div class="hostel-detail-line">${icon('bell')} ${escapeHtml(hostel.warden_phone || 'No contact number')}</div>
            <div class="hostel-facilities">
              <div class="facility-title"><span>Facility register</span><button class="btn-link" data-action="new-facility" data-hostel="${hostel.id}">${icon('plus')} Add</button></div>
              ${hostelFacilities.length ? hostelFacilities.map((facility) => `
                <div class="facility-row">
                  <span class="facility-name">${escapeHtml(facility.name)}</span>
                  ${conditionBadge(facility.condition)}
                  <button class="icon-btn" style="width:24px;height:24px" data-action="edit-facility" data-id="${facility.id}" aria-label="Edit ${escapeHtml(facility.name)}">${icon('edit')}</button>
                </div>`).join('') : `<p style="font-size:9px;color:var(--muted-2);padding:4px 0">No facilities registered yet.</p>`}
            </div>
            <div style="display:flex;gap:6px;margin-top:13px">
              <button class="btn btn-sm btn-ghost" data-action="edit-hostel" data-id="${hostel.id}">${icon('edit')} Edit hostel</button>
              <button class="btn btn-sm btn-soft" data-action="new-facility" data-hostel="${hostel.id}">${icon('plus')} Facility</button>
            </div>
          </div>
        </section>`;
    }).join('')}</div>` : emptyState({ title: 'No hostels registered', text: 'Add the first hostel to begin managing facilities.', iconName: 'building' })}
  `;
}

/* ==========================================================================
   Announcements
   ========================================================================== */
export function renderAnnouncements(items) {
  return `
    ${pageHead({
      kicker: 'Resident communications',
      kickerIcon: 'megaphone',
      title: 'Announcements.',
      subtitle: 'Publish maintenance notices to all residents, students or the maintenance team.',
      actions: `<button class="btn btn-primary" data-action="new-announcement">${icon('plus')} New announcement</button>`,
    })}
    ${items.length ? `<div class="announcement-grid">${items.map((item) => `
      <article class="panel announcement-card">
        <div class="ann-top">
          <span class="audience-badge ${item.audience}">${escapeHtml(AUDIENCE_LABEL[item.audience] || item.audience)}</span>
          ${item.is_pinned ? `<span class="chip">${icon('star')} Pinned</span>` : ''}
        </div>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.body)}</p>
        <div class="ann-foot">${icon('calendar')} ${formatDate(item.created_at)} <span class="report-meta-dot"></span> ${escapeHtml(item.author_name || 'Facilities office')}
          <button class="icon-btn" style="width:29px;height:29px" data-action="delete-announcement" data-id="${item.id}" title="Delete announcement" aria-label="Delete announcement">${icon('trash')}</button>
        </div>
      </article>`).join('')}</div>` : emptyState({
        title: 'No announcements yet',
        text: 'Publish a notice to keep residents informed about maintenance, supply interruptions or new procedures.',
        action: `<button class="btn btn-primary btn-sm" data-action="new-announcement">${icon('plus')} Create announcement</button>`,
        iconName: 'megaphone',
      })}
  `;
}

/* ==========================================================================
   Report detail drawer
   ========================================================================== */
export function renderReportDrawer(report, meta, user) {
  const capabilities = report.capabilities || {};
  const updates = report.updates || [];
  const staffOptions = meta.staff || [];
  const isStudent = user.role === 'student';
  const isResolved = ['resolved', 'closed'].includes(report.status);
  return `
    <aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
      <div class="drawer-head">
        <div class="drawer-topline">
          <span class="mono">${escapeHtml(report.ref)}</span>
          ${statusBadge(report.status)}
          ${priorityLabel(report.priority)}
          <button class="icon-btn" data-action="close-drawer" aria-label="Close report">${icon('x')}</button>
        </div>
        <h2 id="drawer-title">${escapeHtml(report.title)}</h2>
        <div class="drawer-head-meta">
          ${icon('pin')} ${escapeHtml(report.hostel?.name || report.hostel_name)} <span class="report-meta-dot"></span> ${escapeHtml(report.location)}
          <span class="report-meta-dot"></span> ${timeAgo(report.created_at)}
        </div>
      </div>
      <div class="drawer-scroll">
        <section class="detail-card">
          <div class="detail-card-title">${icon('info')} Report details</div>
          <p class="detail-description">${escapeHtml(report.description)}</p>
          ${report.photo ? `<div class="detail-photo"><img src="${report.photo}" alt="Photo attached to report ${escapeHtml(report.ref)}"></div>` : ''}
          <div class="sla-line ${report.is_overdue ? 'overdue' : ''}">
            ${icon(report.is_overdue ? 'alert' : 'clock')}
            ${report.is_overdue ? `Past the ${escapeHtml(report.priority)} priority response target` : dueLabel(report)}
            <span style="margin-left:auto">Target: ${formatDateTime(report.sla_due_at)}</span>
          </div>
        </section>

        <section class="detail-card">
          <div class="detail-card-title">${icon('clipboard')} Report information</div>
          <div class="detail-grid">
            <div class="detail-item"><small>Hostel</small><strong>${escapeHtml(report.hostel?.name || report.hostel_name)}</strong><span>${escapeHtml(report.hostel?.code || '')}</span></div>
            <div class="detail-item"><small>Category</small><strong>${escapeHtml(report.category)}</strong><span>Facility fault</span></div>
            <div class="detail-item"><small>Reported by</small><strong>${escapeHtml(report.student?.full_name || 'Student')}</strong><span>${escapeHtml(report.student?.student_id || '')}${report.student?.room_number ? ` · Room ${escapeHtml(report.student.room_number)}` : ''}</span></div>
            <div class="detail-item"><small>Assigned to</small><strong>${escapeHtml(report.staff?.full_name || 'Not yet assigned')}</strong><span>${escapeHtml(report.staff?.email || 'Awaiting triage')}</span></div>
            <div class="detail-item"><small>Submitted</small><strong>${formatDate(report.created_at)}</strong><span>${formatDateTime(report.created_at)}</span></div>
            <div class="detail-item"><small>Last updated</small><strong>${timeAgo(report.updated_at)}</strong><span>${formatDateTime(report.updated_at)}</span></div>
          </div>
          ${report.resolution_note ? `<div class="resolution-box"><strong>${icon('check')} Resolution note</strong><p>${escapeHtml(report.resolution_note)}</p></div>` : ''}
          ${report.rating ? `<div class="resolution-box" style="background:var(--accent-soft);border-color:#f0d7b7"><strong style="color:var(--accent-deep)">${icon('star')} Resident feedback</strong><div style="margin:2px 0 4px">${stars(report.rating)}</div>${report.feedback ? `<p style="color:#7a5730">${escapeHtml(report.feedback)}</p>` : ''}</div>` : ''}
        </section>

        ${capabilities.can_feedback ? feedbackCard(report) : ''}

        <section class="detail-card">
          <div class="detail-card-title">${icon('message')} Activity & comments</div>
          <div class="timeline">
            ${updates.map((update) => timelineItem(update)).join('')}
          </div>
          ${capabilities.can_comment ? commentForm(report, user) : ''}
        </section>
      </div>
      ${drawerFooter(report, meta, user, capabilities, staffOptions, isStudent, isResolved)}
    </aside>`;
}

function timelineItem(update) {
  return `
    <div class="timeline-item">
      <span class="timeline-dot ${escapeHtml(update.action)}"></span>
      <div class="timeline-body">
        <div class="timeline-top">
          <strong>${escapeHtml(ACTION_LABEL[update.action] || update.action)} ${update.is_internal ? '<span class="internal-pill">Internal</span>' : ''}</strong>
          <time>${timeAgo(update.created_at)}</time>
        </div>
        ${update.note ? `<div class="timeline-note">${escapeHtml(update.note)}</div>` : ''}
        <div class="timeline-author">${escapeHtml(update.author_name || 'System')}${update.author_role ? ` · ${escapeHtml(ROLE_LABEL[update.author_role] || update.author_role)}` : ''}</div>
      </div>
    </div>`;
}

function feedbackCard(report) {
  return `
    <section class="detail-card" style="border-color:#f0d7b7;background:#fffdf8">
      <div class="detail-card-title" style="color:var(--accent-deep)">${icon('star')} Rate the repair</div>
      <p style="font-size:10.5px;color:var(--muted);margin-bottom:10px">How well was this issue handled? Your rating helps the facilities desk improve response quality.</p>
      <form data-form="feedback" data-id="${report.id}">
        <input type="hidden" name="rating" id="feedback-rating" value="">
        <div class="feedback-stars" role="group" aria-label="Service rating">
          ${[1, 2, 3, 4, 5].map((value) => `<button class="star-btn" type="button" data-action="set-rating" data-value="${value}" aria-label="${value} star${value > 1 ? 's' : ''}">${icon('star')}</button>`).join('')}
        </div>
        <div class="field" style="margin-top:10px"><label for="feedback-text">Comment <span style="font-weight:400;color:var(--muted-2)">(optional)</span></label><textarea class="textarea" id="feedback-text" name="feedback" maxlength="1000" placeholder="Tell us what went well or what could be better…"></textarea></div>
        <button class="btn btn-accent btn-sm" type="submit" style="margin-top:9px">${icon('star')} Submit rating</button>
      </form>
    </section>`;
}

function commentForm(report, user) {
  return `
    <form class="comment-box" data-form="comment" data-id="${report.id}" style="margin-top:14px;padding-top:13px;border-top:1px solid var(--line)">
      <textarea class="textarea" name="note" maxlength="2000" placeholder="Add a comment or update for everyone following this report…" aria-label="Comment" required></textarea>
      <div class="comment-actions">
        ${user.role !== 'student' ? `<label class="checkbox-line" style="font-size:9px"><input type="checkbox" name="internal"> Internal note</label>` : '<span class="comment-hint">Visible to the facilities team</span>'}
        <button class="btn btn-primary btn-sm" type="submit">${icon('send')} Post comment</button>
      </div>
    </form>`;
}

function drawerFooter(report, meta, user, capabilities, staffOptions, isStudent, isResolved) {
  const parts = [];
  if (user.role === 'admin' && capabilities.can_assign) {
    parts.push(`
      <div class="assign-row">
        <select class="select" id="assign-staff" aria-label="Assign to staff">
          ${selectOptions((staffOptions || []).map((staff) => ({ value: staff.id, label: `${staff.full_name}${staff.active_load ? ` (${staff.active_load} active)` : ''}` })), report.assigned_to, 'Assign a maintenance officer…')}
        </select>
        <button class="btn btn-soft btn-sm" data-action="assign-report" data-id="${report.id}">${icon('user')} Assign</button>
      </div>`);
  }
  if (capabilities.can_start) {
    parts.push(`<button class="btn btn-primary btn-sm" data-action="start-report" data-id="${report.id}">${icon('wrench')} Start work</button>`);
  }
  if (capabilities.can_resolve) {
    parts.push(`<button class="btn ${capabilities.can_start ? 'btn-ghost' : 'btn-primary'} btn-sm" data-action="resolve-report" data-id="${report.id}">${icon('check')} Mark resolved</button>`);
  }
  if (capabilities.can_close) {
    parts.push(`<button class="btn btn-ghost btn-sm" data-action="close-report" data-id="${report.id}">${icon('check')} Close report</button>`);
  }
  if (capabilities.can_reopen) {
    parts.push(`<button class="btn btn-danger btn-sm" data-action="reopen-report" data-id="${report.id}">${icon('refresh')} Reopen</button>`);
  }
  if (isStudent && isResolved && report.rating) {
    parts.push(`<span style="font-size:9px;color:var(--muted);margin-left:auto">${icon('star')} You rated this repair ${report.rating}/5</span>`);
  }
  if (!parts.length) return '';
  return `<div class="drawer-foot">${parts.join('')}</div>`;
}

/* ==========================================================================
   Modal forms
   ========================================================================== */
export function openReportForm(state) {
  const { meta, user } = state;
  const defaultHostel = user.hostel_id || meta.hostels[0]?.id || '';
  const body = `
    <form id="report-form" data-form="report" class="form-grid-modal" novalidate>
      <div class="field">
        <label for="report-hostel">Hostel <span class="req">*</span></label>
        <select class="select" id="report-hostel" name="hostel_id" required>
          ${selectOptions(meta.hostels.map((h) => ({ value: h.id, label: `${h.name} (${h.code})` })), defaultHostel, 'Choose hostel')}
        </select>
      </div>
      <div class="field">
        <label for="report-facility">Facility <span style="font-weight:400;color:var(--muted-2)">(optional)</span></label>
        <select class="select" id="report-facility" name="facility_id">
          <option value="">Not sure / other</option>
          ${meta.facilities.map((f) => `<option value="${f.id}" data-hostel="${f.hostel_id}" ${String(f.hostel_id) === String(defaultHostel) ? '' : 'hidden'}>${escapeHtml(f.name)} — ${escapeHtml(f.location || f.category)}</option>`).join('')}
        </select>
      </div>
      <div class="field">
        <label for="report-category">Category <span class="req">*</span></label>
        <select class="select" id="report-category" name="category" required>
          ${selectOptions(meta.categories, '', 'Choose a category')}
        </select>
      </div>
      <div class="field">
        <label for="report-priority">Priority <span class="req">*</span></label>
        <select class="select" id="report-priority" name="priority">
          ${selectOptions(meta.priorities, 'medium')}
        </select>
        <span class="field-hint">Urgent: safety risk or total loss of service.</span>
      </div>
      <div class="field span-2">
        <label for="report-location">Exact location <span class="req">*</span></label>
        <input class="input" id="report-location" name="location" placeholder="e.g. Room 204, second floor bathroom" maxlength="120" required>
      </div>
      <div class="field span-2">
        <label for="report-title">Short title <span class="req">*</span></label>
        <input class="input" id="report-title" name="title" placeholder="e.g. Bathroom pipe leaking into the corridor" maxlength="120" required>
      </div>
      <div class="field span-2">
        <label for="report-description">What is wrong? <span class="req">*</span></label>
        <textarea class="textarea" id="report-description" name="description" maxlength="4000" placeholder="Describe the fault, how long it has been happening and anything the maintenance team should know…" rows="4" required></textarea>
        <span class="field-hint">At least 15 characters. Clear details help us fix it faster.</span>
      </div>
      <div class="field span-2">
        <label>Photo evidence <span style="font-weight:400;color:var(--muted-2)">(optional, max 2 MB)</span></label>
        <input type="hidden" name="photo" id="report-photo">
        <label class="upload-zone" id="upload-zone" for="report-photo-file">
          ${icon('camera')}
          <strong>Click to upload or drag an image here</strong>
          <span>PNG, JPEG or WebP · up to 2 MB</span>
        </label>
        <input type="file" id="report-photo-file" accept="image/png,image/jpeg,image/webp" hidden>
        <div id="photo-preview"></div>
      </div>
    </form>`;
  const modal = openModal({
    title: 'Report a facility issue',
    subtitle: 'Give the maintenance team enough detail to act on the first visit.',
    body,
    size: 'modal-wide',
    footer: `<span class="danger-note" id="report-required-note">Fields marked * are required</span>
             <button class="btn btn-ghost" data-action="close-modal">Cancel</button>
             <button class="btn btn-primary" type="submit" form="report-form">${icon('send')} Submit report</button>`,
  });

  const hostelSelect = modal.querySelector('#report-hostel');
  const facilitySelect = modal.querySelector('#report-facility');
  const filterFacilities = () => {
    const hostelId = hostelSelect.value;
    [...facilitySelect.options].forEach((option) => {
      if (!option.value) return;
      option.hidden = option.dataset.hostel !== hostelId;
    });
    if (facilitySelect.selectedOptions[0]?.hidden) facilitySelect.value = '';
  };
  hostelSelect.addEventListener('change', filterFacilities);
  filterFacilities();

  const fileInput = modal.querySelector('#report-photo-file');
  const photoInput = modal.querySelector('#report-photo');
  const preview = modal.querySelector('#photo-preview');
  const zone = modal.querySelector('#upload-zone');
  const showPreview = (dataUrl) => {
    preview.innerHTML = `<div class="photo-preview" style="margin-top:10px"><img src="${dataUrl}" alt="Selected photo preview"><button type="button" class="photo-remove" data-action="remove-photo" aria-label="Remove photo">${icon('x')}</button></div>`;
    zone.classList.add('hidden');
  };
  const handleFile = async (file) => {
    if (!file) return;
    try {
      const dataUrl = await readFileAsDataUrl(file);
      photoInput.value = dataUrl;
      showPreview(dataUrl);
    } catch (error) {
      toast('Photo not added', error.message, 'error');
    }
  };
  fileInput.addEventListener('change', () => handleFile(fileInput.files?.[0]));
  zone.addEventListener('dragover', (event) => { event.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', (event) => {
    event.preventDefault();
    zone.classList.remove('dragover');
    handleFile(event.dataTransfer.files?.[0]);
  });
  modal.addEventListener('click', (event) => {
    if (event.target.closest('[data-action="remove-photo"]')) {
      photoInput.value = '';
      preview.innerHTML = '';
      zone.classList.remove('hidden');
      fileInput.value = '';
    }
  });
}

export function openUserForm(state, person = null) {
  const editing = Boolean(person);
  const hostels = state.meta.hostels;
  const body = `
    <form id="user-form" data-form="${editing ? 'edit-user' : 'create-user'}" data-id="${person?.id || ''}" class="form-grid-modal" novalidate>
      <div class="field span-2">
        <label for="user-name">Full name <span class="req">*</span></label>
        <input class="input" id="user-name" name="full_name" value="${escapeHtml(person?.full_name || '')}" placeholder="e.g. Grace Okafor" required>
      </div>
      <div class="field span-2">
        <label for="user-email">Email address <span class="req">*</span></label>
        <input class="input" type="email" id="user-email" name="email" value="${escapeHtml(person?.email || '')}" placeholder="name@hostelhub.edu.ng" ${editing ? 'readonly style="background:var(--surface-soft);color:var(--muted)"' : 'required'}>
      </div>
      <div class="field">
        <label for="user-role">Role <span class="req">*</span></label>
        <select class="select" id="user-role" name="role">${selectOptions([
          { value: 'student', label: 'Student' },
          { value: 'staff', label: 'Maintenance staff' },
          { value: 'admin', label: 'Administrator' },
        ], person?.role || 'student')}</select>
      </div>
      <div class="field">
        <label for="user-matric">Matric number <span style="font-weight:400;color:var(--muted-2)">(students)</span></label>
        <input class="input" id="user-matric" name="student_id" value="${escapeHtml(person?.student_id || '')}" placeholder="NSUK/CSC/21/041">
      </div>
      <div class="field">
        <label for="user-phone">Phone</label>
        <input class="input" id="user-phone" name="phone" value="${escapeHtml(person?.phone || '')}" placeholder="0803 000 0000">
      </div>
      <div class="field">
        <label for="user-dept">Department / unit</label>
        <input class="input" id="user-dept" name="department" value="${escapeHtml(person?.department || '')}" placeholder="e.g. Computer Science">
      </div>
      <div class="field">
        <label for="user-hostel">Hostel</label>
        <select class="select" id="user-hostel" name="hostel_id">${selectOptions(hostels.map((h) => ({ value: h.id, label: `${h.name} (${h.code})` })), person?.hostel_id || '', 'Not assigned')}</select>
      </div>
      <div class="field">
        <label for="user-room">Room number</label>
        <input class="input" id="user-room" name="room_number" value="${escapeHtml(person?.room_number || '')}" placeholder="e.g. 204">
      </div>
      <div class="field span-2">
        <label for="user-password">${editing ? 'Reset password' : 'Temporary password'} ${editing ? '' : '<span class="req">*</span>'}</label>
        <input class="input" type="password" id="user-password" name="password" placeholder="${editing ? 'Leave blank to keep the current password' : 'At least 8 characters'}" minlength="8" ${editing ? '' : 'required'}>
      </div>
      ${editing ? `<label class="checkbox-line span-2"><input type="checkbox" name="is_active" ${person.is_active ? 'checked' : ''}> Account is active and can sign in</label>` : ''}
    </form>`;
  openModal({
    title: editing ? 'Edit person' : 'Add a person',
    subtitle: editing ? 'Update role, hall details or reset access.' : 'Create an account for a student, maintenance officer or administrator.',
    body,
    size: 'modal-wide',
    footer: `<button class="btn btn-ghost" data-action="close-modal">Cancel</button>
             <button class="btn btn-primary" type="submit" form="user-form">${editing ? 'Save changes' : 'Create account'}</button>`,
  });
}

export function openHostelForm(hostel = null) {
  const editing = Boolean(hostel);
  openModal({
    title: editing ? 'Edit hostel' : 'Add a hostel',
    subtitle: 'Hostel records feed the reporting form and portfolio analytics.',
    body: `
      <form id="hostel-form" data-form="${editing ? 'edit-hostel' : 'create-hostel'}" data-id="${hostel?.id || ''}" class="form-grid-modal" novalidate>
        <div class="field span-2"><label for="hostel-name">Hostel name <span class="req">*</span></label><input class="input" id="hostel-name" name="name" value="${escapeHtml(hostel?.name || '')}" placeholder="e.g. New Block A" required></div>
        <div class="field"><label for="hostel-code">Short code <span class="req">*</span></label><input class="input" id="hostel-code" name="code" value="${escapeHtml(hostel?.code || '')}" placeholder="NBA" maxlength="12" required></div>
        <div class="field"><label for="hostel-gender">Resident type</label><select class="select" id="hostel-gender" name="gender">${selectOptions(['Male', 'Female', 'Mixed'], hostel?.gender || 'Mixed')}</select></div>
        <div class="field"><label for="hostel-rooms">Total rooms</label><input class="input" type="number" id="hostel-rooms" name="total_rooms" value="${hostel?.total_rooms ?? 0}" min="0" max="5000"></div>
        <div class="field"><label for="hostel-warden">Warden name</label><input class="input" id="hostel-warden" name="warden_name" value="${escapeHtml(hostel?.warden_name || '')}" placeholder="e.g. Mrs. Rebecca Atabo"></div>
        <div class="field"><label for="hostel-phone">Warden phone</label><input class="input" id="hostel-phone" name="warden_phone" value="${escapeHtml(hostel?.warden_phone || '')}" placeholder="0803 000 0000"></div>
        <div class="field span-2"><label for="hostel-address">Address on campus</label><input class="input" id="hostel-address" name="address" value="${escapeHtml(hostel?.address || '')}" placeholder="e.g. North Campus, beside Faculty of Science"></div>
      </form>`,
    size: 'modal-wide',
    footer: `<button class="btn btn-ghost" data-action="close-modal">Cancel</button><button class="btn btn-primary" type="submit" form="hostel-form">${editing ? 'Save hostel' : 'Create hostel'}</button>`,
  });
}

export function openFacilityForm(meta, facility = null, hostelId = '') {
  const editing = Boolean(facility);
  openModal({
    title: editing ? 'Edit facility' : 'Add a facility',
    subtitle: 'Register fixed assets so reports can point to the exact item.',
    body: `
      <form id="facility-form" data-form="${editing ? 'edit-facility' : 'create-facility'}" data-id="${facility?.id || ''}" class="form-grid-modal" novalidate>
        <div class="field span-2"><label for="facility-hostel">Hostel <span class="req">*</span></label><select class="select" id="facility-hostel" name="hostel_id" ${editing ? 'disabled' : ''}>${selectOptions(meta.hostels.map((h) => ({ value: h.id, label: `${h.name} (${h.code})` })), facility?.hostel_id || hostelId, 'Choose hostel')}</select></div>
        <div class="field span-2"><label for="facility-name">Facility name <span class="req">*</span></label><input class="input" id="facility-name" name="name" value="${escapeHtml(facility?.name || '')}" placeholder="e.g. Bathroom water heater" required></div>
        <div class="field"><label for="facility-category">Category</label><select class="select" id="facility-category" name="category">${selectOptions(meta.categories, facility?.category || '', 'Choose category')}</select></div>
        <div class="field"><label for="facility-condition">Condition</label><select class="select" id="facility-condition" name="condition">${selectOptions(['Good', 'Fair', 'Poor', 'Under repair'], facility?.condition || 'Good')}</select></div>
        <div class="field span-2"><label for="facility-location">Location</label><input class="input" id="facility-location" name="location" value="${escapeHtml(facility?.location || '')}" placeholder="e.g. Second floor, west wing"></div>
      </form>`,
    footer: `<button class="btn btn-ghost" data-action="close-modal">Cancel</button><button class="btn btn-primary" type="submit" form="facility-form">${editing ? 'Save facility' : 'Add facility'}</button>`,
  });
}

export function openAnnouncementForm() {
  openModal({
    title: 'Publish an announcement',
    subtitle: 'Keep residents and the maintenance team informed.',
    body: `
      <form id="announcement-form" data-form="announcement" class="form-grid-modal" novalidate>
        <div class="field span-2"><label for="ann-title">Title <span class="req">*</span></label><input class="input" id="ann-title" name="title" placeholder="e.g. Water supply maintenance this Saturday" maxlength="120" required></div>
        <div class="field"><label for="ann-audience">Audience</label><select class="select" id="ann-audience" name="audience">${selectOptions([{ value: 'all', label: 'Everyone' }, { value: 'students', label: 'Students' }, { value: 'staff', label: 'Maintenance staff' }, { value: 'admin', label: 'Administrators' }], 'all')}</select></div>
        <div class="field" style="justify-content:flex-end"><label class="checkbox-line"><input type="checkbox" name="is_pinned"> Pin to the top</label></div>
        <div class="field span-2"><label for="ann-body">Message <span class="req">*</span></label><textarea class="textarea" id="ann-body" name="body" rows="5" maxlength="3000" placeholder="Include dates, times and what residents need to do…" required></textarea></div>
      </form>`,
    size: 'modal-wide',
    footer: `<button class="btn btn-ghost" data-action="close-modal">Cancel</button><button class="btn btn-primary" type="submit" form="announcement-form">${icon('megaphone')} Publish</button>`,
  });
}

export function openResolveForm(report) {
  openModal({
    title: 'Mark report resolved',
    subtitle: `${report.ref} · ${report.title}`,
    body: `
      <form id="resolve-form" data-form="resolve" data-id="${report.id}">
        <div class="field">
          <label for="resolve-note">Resolution note <span class="req">*</span></label>
          <textarea class="textarea" id="resolve-note" name="note" rows="5" maxlength="2000" placeholder="What was the fault, what did you do, and what should the resident check?" required></textarea>
          <span class="field-hint">The resident and facilities desk will see this note. At least 10 characters.</span>
        </div>
      </form>`,
    footer: `<button class="btn btn-ghost" data-action="close-modal">Cancel</button><button class="btn btn-primary" type="submit" form="resolve-form">${icon('check')} Confirm resolution</button>`,
  });
}

export function openReopenForm(report) {
  openModal({
    title: 'Reopen this report',
    subtitle: 'Tell the maintenance team what is still wrong.',
    body: `
      <form id="reopen-form" data-form="reopen" data-id="${report.id}">
        <div class="field">
          <label for="reopen-note">Why are you reopening it? <span class="req">*</span></label>
          <textarea class="textarea" id="reopen-note" name="note" rows="5" maxlength="2000" placeholder="Explain what happened after the repair and what is still faulty…" required></textarea>
          <span class="field-hint">At least 5 characters. The report returns to the maintenance queue.</span>
        </div>
      </form>`,
    footer: `<button class="btn btn-ghost" data-action="close-modal">Cancel</button><button class="btn btn-danger" type="submit" form="reopen-form">${icon('refresh')} Reopen report</button>`,
  });
}
