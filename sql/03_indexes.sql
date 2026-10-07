-- name: source_identity
CREATE UNIQUE INDEX idx_source_identity_lookup ON SourceIdentity(source_system_id, source_key);
-- name: project_activity
CREATE INDEX idx_production_project_time ON ProductionActivity(project_id, activity_timestamp);
-- name: employee_labor
CREATE INDEX idx_timeentry_person_date ON TimeEntry(person_id, work_date);
-- name: project_labor
CREATE INDEX idx_timeentry_work_date ON TimeEntry(work_date);
