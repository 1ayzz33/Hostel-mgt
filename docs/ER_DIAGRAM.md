# Entity–Relationship Diagram (text form)

HostelHub's data model is stored in a single SQLite file. Below is a
machine-readable PlantUML rendering plus a plain-text summary you can paste
into any ER diagram tool (draw.io, dbdiagram.io, Lucidchart, etc.).

## PlantUML (paste at https://www.plantuml.com/plantuml)

```plantuml
@startuml
skinparam monochrome true
skinparam linetype ortho

entity "users" as users {
  id : INTEGER PK
  full_name : TEXT
  email : TEXT UNIQUE
  password_hash : TEXT
  role : TEXT (student|staff|admin)
  student_id : TEXT
  phone : TEXT
  hostel_id : INTEGER FK -> hostels.id
  room_number : TEXT
  department : TEXT
  is_active : INTEGER
  created_at : TEXT
  updated_at : TEXT
}

entity "hostels" as hostels {
  id : INTEGER PK
  name : TEXT
  code : TEXT UNIQUE
  gender : TEXT (Male|Female|Mixed)
  address : TEXT
  warden_name : TEXT
  warden_phone : TEXT
  total_rooms : INTEGER
  created_at : TEXT
}

entity "facilities" as facilities {
  id : INTEGER PK
  hostel_id : INTEGER FK -> hostels.id
  name : TEXT
  category : TEXT
  location : TEXT
  condition : TEXT (Good|Fair|Poor|Under repair)
  created_at : TEXT
}

entity "reports" as reports {
  id : INTEGER PK
  ref : TEXT UNIQUE (HFR-YYYY-NNNN)
  student_id : INTEGER FK -> users.id
  hostel_id : INTEGER FK -> hostels.id
  facility_id : INTEGER FK -> facilities.id
  category : TEXT
  title : TEXT
  description : TEXT
  location : TEXT
  priority : TEXT (low|medium|high|urgent)
  status : TEXT (submitted|assigned|in_progress|resolved|closed|reopened)
  assigned_to : INTEGER FK -> users.id
  photo : TEXT
  created_at : TEXT
  updated_at : TEXT
  resolved_at : TEXT
  resolution_note : TEXT
  rating : INTEGER (1-5)
  feedback : TEXT
}

entity "report_updates" as report_updates {
  id : INTEGER PK
  report_id : INTEGER FK -> reports.id
  user_id : INTEGER FK -> users.id
  action : TEXT
  note : TEXT
  from_status : TEXT
  to_status : TEXT
  is_internal : INTEGER
  created_at : TEXT
}

entity "notifications" as notifications {
  id : INTEGER PK
  user_id : INTEGER FK -> users.id
  report_id : INTEGER FK -> reports.id
  title : TEXT
  message : TEXT
  is_read : INTEGER
  created_at : TEXT
}

entity "announcements" as announcements {
  id : INTEGER PK
  title : TEXT
  body : TEXT
  audience : TEXT (all|students|staff|admin)
  is_pinned : INTEGER
  created_by : INTEGER FK -> users.id
  created_at : TEXT
}

entity "sessions" as sessions {
  token_hash : TEXT PK
  user_id : INTEGER FK -> users.id
  created_at : TEXT
  expires_at : TEXT
  last_seen : TEXT
}

users ||--o{ hostels : "manages (warden)"
users }|--|{ hostels : "lives in / assigned to"
users ||--o{ reports : "submits (student)"
users ||--o{ reports : "handles (staff)"
users ||--o{ reports : "assigns (admin)"
users }|--|{ report_updates : "authors"
users }|--|{ notifications : "receives"
users }|--|{ sessions : "owns"
hostels ||--|{ facilities : "contains"
hostels ||--|{ reports : "belongs to"
facilities }|--|{ reports : "referenced by"
reports ||--|{ report_updates : "timeline"
reports ||--|{ notifications : "triggers"
announcements }|--|| users : "created by"
@enduml
```

## Plain-text summary

| Table | Purpose | Key relationships |
|-------|---------|-------------------|
| `users` | Students, maintenance staff, administrators | `hostel_id` → `hostels` |
| `hostels` | Halls of residence (warden, capacity, gender) | — |
| `facilities` | Registered assets per hostel (tap, fan, Wi-Fi AP…) | `hostel_id` → `hostels` |
| `reports` | Fault reports with priority, status, SLA | `student_id` → `users`; `hostel_id` → `hostels`; `facility_id` → `facilities`; `assigned_to` → `users` |
| `report_updates` | Immutable audit timeline per report | `report_id` → `reports`; `user_id` → `users` |
| `notifications` | Per-user inbox items | `user_id` → `users`; `report_id` → `reports` |
| `announcements` | Pinned notices for audiences | `created_by` → `users` |
| `sessions` | Hashed auth tokens with expiry | `user_id` → `users` |

## Key business rules encoded in the schema

- A student sees only their own reports; staff see only assigned reports; admins see everything.
- `report_updates.is_internal` hides staff-only notes from students.
- `reports.resolved_at`, `rating` and `feedback` are populated only when status moves to `resolved`.
- `ref` is generated as `HFR-YYYY-NNNN` for human-readable ticket IDs.
- Foreign keys are enforced (`PRAGMA foreign_keys = ON`) with cascading deletes where appropriate.
