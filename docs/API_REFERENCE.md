# API Reference

Base path: `/api`

All endpoints accept and return `application/json`. Mutating endpoints check
`Origin` against `Host` to block cross-origin requests. Session is maintained
via the `hfr_session` cookie or `Authorization: Bearer <token>` header.

## Authentication

### POST /auth/register
Create a student account (role is always `student`; matric number required).

Body: `full_name`, `email`, `password` (≥8), `student_id`, `hostel_id` (opt),
`phone`, `room_number`, `department`

Response `201`: `{ user, token }`

### POST /auth/login
Body: `email`, `password`

Response `200`: `{ user, token }`

### POST /auth/logout
Revokes the current session. Response `200`: `{ ok: true }`

### GET /auth/me
Response `200`: `{ user }`

## Meta

### GET /meta
Response `200`: `{ hostels[], facilities[], staff[], categories[],
priorities[], statuses[], sla_hours }`

## Reports

### GET /reports
Query: `status`, `priority`, `category`, `hostel_id`, `assigned_to`, `q`,
`overdue`, `open`, `page`, `per_page`

Students see only their own reports; staff only assigned; admins all.

Response `200`: `{ items[], total, page, per_page, summary }`

### POST /reports (students only)
Body: `hostel_id`, `facility_id` (opt), `category`, `title` (≥5), `description`
(≥15), `location` (≥2), `priority`, `photo` (data URL ≤2 MB)

Response `201`: created report object

### GET /reports/:id
Response `200`: full report with `hostel`, `student`, `staff`, `updates`,
`photo`, `capabilities`

### POST /reports/:id/assign (admin only)
Body: `staff_id`, `note` (opt)

### POST /reports/:id/status
Body: `status` (assigned/in_progress/resolved/closed/reopened), `note` (opt)

Role rules: students may close their own resolved reports and reopen
resolved/closed ones; staff/admins may start and resolve assigned reports.

### POST /reports/:id/comments
Body: `note` (≥2), `internal` (staff/admin only)

### POST /reports/:id/feedback (student only)
Body: `rating` (1–5), `feedback` (opt ≤1000)

## Dashboard & analytics

### GET /dashboard
Role-scoped stats, recent reports, overdue attention list, announcements.

### GET /analytics (admin only)
Totals, by status/priority/category/hostel, 6-month trend, staff workload.

## Notifications

### GET /notifications
`{ items[], unread }`

### POST /notifications/read
Body: `{ id }` (opt) — mark one or all as read.

## Announcements

### GET /announcements
Role-scoped (all / students / staff / admin).

### POST /announcements (admin only)
Body: `title`, `body`, `audience`, `is_pinned`

### DELETE /announcements/:id (admin only)

## Administration — users

### GET /admin/users
Query: `role`, `q`

### POST /admin/users (admin only)
Body: full user payload incl. `role`

### PATCH /admin/users/:id (admin only)
Body: any subset of `full_name`, `role`, `is_active`, `phone`, `department`,
`room_number`, `hostel_id`, `password`

Cannot deactivate yourself or remove your own admin role if you are the last
active admin.

## Administration — hostels

### GET /admin/hostels | POST /admin/hostels | PATCH /admin/hostels/:id

Fields: `name`, `code` (unique), `gender`, `total_rooms`, `address`,
`warden_name`, `warden_phone`

## Administration — facilities

### GET /admin/facilities | POST /admin/facilities | PATCH /admin/facilities/:id

Fields: `hostel_id`, `name`, `category`, `location`, `condition`

## Error responses

```json
{ "error": "human-readable message", "details": {} }
```

Common statuses: `400` validation, `401` not signed in, `403` forbidden,
`404` not found, `409` conflict, `413` payload too large, `415` wrong
content type, `500` server error.
