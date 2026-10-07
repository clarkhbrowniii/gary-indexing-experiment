-- Query sections are separated by the named marker below.
-- name: source_identity
SELECT entity_type, entity_id FROM SourceIdentity
WHERE source_system_id = ? AND source_key = ?;
-- name: project_activity
SELECT activity_id, person_id, application_id, endpoint_id, activity_type,
       activity_timestamp, duration_seconds
FROM ProductionActivity
WHERE project_id = ? AND activity_timestamp >= ? AND activity_timestamp < ?
ORDER BY activity_timestamp;
-- name: employee_labor
SELECT time_entry_id, project_id, work_date, hours, description
FROM TimeEntry
WHERE person_id = ? AND work_date BETWEEN ? AND ?
ORDER BY work_date;
-- name: project_labor
SELECT project_id, SUM(hours) AS total_hours, COUNT(*) AS entry_count
FROM TimeEntry
WHERE work_date >= ? AND work_date < ?
GROUP BY project_id ORDER BY total_hours DESC;
