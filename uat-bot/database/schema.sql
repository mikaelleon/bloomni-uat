CREATE TABLE IF NOT EXISTS testers (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    full_name TEXT,
    gcash_number TEXT NOT NULL,
    section_relationship TEXT,
    availability TEXT,
    device_platform TEXT,
    prior_experience TEXT,
    hearing_source TEXT,
    tos_signature TEXT,
    registered_at DATETIME NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    weeks_active INTEGER NOT NULL DEFAULT 0,
    consecutive_weeks INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL DEFAULT 'tester'
);

CREATE TABLE IF NOT EXISTS applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    gcash_number TEXT NOT NULL,
    section_relationship TEXT NOT NULL,
    hearing_source TEXT NOT NULL,
    availability TEXT,
    device_platform TEXT,
    prior_experience TEXT,
    tos_signature TEXT NOT NULL,
    invite_code TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reject_reason TEXT,
    created_at DATETIME NOT NULL,
    reviewed_at DATETIME
);

CREATE TABLE IF NOT EXISTS bugs (
    bug_id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    title TEXT NOT NULL,
    steps TEXT NOT NULL,
    actual TEXT NOT NULL,
    expected TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted',
    duplicate_of TEXT,
    submitted_at DATETIME NOT NULL,
    resolved_at DATETIME,
    thread_id TEXT,
    message_id TEXT,
    FOREIGN KEY (reporter_id) REFERENCES testers(user_id)
);

CREATE TABLE IF NOT EXISTS suggestions (
    suggestion_id TEXT PRIMARY KEY,
    submitter_id TEXT NOT NULL,
    feature_tag TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted',
    dismiss_reason TEXT,
    submitted_at DATETIME NOT NULL,
    actioned_at DATETIME,
    message_id TEXT,
    FOREIGN KEY (submitter_id) REFERENCES testers(user_id)
);

CREATE TABLE IF NOT EXISTS earnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    week_start DATE NOT NULL,
    bugs_submitted INTEGER NOT NULL DEFAULT 0,
    bugs_validated INTEGER NOT NULL DEFAULT 0,
    bugs_resolved INTEGER NOT NULL DEFAULT 0,
    suggestions_submitted INTEGER NOT NULL DEFAULT 0,
    suggestions_acknowledged INTEGER NOT NULL DEFAULT 0,
    suggestions_implemented INTEGER NOT NULL DEFAULT 0,
    loyalty_bonus INTEGER NOT NULL DEFAULT 0,
    total_earned INTEGER NOT NULL DEFAULT 0,
    is_paid INTEGER NOT NULL DEFAULT 0,
    paid_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES testers(user_id)
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    rate_changes TEXT NOT NULL,
    reached INTEGER NOT NULL DEFAULT 0,
    reached_at DATETIME
);

CREATE TABLE IF NOT EXISTS daily_counts (
    user_id TEXT NOT NULL,
    date DATE NOT NULL,
    bugs_today INTEGER NOT NULL DEFAULT 0,
    suggestions_today INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, date),
    FOREIGN KEY (user_id) REFERENCES testers(user_id)
);
