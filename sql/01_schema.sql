PRAGMA foreign_keys = ON;
CREATE TABLE SourceSystem (
 source_system_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
 system_type TEXT NOT NULL CHECK(system_type IN ('design','erp','collaboration','identity'))
);
CREATE TABLE Person (
 person_id INTEGER PRIMARY KEY, display_name TEXT NOT NULL,
 discipline TEXT NOT NULL CHECK(discipline IN ('architecture','structural','civil','mep','management')),
 is_active INTEGER NOT NULL CHECK(is_active IN (0,1))
);
CREATE TABLE Project (
 project_id INTEGER PRIMARY KEY, project_code TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','completed','planning'))
);
CREATE TABLE Application (
 application_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
 category TEXT NOT NULL CHECK(category IN ('bim','cad','analysis','office'))
);
CREATE TABLE Endpoint (
 endpoint_id INTEGER PRIMARY KEY, asset_tag TEXT NOT NULL UNIQUE,
 person_id INTEGER NOT NULL REFERENCES Person(person_id),
 endpoint_type TEXT NOT NULL CHECK(endpoint_type IN ('workstation','laptop'))
);
CREATE TABLE SourceIdentity (
 source_identity_id INTEGER PRIMARY KEY,
 source_system_id INTEGER NOT NULL REFERENCES SourceSystem(source_system_id),
 source_key TEXT NOT NULL CHECK(length(source_key)>0),
 entity_type TEXT NOT NULL CHECK(entity_type IN ('Person','Project','Application','Endpoint')),
 entity_id INTEGER NOT NULL CHECK(entity_id>0)
);
-- Trigger-enforced uniqueness intentionally replaces UNIQUE(system,key) in this
-- experimental schema: a UNIQUE constraint would pre-index Query 1's baseline.
CREATE TRIGGER source_identity_unique_insert BEFORE INSERT ON SourceIdentity
WHEN EXISTS(SELECT 1 FROM SourceIdentity WHERE source_system_id=NEW.source_system_id AND source_key=NEW.source_key)
BEGIN SELECT RAISE(ABORT, 'duplicate source identity'); END;
CREATE TRIGGER source_identity_unique_update BEFORE UPDATE OF source_system_id,source_key ON SourceIdentity
WHEN EXISTS(SELECT 1 FROM SourceIdentity WHERE source_system_id=NEW.source_system_id AND source_key=NEW.source_key AND source_identity_id<>OLD.source_identity_id)
BEGIN SELECT RAISE(ABORT, 'duplicate source identity'); END;
CREATE TRIGGER source_identity_entity_insert BEFORE INSERT ON SourceIdentity
WHEN (NEW.entity_type='Person' AND NOT EXISTS(SELECT 1 FROM Person WHERE person_id=NEW.entity_id))
 OR (NEW.entity_type='Project' AND NOT EXISTS(SELECT 1 FROM Project WHERE project_id=NEW.entity_id))
 OR (NEW.entity_type='Application' AND NOT EXISTS(SELECT 1 FROM Application WHERE application_id=NEW.entity_id))
 OR (NEW.entity_type='Endpoint' AND NOT EXISTS(SELECT 1 FROM Endpoint WHERE endpoint_id=NEW.entity_id))
BEGIN SELECT RAISE(ABORT, 'missing source entity'); END;
CREATE TRIGGER source_identity_entity_update BEFORE UPDATE OF entity_type,entity_id ON SourceIdentity
WHEN (NEW.entity_type='Person' AND NOT EXISTS(SELECT 1 FROM Person WHERE person_id=NEW.entity_id))
 OR (NEW.entity_type='Project' AND NOT EXISTS(SELECT 1 FROM Project WHERE project_id=NEW.entity_id))
 OR (NEW.entity_type='Application' AND NOT EXISTS(SELECT 1 FROM Application WHERE application_id=NEW.entity_id))
 OR (NEW.entity_type='Endpoint' AND NOT EXISTS(SELECT 1 FROM Endpoint WHERE endpoint_id=NEW.entity_id))
BEGIN SELECT RAISE(ABORT, 'missing source entity'); END;
CREATE TABLE ProductionActivity (
 activity_id INTEGER PRIMARY KEY,
 person_id INTEGER NOT NULL REFERENCES Person(person_id),
 project_id INTEGER NOT NULL REFERENCES Project(project_id),
 application_id INTEGER NOT NULL REFERENCES Application(application_id),
 endpoint_id INTEGER NOT NULL REFERENCES Endpoint(endpoint_id),
 activity_type TEXT NOT NULL CHECK(activity_type IN ('model','draft','review','analyze')),
 activity_timestamp TEXT NOT NULL CHECK(length(activity_timestamp)=19 AND activity_timestamp GLOB '????-??-?? ??:??:??'),
 duration_seconds INTEGER NOT NULL CHECK(duration_seconds BETWEEN 1 AND 28800)
);
CREATE TABLE TimeEntry (
 time_entry_id INTEGER PRIMARY KEY,
 person_id INTEGER NOT NULL REFERENCES Person(person_id),
 project_id INTEGER NOT NULL REFERENCES Project(project_id),
 work_date TEXT NOT NULL CHECK(length(work_date)=10 AND work_date GLOB '????-??-??'),
 hours REAL NOT NULL CHECK(hours>0 AND hours<=24), description TEXT NOT NULL
);
