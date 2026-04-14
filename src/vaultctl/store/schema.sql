PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  root TEXT NOT NULL,
  include_glob TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  source_id TEXT NOT NULL,
  rel_path TEXT NOT NULL,
  abs_path TEXT NOT NULL,
  title TEXT NOT NULL,
  title_ci TEXT NOT NULL DEFAULT '',
  title_slug TEXT NOT NULL DEFAULT '',
  status TEXT,
  body TEXT NOT NULL,
  heading_path TEXT NOT NULL DEFAULT '',
  tags_text TEXT NOT NULL DEFAULT '',
  mtime REAL NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_id, rel_path),
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_source_title_ci ON documents(source_id, title_ci);
CREATE INDEX IF NOT EXISTS idx_documents_source_title_slug ON documents(source_id, title_slug);

CREATE TABLE IF NOT EXISTS document_aliases (
  document_id INTEGER NOT NULL,
  alias TEXT NOT NULL,
  alias_ci TEXT NOT NULL,
  alias_slug TEXT NOT NULL,
  UNIQUE(document_id, alias),
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_aliases_ci ON document_aliases(alias_ci);
CREATE INDEX IF NOT EXISTS idx_aliases_slug ON document_aliases(alias_slug);

CREATE TABLE IF NOT EXISTS document_tags (
  document_id INTEGER NOT NULL,
  tag TEXT NOT NULL,
  UNIQUE(document_id, tag),
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS document_links (
  document_id INTEGER NOT NULL,
  raw_target TEXT NOT NULL,
  link_target TEXT NOT NULL,
  link_target_ci TEXT NOT NULL,
  link_target_slug TEXT NOT NULL,
  target_fragment TEXT,
  resolved_document_id INTEGER,
  resolution_state TEXT NOT NULL DEFAULT 'dangling',
  resolution_method TEXT,
  ambiguous_count INTEGER NOT NULL DEFAULT 0,
  occurrences INTEGER NOT NULL DEFAULT 1,
  UNIQUE(document_id, raw_target, target_fragment),
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY(resolved_document_id) REFERENCES documents(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_links_document_id ON document_links(document_id);
CREATE INDEX IF NOT EXISTS idx_links_target_ci ON document_links(link_target_ci);
CREATE INDEX IF NOT EXISTS idx_links_target_slug ON document_links(link_target_slug);
CREATE INDEX IF NOT EXISTS idx_links_state ON document_links(resolution_state);
CREATE INDEX IF NOT EXISTS idx_links_resolved ON document_links(resolved_document_id);

CREATE TABLE IF NOT EXISTS document_graph_stats (
  document_id INTEGER PRIMARY KEY,
  in_degree INTEGER NOT NULL DEFAULT 0,
  out_degree INTEGER NOT NULL DEFAULT 0,
  dangling_outgoing INTEGER NOT NULL DEFAULT 0,
  ambiguous_outgoing INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS graph_scores (
  document_id INTEGER NOT NULL,
  metric TEXT NOT NULL,
  score REAL NOT NULL,
  PRIMARY KEY(document_id, metric),
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sections (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL,
  heading_path TEXT NOT NULL,
  body TEXT NOT NULL,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
  title,
  heading_path,
  tags_text,
  body,
  source_id UNINDEXED,
  rel_path UNINDEXED,
  tokenize='unicode61 remove_diacritics 2'
);
