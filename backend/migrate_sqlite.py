#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Migration SQLite idempotente pour FeedFormula AI.

Objectifs :
1) Ajouter la colonne `region` à la table `users` (si absente),
2) Créer la table `otp_codes` (si absente),
3) Créer la table `user_action_logs` (si absente),
4) Créer les index nécessaires (si absents).

Ce script peut être relancé plusieurs fois sans effet de bord.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import Optional


def resolve_sqlite_path() -> Path:
    """
    Résout le chemin SQLite depuis DATABASE_URL ou fallback local.

    Formats supportés (principaux) :
    - sqlite:///relative/path.db
    - sqlite:////absolute/path.db
    - sqlite:///C:/path/windows.db
    """
    database_url = (os.getenv("DATABASE_URL") or "").strip()

    if database_url.startswith("sqlite:///"):
        raw = database_url[len("sqlite:///") :]

        # Nettoyage querystring éventuelle : sqlite:///db.sqlite?mode=rwc
        if "?" in raw:
            raw = raw.split("?", 1)[0]

        # Cas Windows : /C:/path -> C:/path
        if raw.startswith("/") and len(raw) > 2 and raw[2] == ":":
            raw = raw[1:]

        path = Path(raw)

        # Si relatif, on l'ancre sur la racine projet
        if not path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent
            path = project_root / path

        return path.resolve()

    # Fallback par défaut : <repo>/data/feedformula.db
    project_root = Path(__file__).resolve().parent.parent
    return (project_root / "data" / "feedformula.db").resolve()


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(r[1]).lower() == column_name.lower() for r in rows)


def index_exists(conn: sqlite3.Connection, index_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'index' AND name = ?
        LIMIT 1
        """,
        (index_name,),
    ).fetchone()
    return row is not None


def migrate_users_region(conn: sqlite3.Connection) -> None:
    """
    Ajoute la colonne users.region si absente.
    """
    if not table_exists(conn, "users"):
        print("ℹ️ Table `users` absente : aucune migration de colonne `region` appliquée.")
        return

    if not column_exists(conn, "users", "region"):
        conn.execute("ALTER TABLE users ADD COLUMN region TEXT NOT NULL DEFAULT 'Bénin'")
        print("✅ Colonne `users.region` ajoutée.")
    else:
        print("✓ Colonne `users.region` déjà présente.")

    # Backfill défensif pour lignes legacy (au cas où)
    conn.execute(
        """
        UPDATE users
        SET region = 'Bénin'
        WHERE region IS NULL OR TRIM(region) = ''
        """
    )
    print("✓ Backfill `users.region` vérifié.")


def migrate_otp_codes(conn: sqlite3.Connection) -> None:
    """
    Crée la table otp_codes si absente.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS otp_codes (
            id TEXT PRIMARY KEY,
            telephone TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            expires_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    print("✓ Table `otp_codes` vérifiée/créée.")

    # Index utiles
    if not index_exists(conn, "idx_otp_codes_expires_at"):
        conn.execute(
            "CREATE INDEX idx_otp_codes_expires_at ON otp_codes (expires_at)"
        )
        print("✅ Index `idx_otp_codes_expires_at` créé.")
    else:
        print("✓ Index `idx_otp_codes_expires_at` déjà présent.")


def migrate_user_action_logs(conn: sqlite3.Connection) -> None:
    """
    Crée la table user_action_logs si absente.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_action_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            points_awarded INTEGER NOT NULL DEFAULT 0,
            meta_json TEXT NOT NULL DEFAULT '{}',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    print("✓ Table `user_action_logs` vérifiée/créée.")

    # Index ciblés pour les requêtes de gamification / anti-abus
    indexes = {
        "idx_user_action_logs_user_id": "CREATE INDEX idx_user_action_logs_user_id ON user_action_logs (user_id)",
        "idx_user_action_logs_action": "CREATE INDEX idx_user_action_logs_action ON user_action_logs (action)",
        "idx_user_action_logs_created_at": "CREATE INDEX idx_user_action_logs_created_at ON user_action_logs (created_at)",
        "idx_user_action_logs_user_action_created_at": (
            "CREATE INDEX idx_user_action_logs_user_action_created_at "
            "ON user_action_logs (user_id, action, created_at DESC)"
        ),
        "idx_user_action_logs_user_created_at": (
            "CREATE INDEX idx_user_action_logs_user_created_at "
            "ON user_action_logs (user_id, created_at DESC)"
        ),
    }

    for name, ddl in indexes.items():
        if not index_exists(conn, name):
            conn.execute(ddl)
            print(f"✅ Index `{name}` créé.")
        else:
            print(f"✓ Index `{name}` déjà présent.")


def run_migration(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN")

        migrate_users_region(conn)
        migrate_otp_codes(conn)
        migrate_user_action_logs(conn)

        conn.commit()
        print(f"\n🎉 Migration terminée avec succès sur : {db_path}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    try:
        db_path = resolve_sqlite_path()
        print(f"📦 Base SQLite cible : {db_path}")
        run_migration(db_path)
        return 0
    except Exception as exc:
        print(f"❌ Échec migration : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
