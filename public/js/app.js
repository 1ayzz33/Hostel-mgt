import { api, ApiError, loadSession } from './api.js';
import {
  $,
  avatar,
  buttonBusy,
  closeDrawer,
  closeModal,
  confirmDialog,
  debounce,
  escapeHtml,
  icon,
  openDrawer,
  openModal,
  toast,
} from './ui.js';
import {
  openAnnouncementForm,
  openFacilityForm,
  openHostelForm,
  openReportForm,
  openReopenForm,
  openResolveForm,
  openUserForm,
  renderAnnouncements,
  renderAuth,
  renderDashboard,
  renderHostels,
  renderMobileNav,
  renderNav,
  renderNotifications,
  renderReportDrawer,
  renderReports,
  renderSidebarNote,
  renderSidebarUser,
  renderUsers,
} from './views.js';

const VIEW_TITLES = {
  dashboard: 'Dashboard',
  reports: 'Reports',
  notifications: 'Notifications',
  users: 'People',
  hostels: 'Hostels',
  announcements: 'Announcements',
};

const state = {
  user: null,
  meta: null,
  publicHostels: [],
  authMode: 'login',
  view: 'dashboard',
  unread: 0,
  dashboard: null,
  analytics: null,
  reports: { items: [], total: 0 },
  filters: { q: '', status: '', priority: '', category: '', hostel_id: '', overdue: false },
  notifications: { items: [], unread: 0 },
  users: [],
  userFilters: { q: '', role: '' },
  hostels: [],
  facilities: [],
  announcements: [],
  activeReport: null,
  renderSeq: 0,
  booted: false,
};

const isAdmin = () => state.user?.role === 'admin';
const isStaff = () => state.user?.role === 'staff';
const isStudent = () => state.user?.role === 'student';

/* ==========================================================================
   Boot and authentication
   ========================================================================== */
async function boot() {
  try {
    const [user, hostels] = await Promise.all([
      loadSession(),
      api.get('/auth/hostels').catch(() => ({ items: [] })),
    ]);
    state.publicHostels = hostels.items || [];
    if (user) {
      await enterApp(user);
    } else {
      showAuth('login');
    }
  } catch (error) {
    showAuth('login');
    toast('Could not load HostelHub', error.message || 'Check the server and refresh.', 'error');
  } finally {
    hideBoot();
  }
}

function hideBoot() {
  const bootScreen = $('#boot-screen');
  if (!bootScreen) return;
  bootScreen.classList.add('is-leaving');
  setTimeout(() => bootScreen.classList.add('hidden'), 380);
}

function showAuth(mode = 'login') {
  state.user = null;
  state.authMode = mode;
  state.meta = null;
  closeDrawer();
  closeModal();
  $('#app-shell').classList.add('hidden');
  $('#auth-screen').classList.remove('hidden');
  document.body.classList.remove('app-open');
  renderAuthView();
  document.title = 'Sign in · HostelHub';
  window.scrollTo(0, 0);
}

function renderAuthView() {
  $('#auth-view').innerHTML = renderAuth(state.authMode, state.publicHostels);
  $('#auth-switch').innerHTML = state.authMode === 'login'
    ? `New to HostelHub? <button type="button" data-action="auth-mode" data-mode="register">Create a student account</button>`
    : `Already have an account? <button type="button" data-action="auth-mode" data-mode="login">Sign in</button>`;
}

function showAuthError(message) {
  const box = $('#auth-error');
  if (!box) return;
  box.classList.remove('hidden');
  box.innerHTML = `${icon('alert')}<span>${escapeHtml(message)}</span>`;
}

async function enterApp(user) {
  state.user = user;
  state.meta = await api.get('/meta');
  state.booted = true;
  $('#auth-screen').classList.add('hidden');
  $('#app-shell').classList.remove('hidden');
  document.body.classList.add('app-open');
  renderChrome();
  const requested = viewFromHash();
  const initial = canAccess(requested) ? requested : 'dashboard';
  if (location.hash !== `#/${initial}`) history.replaceState(null, '', `#/${initial}`);
  await showView(initial);
}

function canAccess(view) {
  if (!state.user) return false;
  if (state.user.role !== 'admin' && ['users', 'hostels', 'announcements'].includes(view)) return false;
  return Object.hasOwn(VIEW_TITLES, view);
}

