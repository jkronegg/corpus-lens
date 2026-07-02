-- ============================================================
-- Base de données des entités nommées (Named Entities)
-- Source secondaire dérivée des fichiers Markdown de sources/
-- ============================================================
-- Conçue pour être extensible: la table `person` peut être
-- accompagnée à l'avenir d'autres tables (lieu, organisation...)
-- toutes liées à une table centrale `named_entity`.
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- Table centrale : entité nommée (base extensible)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS named_entity (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    key          TEXT    NOT NULL UNIQUE,  -- clé métier stable (ex. "karl_egli_1865")
    entity_type  TEXT    NOT NULL          -- discriminant: 'person', 'place', 'org', ...
        CHECK (entity_type IN ('person', 'place', 'organization', 'event', 'other')),
    display_name TEXT    NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_named_entity_type ON named_entity(entity_type);
CREATE INDEX IF NOT EXISTS idx_named_entity_key  ON named_entity(key);

-- ------------------------------------------------------------
-- Table spécialisée : personne
-- Liée 1-1 à named_entity via entity_id (entity_type = 'person')
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS person (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id    INTEGER NOT NULL UNIQUE
        REFERENCES named_entity(id) ON DELETE CASCADE,
    -- Copie dénormalisée pour accès direct sans jointure
    key          TEXT    NOT NULL UNIQUE,
    display_name TEXT    NOT NULL,
    -- aliases_names: tableau JSON de chaînes (ex. ["Egli, Karl", "Colonel Egli"])
    aliases_names TEXT   NOT NULL DEFAULT '[]'
        CHECK (json_valid(aliases_names)),
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_person_key          ON person(key);
CREATE INDEX IF NOT EXISTS idx_person_display_name ON person(display_name COLLATE NOCASE);

-- ------------------------------------------------------------
-- Table des sources indexées (remplace le concept sources_index.json)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    identifiant_technique  TEXT    NOT NULL UNIQUE,
    identifiant_source     TEXT    NOT NULL UNIQUE,
    titre                  TEXT    NOT NULL,
    date_publication       TEXT    NOT NULL DEFAULT '0000-00-00',
    date_consultation      TEXT    NOT NULL DEFAULT '0000-00-00',
    origine                TEXT    NOT NULL UNIQUE,
    auteurs_json           TEXT    NOT NULL DEFAULT '[]'
        CHECK (json_valid(auteurs_json)),
    periodes_json          TEXT    NOT NULL DEFAULT '[]'
        CHECK (json_valid(periodes_json)),
    isbn                   TEXT    NOT NULL DEFAULT '',
    issn                   TEXT    NOT NULL DEFAULT '',
    doi                    TEXT    NOT NULL DEFAULT '',
    url                    TEXT    NOT NULL DEFAULT '',
    langues                TEXT,
    pertinence             REAL    NOT NULL DEFAULT 0.0
        CHECK (pertinence >= 0.0 AND pertinence <= 1.0),
    type_source            TEXT    NOT NULL DEFAULT 'secondaire'
        CHECK (type_source IN ('primaire', 'secondaire')),
    lisible                INTEGER NOT NULL DEFAULT 0
        CHECK (lisible IN (0, 1)),
    nombre_pages           INTEGER NOT NULL DEFAULT -1,
    categorie              TEXT    NOT NULL DEFAULT 'autre',
    extrait_brut           TEXT    NOT NULL DEFAULT '',
    resume                 TEXT    NOT NULL DEFAULT '',
    created_at             TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at             TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_source_identifiant_source ON source(identifiant_source);
CREATE INDEX IF NOT EXISTS idx_source_origine            ON source(origine);
CREATE INDEX IF NOT EXISTS idx_source_date_publication   ON source(date_publication);
CREATE INDEX IF NOT EXISTS idx_source_type_source        ON source(type_source);
CREATE INDEX IF NOT EXISTS idx_source_categorie          ON source(categorie);

-- ------------------------------------------------------------
-- Table de correspondance entre une source indexée et ses fichiers
-- (document principal + documents dérivés: .md, .json, traduction, etc.)
-- Le type du document est déduit de parent_doc_id:
--   - parent_doc_id IS NULL  => document original
--   - parent_doc_id NOT NULL => document dérivé
-- ner_status: Statut NER (Named Entity Recognition) du document
--   - 0 = not NER-able (fichiers non-.md: images, JSON, PDF, etc.)
--   - 1 = NER-able (fichier .md sans mentions reconnaissables)
--   - 2 = NER-ed (fichier .md avec mentions d'entités nommées enregistrées)
-- Permet de suivre le traitement NER et d'identifier les documents
-- candidats pour extraction de mentions ou amélioration du NER.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source_document (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     INTEGER NOT NULL
        REFERENCES source(id) ON DELETE CASCADE,
    parent_doc_id INTEGER
        REFERENCES source_document(id) ON DELETE SET NULL,
    path          TEXT    NOT NULL UNIQUE,
    file_name     TEXT    NOT NULL,
    relative_path TEXT,
    author        TEXT    NOT NULL DEFAULT '',
    ner_status    NUMBER  DEFAULT NULL
        CHECK (ner_status IN (0, 1, 2))
);

CREATE INDEX IF NOT EXISTS idx_source_document_source_id ON source_document(source_id);
CREATE INDEX IF NOT EXISTS idx_source_document_path      ON source_document(path);
CREATE INDEX IF NOT EXISTS idx_source_document_parent_doc_id ON source_document(parent_doc_id);

-- ------------------------------------------------------------
-- Table des mentions (références dans les sources Markdown)
-- Générique: peut référencer n'importe quelle named_entity
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mention (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Référence à l'entité nommée (generique) et raccourci vers person
    entity_id     INTEGER NOT NULL
        REFERENCES named_entity(id) ON DELETE CASCADE,
    -- Localisation dans la source
    source_document_id INTEGER
        REFERENCES source_document(id) ON DELETE CASCADE,
    source        TEXT    NOT NULL,  -- chemin relatif depuis sources/ (ex. "DHS/colonels_dhs_017332.md")
    page          INTEGER NOT NULL,  -- numéro de page (## Page X)
    line_start    INTEGER,           -- numéro de ligne dans le fichier (nullable)
    line_end      INTEGER,           -- fin de mention (nullable)
    -- Contenu
    quote         TEXT,              -- extrait exact du texte (nullable)
    -- Dates
    event_date    TEXT,              -- date contextuelle de la mention (ISO 8601, nullable)
    creation_date TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    -- Traçabilité de l'extraction
    extractor     TEXT    NOT NULL DEFAULT 'manual'  -- 'manual', 'spacy', 'llm', ...
        CHECK (extractor IN ('manual', 'spacy', 'stanza', 'llm', 'rule', 'import')),
    confidence    REAL             -- score de confiance NER 0.0-1.0 (nullable)
        CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    UNIQUE (entity_id, source, page, line_start, line_end, quote)
);

CREATE INDEX IF NOT EXISTS idx_mention_entity_id ON mention(entity_id);
CREATE INDEX IF NOT EXISTS idx_mention_source_document_id ON mention(source_document_id);
CREATE INDEX IF NOT EXISTS idx_mention_source    ON mention(source);
CREATE INDEX IF NOT EXISTS idx_mention_entity_source_document ON mention(entity_id, source_document_id);
CREATE INDEX IF NOT EXISTS idx_mention_entity_source ON mention(entity_id, source);
CREATE INDEX IF NOT EXISTS idx_mention_event_date    ON mention(event_date);

-- ------------------------------------------------------------
-- Vue pratique : mentions de personnes avec nom complet
-- Note: mention.source contient le chemin complet depuis sources/
-- La correspondance se fait directement avec source_document.path
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_person_mentions;
CREATE VIEW v_person_mentions AS
SELECT
    p.id            AS person_id,
    p.key           AS person_key,
    p.display_name  AS person_name,
    p.aliases_names AS person_aliases,
    m.id            AS mention_id,
    m.source,
    sd.id           AS source_document_id_resolved,
    sd.path         AS source_path,
    s.id            AS source_id,
    s.identifiant_technique AS source_identifiant_technique,
    s.identifiant_source    AS source_identifiant_source,
    s.titre                AS source_titre,
    s.origine              AS source_origine,
    m.page,
    m.line_start,
    m.line_end,
    m.quote,
    m.event_date,
    m.creation_date,
    m.extractor,
    m.confidence
FROM person p
JOIN mention m ON m.entity_id = p.entity_id
LEFT JOIN source_document sd ON sd.path = m.source
LEFT JOIN source s ON s.id = sd.source_id;