function viewFromHash() {
  const raw = location.hash.replace(/^#\/?/, '').split('?')[0];
  return VIEW_TITLES[raw] ? raw : 'dashboard';
}

/* ==========================================================================
   Chrome (sidebar, topbar, navigation)
   ========================================================================== */
function renderChrome() {
  if (!state.user) return;
  $('#main-nav').innerHTML = renderNav(state.user, state.unread, state.view);
  $('#mobile-nav').innerHTML = renderMobileNav(state.user, state.unread, state.view);
  $('#sidebar-user').innerHTML = renderSidebarUser(state.user);
  $('#sidebar-note').innerHTML = renderSidebarNote(state.user);
  $('#topbar-user').innerHTML = avatar(state.user);
  const dot = $('#notification-dot');
  dot.classList.toggle('hidden', state.unread === 0);
  $('#page-crumb').innerHTML = `<span>${escapeHtml(roleWorkspace())}</span>${icon('chevron')}<strong>${escapeHtml(VIEW_TITLES[state.view] || 'Dashboard')}</strong>`;
  document.title = `${VIEW_TITLES[state.view] || 'Dashboard'} · HostelHub`;
}

function roleWorkspace() {
  if (isAdmin()) return 'Facilities office';
  if (isStaff()) return 'Maintenance';
  return 'Resident';
}

function updateUnread(count) {
  state.unread = Math.max(0, Number(count) || 0);
  renderChrome();
}

function closeSidebar() {
  $('#sidebar')?.classList.remove('open');
  $('#sidebar-scrim')?.classList.remove('open');
}

/* ==========================================================================
   Routing and data loading
   ========================================================================== */
async function navigate(view, { push = true } = {}) {
  if (!state.user) return;
  if (!canAccess(view)) view = 'dashboard';
  closeSidebar();
  closePopover();
  if (push && location.hash !== `#/${view}`) {
    history.pushState(null, '', `#/${view}`);
  }
  await showView(view);
}

async function showView(view, { silent = false } = {}) {
  if (!state.user) return;
  state.view = view;
  renderChrome();
  window.scrollTo({ top: 0, behavior: silent ? 'auto' : 'smooth' });
  if (!silent) showSkeleton();
  await loadView(view, { silent });
}

async function loadView(view, { silent = false } = {}) {
  const seq = ++state.renderSeq;
  try {
    let html = '';
    if (view === 'dashboard') {
      const [dashboard, analytics] = await Promise.all([
        api.get('/dashboard'),
        isAdmin() ? api.get('/analytics') : Promise.resolve(null),
      ]);
      if (seq !== state.renderSeq) return;
      state.dashboard = dashboard;
      state.analytics = analytics;
      updateUnread(dashboard.unread_notifications || 0);
      html = renderDashboard({ data: dashboard, analytics, meta: state.meta, user: state.user });
    } else if (view === 'reports') {
      const data = await api.get('/reports', state.filters);
      if (seq !== state.renderSeq) return;
      state.reports = data;
      html = renderReports({ data, meta: state.meta, user: state.user, filters: state.filters });
    } else if (view === 'notifications') {
      const data = await api.get('/notifications');
      if (seq !== state.renderSeq) return;
      state.notifications = data;
      updateUnread(data.unread || 0);
      html = renderNotifications(data);
    } else if (view === 'users') {
      const data = await api.get('/api/admin/users', state.userFilters);
      if (seq !== state.renderSeq) return;
      state.users = data.items || [];
      html = renderUsers({ users: state.users, filters: state.userFilters });
    } else if (view === 'hostels') {
      const [hostels, facilities] = await Promise.all([
        api.get('/api/admin/hostels'),
        api.get('/api/admin/facilities'),
      ]);
      if (seq !== state.renderSeq) return;
      state.hostels = hostels.items || [];
      state.facilities = facilities.items || [];
      html = renderHostels({ hostels: state.hostels, facilities: state.facilities });
    } else if (view === 'announcements') {
      const data = await api.get('/api/announcements');
      if (seq !== state.renderSeq) return;
      state.announcements = data.items || [];
      html = renderAnnouncements(state.announcements);
    }
    if (seq !== state.renderSeq) return;
    $('#main-content').innerHTML = html;
    $('#main-content').focus({ preventScroll: true });
  } catch (error) {
    if (seq !== state.renderSeq) return;
    if (error instanceof ApiError && error.status === 401) {
      signOutLocal('Your session has expired. Please sign in again.');
      return;
    }
    if (silent) {
      toast('Could not refresh', error.message, 'error');
    } else {
      renderLoadError(error);
    }
  }
}

async function refreshSilent() {
  await loadView(state.view, { silent: true });
}

function showSkeleton() {
  $('#main-content').innerHTML = `
    <div class="page-loading">
      <div class="skeleton" style="height:22px;width:180px"></div>
      <div class="skeleton" style="height:38px;width:330px;max-width:70%"></div>
      <div class="skeleton-stats">
        ${Array.from({ length: 4 }, () => '<div class="skeleton skeleton-stat"></div>').join('')}
      </div>
      <div class="skeleton skeleton-block"></div>
    </div>`;
}

function renderLoadError(error) {
  $('#main-content').innerHTML = `
    <div class="panel" style="max-width:560px;margin:6vh auto">
      <div class="empty-state">
        <div class="empty-icon">${icon('alert')}</div>
        <h3>We could not load this page</h3>
        <p>${escapeHtml(error.message || 'The server did not respond. Check that HostelHub is running.')}</p>
        <button class="btn btn-primary btn-sm" data-action="refresh">${icon('refresh')} Try again</button>
      </div>
    </div>`;
}

/* ==========================================================================
   Report detail
   ========================================================================== */
async function openReport(id) {
  try {
    const report = await api.get(`/reports/${id}`);
    state.activeReport = report;
    openDrawer(renderReportDrawer(report, state.meta, state.user));
  } catch (error) {
    handleError(error, 'Could not open that report.');
  }
}

async function reloadReport(id) {
  try {
    const report = await api.get(`/reports/${id}`);
    state.activeReport = report;
    openDrawer(renderReportDrawer(report, state.meta, state.user));
    await refreshSilent();
  } catch (error) {
    handleError(error, 'Could not refresh the report.');
  }
}

/* ==========================================================================
   Account menu
   ========================================================================== */
let popover = null;

function closePopover() {
  popover?.remove();
  popover = null;
}

function openProfileMenu(anchor) {
  closePopover();
  const rect = anchor.getBoundingClientRect();
  popover = document.createElement('div');
  popover.className = 'popover';
  popover.style.top = `${rect.bottom + 8}px`;
  popover.style.right = `${Math.max(12, window.innerWidth - rect.right)}px`;
  popover.innerHTML = `
    <div class="popover-head">${avatar(state.user)}<div><strong>${escapeHtml(state.user.full_name)}</strong><small>${escapeHtml(state.user.email)}</small></div></div>
    <button class="popover-item" data-action="go" data-view="dashboard">${icon('grid')} Dashboard</button>
    <button class="popover-item" data-action="go" data-view="notifications">${icon('bell')} Notifications ${state.unread ? `(${state.unread})` : ''}</button>
    <div class="popover-sep"></div>
    <button class="popover-item danger" data-action="logout">${icon('logout')} Sign out</button>`;
  document.body.append(popover);
}

/* ==========================================================================
   Auth helpers
   ========================================================================== */
const DEMO = {
  student: { email: 'student@hostelhub.edu.ng', password: 'Student@123' },
  staff: { email: 'grace.okafor@hostelhub.edu.ng', password: 'Staff@123' },
  admin: { email: 'admin@hostelhub.edu.ng', password: 'Admin@123' },
};

function fillDemo(role) {
  const credentials = DEMO[role];
  if (!credentials) return;
  if (state.authMode !== 'login') {
    state.authMode = 'login';
    renderAuthView();
  }
  $('#login-email').value = credentials.email;
  $('#login-password').value = credentials.password;
  $('#login-password').focus();
  toast('Demo account ready', `Sign in as ${role === 'staff' ? 'maintenance staff' : role}.`);
}

async function logout() {
  try {
    await api.post('/auth/logout');
  } catch {
    /* The local session is cleared regardless. */
  }
  signOutLocal();
}

function signOutLocal(message = '') {
  closeDrawer();
  closeModal();
  closePopover();
  state.user = null;
  state.meta = null;
  state.dashboard = null;
  state.analytics = null;
  state.unread = 0;
  state.booted = false;
  showAuth('login');
  if (message) toast('Signed out', message, 'error');
}

/* ==========================================================================
   Error helpers
   ========================================================================== */
function handleError(error, fallback = 'Something went wrong.') {
  if (error instanceof ApiError && error.status === 401) {
    signOutLocal('Your session has expired. Please sign in again.');
    return;
  }
  toast('Request failed', error.message || fallback, 'error');
}

function formButton(form) {
  return form.querySelector('button[type="submit"]') || document.querySelector(`button[form="${form.id}"]`);
}

function formObject(form) {
  const data = {};
  new FormData(form).forEach((value, key) => { data[key] = value; });
  return data;
}

/* ==========================================================================
   Click handling
   ========================================================================== */
document.addEventListener('click', async (event) => {
  const target = event.target.closest('[data-action]');
  if (!target) return;
  const action = target.dataset.action;
  if (action === 'noop') return;

  if (action === 'go') {
    event.preventDefault();
    await navigate(target.dataset.view);
    return;
  }
  if (action === 'open-sidebar') {
    $('#sidebar').classList.add('open');
    $('#sidebar-scrim').classList.add('open');
    return;
  }
  if (action === 'close-sidebar') {
    closeSidebar();
    return;
  }
  if (action === 'profile-menu') {
    event.stopPropagation();
    if (popover) closePopover();
    else openProfileMenu(target);
    return;
  }
  if (action === 'close-modal') {
    closeModal();
    return;
  }
  if (action === 'close-drawer') {
    closeDrawer();
    return;
  }
  if (action === 'auth-mode') {
    state.authMode = target.dataset.mode || 'login';
    renderAuthView();
    return;
  }
  if (action === 'fill-demo') {
    fillDemo(target.dataset.role);
    return;
  }
  if (action === 'toggle-password') {
    const input = document.getElementById(target.dataset.target);
    if (!input) return;
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    target.innerHTML = icon(show ? 'eye' : 'lock');
    target.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    return;
  }
  if (action === 'logout') {
    await logout();
    return;
  }
  if (action === 'refresh') {
    await showView(state.view);
    return;
  }
  if (!state.user) return;

  if (action === 'new-report') {
    openReportForm(state);
    return;
  }
  if (action === 'open-report') {
    await openReport(Number(target.dataset.id));
    return;
  }
  if (action === 'toggle-overdue') {
    state.filters.overdue = !state.filters.overdue;
    await loadView('reports', { silent: true });
    return;
  }
  if (action === 'clear-filters') {
    state.filters = { q: '', status: '', priority: '', category: '', hostel_id: '', overdue: false };
    await loadView('reports', { silent: true });
    return;
  }
  if (action === 'set-rating') {
    const form = target.closest('form');
    const rating = Number(target.dataset.value);
    form.querySelector('input[name="rating"]').value = rating;
    [...form.querySelectorAll('.star-btn')].forEach((button) => {
      button.classList.toggle('active', Number(button.dataset.value) <= rating);
    });
    return;
  }
  if (action === 'mark-all-read') {
    try {
      const data = await api.post('/notifications/read', {});
      state.notifications = data;
      updateUnread(data.unread || 0);
      if (state.view === 'notifications') {
        $('#main-content').innerHTML = renderNotifications(data);
      }
      toast('Notifications cleared', 'Everything is marked as read.');
    } catch (error) {
      handleError(error);
    }
    return;
  }
  if (action === 'open-notification') {
    const reportId = Number(target.dataset.id);
    try {
      await api.post('/notifications/read', { id: target.dataset.id });
      state.unread = Math.max(0, state.unread - 1);
      renderChrome();
    } catch {
      /* Reading the notification is not critical to opening the report. */
    }
    await openReport(reportId);
    return;
  }
  if (action === 'new-user') {
    openUserForm(state);
    return;
  }
  if (action === 'edit-user') {
    const person = state.users.find((item) => item.id === Number(target.dataset.id));
    if (person) openUserForm(state, person);
    return;
  }
  if (action === 'new-hostel') {
    openHostelForm();
    return;
  }
  if (action === 'edit-hostel') {
    const hostel = state.hostels.find((item) => item.id === Number(target.dataset.id));
    if (hostel) openHostelForm(hostel);
    return;
  }
  if (action === 'new-facility') {
    openFacilityForm(state.meta, null, Number(target.dataset.hostel) || '');
    return;
  }
  if (action === 'edit-facility') {
    const facility = state.facilities.find((item) => item.id === Number(target.dataset.id));
    if (facility) openFacilityForm(state.meta, facility);
    return;
  }
  if (action === 'new-announcement') {
    openAnnouncementForm();
    return;
  }
  if (action === 'delete-announcement') {
    const confirmed = await confirmDialog({
      title: 'Delete this announcement?',
      message: 'It will disappear from every resident and staff dashboard. This cannot be undone.',
      confirmLabel: 'Delete announcement',
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api.delete(`/api/announcements/${target.dataset.id}`);
      toast('Announcement deleted', 'It has been removed from the noticeboard.');
      await refreshSilent();
    } catch (error) {
      handleError(error);
    }
    return;
  }
  if (action === 'assign-report') {
    const id = Number(target.dataset.id);
    const select = $('#assign-staff');
    const staffId = Number(select?.value);
    if (!staffId) {
      toast('Choose an officer', 'Select a maintenance officer before assigning.', 'error');
      return;
    }
    const restore = buttonBusy(target, 'Assigning…');
    try {
      await api.post(`/reports/${id}/assign`, { staff_id: staffId });
      toast('Report assigned', 'The officer and resident have been notified.');
      await reloadReport(id);
      restore();
    } catch (error) {
      restore();
      handleError(error);
    }
    return;
  }
  if (action === 'start-report') {
    const id = Number(target.dataset.id);
    const restore = buttonBusy(target, 'Starting…');
    try {
      await api.post(`/reports/${id}/status`, { status: 'in_progress' });
      toast('Work started', 'The resident has been notified.');
      await reloadReport(id);
      restore();
    } catch (error) {
      restore();
      handleError(error);
    }
    return;
  }
  if (action === 'resolve-report') {
    if (state.activeReport) openResolveForm(state.activeReport);
    return;
  }
  if (action === 'reopen-report') {
    if (state.activeReport) openReopenForm(state.activeReport);
    return;
  }
  if (action === 'close-report') {
    const report = state.activeReport;
    if (!report) return;
    const confirmed = await confirmDialog({
      title: 'Close this report?',
      message: 'Closing confirms the issue is fully resolved. The resident can still reopen it later if the fault returns.',
      confirmLabel: 'Close report',
    });
    if (!confirmed) return;
    try {
      await api.post(`/reports/${report.id}/status`, { status: 'closed' });
      toast('Report closed', `${report.ref} is now closed.`);
      await reloadReport(report.id);
    } catch (error) {
      handleError(error);
    }
  }
});

document.addEventListener('click', (event) => {
  if (popover && !event.target.closest('.popover') && !event.target.closest('[data-action="profile-menu"]')) {
    closePopover();
  }
});

/* ==========================================================================
   Input and filter handling
   ========================================================================== */
const debouncedReportSearch = debounce((value) => {
  state.filters.q = value;
  if (state.view === 'reports') loadView('reports', { silent: true });
}, 320);

const debouncedUserSearch = debounce((value) => {
  state.userFilters.q = value;
  if (state.view === 'users') loadView('users', { silent: true });
}, 320);

document.addEventListener('input', (event) => {
  if (event.target.id === 'report-search') debouncedReportSearch(event.target.value);
  if (event.target.id === 'user-search') debouncedUserSearch(event.target.value);
});

document.addEventListener('change', async (event) => {
  const filter = event.target.dataset.filter;
  if (!filter) return;
  if (filter === 'user_role') {
    state.userFilters.role = event.target.value;
    await loadView('users', { silent: true });
    return;
  }
  state.filters[filter] = event.target.value;
  await loadView('reports', { silent: true });
});

/* ==========================================================================
   Form submissions
   ========================================================================== */
document.addEventListener('submit', async (event) => {
  const form = event.target.closest('form[data-form]');
  if (!form) return;
  event.preventDefault();
  if (form.dataset.busy === '1') return;
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  const type = form.dataset.form;
  const button = formButton(form);
  const restore = buttonBusy(button, 'Working…');
  form.dataset.busy = '1';

  try {
    if (type === 'login' || type === 'register') {
      const data = formObject(form);
      if (type === 'register' && data.hostel_id) data.hostel_id = Number(data.hostel_id);
      if (type === 'register' && !data.hostel_id) delete data.hostel_id;
      const path = type === 'login' ? '/auth/login' : '/auth/register';
      const result = await api.post(path, data);
      await enterApp(result.user);
      toast(type === 'login' ? `Welcome back, ${result.user.full_name.split(' ')[0]}` : 'Account created', 'Your HostelHub workspace is ready.');
      return;
    }

    if (!state.user) return;

    if (type === 'report') {
      const payload = formObject(form);
      if (!payload.facility_id) delete payload.facility_id;
      if (payload.hostel_id) payload.hostel_id = Number(payload.hostel_id);
      if (!payload.photo) delete payload.photo;
      const created = await api.post('/reports', payload);
      closeModal();
      state.filters = { q: '', status: '', priority: '', category: '', hostel_id: '', overdue: false };
      toast('Report submitted', `${created.ref} is now in the facilities queue.`);
      await navigate('reports');
      await openReport(created.id);
      return;
    }

    if (type === 'comment') {
      const id = Number(form.dataset.id);
      const payload = {
        note: form.querySelector('[name="note"]').value,
        internal: Boolean(form.querySelector('[name="internal"]')?.checked),
      };
      await api.post(`/reports/${id}/comments`, payload);
      toast('Comment posted', payload.internal ? 'Only staff can see this internal note.' : 'Everyone following the report can see it.');
      await reloadReport(id);
      return;
    }

    if (type === 'feedback') {
      const id = Number(form.dataset.id);
      const payload = {
        rating: Number(form.querySelector('[name="rating"]').value),
        feedback: form.querySelector('[name="feedback"]').value,
      };
      if (!payload.rating) {
        toast('Choose a rating', 'Select between one and five stars.', 'error');
        return;
      }
      await api.post(`/reports/${id}/feedback`, payload);
      toast('Thank you', 'Your rating helps us improve the maintenance service.');
      await reloadReport(id);
      return;
    }

    if (type === 'resolve') {
      const id = Number(form.dataset.id);
      const note = form.querySelector('[name="note"]').value;
      await api.post(`/reports/${id}/status`, { status: 'resolved', note });
      closeModal();
      toast('Report resolved', 'The resident can now rate the service.');
      await reloadReport(id);
      return;
    }

    if (type === 'reopen') {
      const id = Number(form.dataset.id);
      const note = form.querySelector('[name="note"]').value;
      await api.post(`/reports/${id}/status`, { status: 'reopened', note });
      closeModal();
      toast('Report reopened', 'It has returned to the maintenance queue.');
      await reloadReport(id);
      return;
    }

    if (type === 'create-user' || type === 'edit-user') {
      const payload = formObject(form);
      if (type === 'create-user') {
        await api.post('/api/admin/users', payload);
        toast('Account created', `${payload.full_name} can now sign in.`);
      } else {
        const id = Number(form.dataset.id);
        const active = form.querySelector('[name="is_active"]')?.checked;
        payload.is_active = Boolean(active);
        if (!payload.password) delete payload.password;
        delete payload.email;
        await api.patch(`/api/admin/users/${id}`, payload);
        toast('Person updated', 'Their role and access settings have been saved.');
      }
      closeModal();
      await refreshSilent();
      return;
    }

    if (type === 'create-hostel' || type === 'edit-hostel') {
      const payload = formObject(form);
      payload.total_rooms = Number(payload.total_rooms || 0);
      if (type === 'create-hostel') {
        await api.post('/api/admin/hostels', payload);
        toast('Hostel added', `${payload.name} is now part of the portfolio.`);
      } else {
        await api.patch(`/api/admin/hostels/${form.dataset.id}`, payload);
        toast('Hostel updated', 'The hostel record has been saved.');
      }
      closeModal();
      await refreshSilent();
      return;
    }

    if (type === 'create-facility' || type === 'edit-facility') {
      const payload = formObject(form);
      if (payload.hostel_id) payload.hostel_id = Number(payload.hostel_id);
      if (type === 'create-facility') {
        await api.post('/api/admin/facilities', payload);
        toast('Facility added', 'It can now be selected when reporting a fault.');
      } else {
        delete payload.hostel_id;
        await api.patch(`/api/admin/facilities/${form.dataset.id}`, payload);
        toast('Facility updated', 'Its condition has been saved.');
      }
      closeModal();
      await refreshSilent();
      return;
    }

    if (type === 'announcement') {
      const payload = formObject(form);
      payload.is_pinned = Boolean(form.querySelector('[name="is_pinned"]')?.checked);
      await api.post('/api/announcements', payload);
      closeModal();
      toast('Announcement published', 'It is now visible to the selected audience.');
      await refreshSilent();
      return;
    }
  } catch (error) {
    if (type === 'login' || type === 'register') {
      showAuthError(error.message || 'Could not sign in.');
    } else {
      handleError(error);
    }
  } finally {
    form.dataset.busy = '';
    restore();
  }
});

/* ==========================================================================
   Global listeners and start
   ========================================================================== */
window.addEventListener('popstate', () => {
  if (!state.user) return;
  const view = viewFromHash();
  navigate(view, { push: false });
});

window.addEventListener('scroll', () => closePopover(), { passive: true });

let bootStarted = false;
function start() {
  if (bootStarted) return;
  bootStarted = true;
  boot();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', start, { once: true });
} else {
  start();
}
