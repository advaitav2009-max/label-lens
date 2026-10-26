"""
Label Lens - SQLite Database Management
Handles user authentication, profiles, scans, and comparison history.
"""

import sqlite3
import os
import json
import shutil
from datetime import datetime

# Serverless detection (Vercel, AWS Lambda, or read-only container)
IS_SERVERLESS = (
    os.environ.get("VERCEL") is not None
    or os.environ.get("VERCEL_ENV") is not None
    or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
    or os.environ.get("LAMBDA_TASK_ROOT") is not None
    or os.path.exists("/var/task")
)

if IS_SERVERLESS:
    DB_PATH = "/tmp/label_lens.db"
    BUNDLED_DB = os.path.join(os.path.dirname(__file__), "label_lens.db")
    if not os.path.exists(DB_PATH) and os.path.exists(BUNDLED_DB):
        try:
            shutil.copy2(BUNDLED_DB, DB_PATH)
        except Exception:
            pass
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "label_lens.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        allergies TEXT DEFAULT '[]',
        dietary_preference TEXT DEFAULT 'Non-Vegetarian',
        avoid_items TEXT DEFAULT '[]',
        health_goals TEXT DEFAULT '[]',
        budget_target REAL DEFAULT 50.0,
        currency TEXT DEFAULT '₹',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Scanned Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        device_id TEXT,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        packet_price REAL DEFAULT 0.0,
        servings REAL DEFAULT 1.0,
        cost_per_serving REAL DEFAULT 0.0,
        image_path TEXT,
        raw_text TEXT,
        clean_ingredients TEXT,
        overall_score INTEGER DEFAULT 50,
        star_rating REAL DEFAULT 2.5,
        verdict TEXT NOT NULL,
        verdict_badge TEXT DEFAULT 'caution',
        analysis_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Safe migration for existing schemas lacking device_id column
    try:
        cursor.execute("ALTER TABLE scans ADD COLUMN device_id TEXT")
    except Exception:
        pass

    conn.commit()
    conn.close()

def get_user_by_id(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        user = dict(row)
        user['allergies'] = json.loads(user['allergies'] or '[]')
        user['custom_allergies'] = json.loads(user.get('custom_allergies') or '[]') if 'custom_allergies' in user else []
        user['avoid_items'] = json.loads(user['avoid_items'] or '[]')
        user['health_goals'] = json.loads(user['health_goals'] or '[]')
        user['custom_goals'] = json.loads(user.get('custom_goals') or '[]') if 'custom_goals' in user else []
        return user
    return None

def get_user_by_username(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        user = dict(row)
        user['allergies'] = json.loads(user['allergies'] or '[]')
        user['custom_allergies'] = json.loads(user.get('custom_allergies') or '[]') if 'custom_allergies' in user else []
        user['avoid_items'] = json.loads(user['avoid_items'] or '[]')
        user['health_goals'] = json.loads(user['health_goals'] or '[]')
        user['custom_goals'] = json.loads(user.get('custom_goals') or '[]') if 'custom_goals' in user else []
        return user
    return None

def get_user_by_email(email):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if row:
        user = dict(row)
        user['allergies'] = json.loads(user['allergies'] or '[]')
        user['custom_allergies'] = json.loads(user.get('custom_allergies') or '[]') if 'custom_allergies' in user else []
        user['avoid_items'] = json.loads(user['avoid_items'] or '[]')
        user['health_goals'] = json.loads(user['health_goals'] or '[]')
        user['custom_goals'] = json.loads(user.get('custom_goals') or '[]') if 'custom_goals' in user else []
        return user
    return None

def create_user(username, email, password_hash, allergies=None, custom_allergies=None,
                dietary_preference='Non-Vegetarian', avoid_items=None, health_goals=None,
                custom_goals=None, budget_target=None, currency='₹'):
    conn = get_db()
    cursor = conn.cursor()
    allergies_json = json.dumps(allergies or [])
    custom_allergies_json = json.dumps(custom_allergies or [])
    avoid_items_json = json.dumps(avoid_items or [])
    health_goals_json = json.dumps(health_goals or [])
    custom_goals_json = json.dumps(custom_goals or [])

    cursor.execute("""
    INSERT INTO users (username, email, password_hash, allergies, dietary_preference, avoid_items, health_goals, budget_target, currency)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (username, email, password_hash, allergies_json, dietary_preference, avoid_items_json, health_goals_json, budget_target, currency))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id

def restore_user_from_session(user_profile):
    """
    Restores or synchronizes an authenticated user from a signed session
    into the current SQLite database (essential for serverless lambda instances on Vercel).
    """
    if not user_profile or "id" not in user_profile:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ? AND username = ?", (user_profile["id"], user_profile.get("username")))
    if cursor.fetchone():
        conn.close()
        return user_profile["id"]

    allergies_json = json.dumps(user_profile.get("allergies", []))
    avoid_items_json = json.dumps(user_profile.get("avoid_items", []))
    health_goals_json = json.dumps(user_profile.get("health_goals", []))

    try:
        # Remove any existing conflicting records for this username/email
        cursor.execute("DELETE FROM users WHERE username = ? OR email = ?", (
            user_profile.get("username", "user"),
            user_profile.get("email", "user@example.com")
        ))
        cursor.execute("""
        INSERT OR REPLACE INTO users (
            id, username, email, password_hash, allergies, dietary_preference,
            avoid_items, health_goals, budget_target, currency
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_profile["id"],
            user_profile.get("username", "user"),
            user_profile.get("email", "user@example.com"),
            user_profile.get("password_hash", "session_auth"),
            allergies_json,
            user_profile.get("dietary_preference", "Non-Vegetarian"),
            avoid_items_json,
            health_goals_json,
            user_profile.get("budget_target", 50.0),
            user_profile.get("currency", "₹")
        ))
        conn.commit()
    except Exception as e:
        print(f"Error restoring user in database: {e}")
    finally:
        conn.close()
    return user_profile["id"]

def update_user_profile(user_id, allergies, dietary_preference, avoid_items, health_goals,
                        budget_target=None, currency='₹', custom_allergies=None, custom_goals=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE users SET
        allergies = ?,
        dietary_preference = ?,
        avoid_items = ?,
        health_goals = ?,
        budget_target = ?,
        currency = ?
    WHERE id = ?
    """, (json.dumps(allergies), dietary_preference, json.dumps(avoid_items), json.dumps(health_goals), budget_target, currency, user_id))
    conn.commit()
    conn.close()

def get_scans_by_ids(scan_ids):
    if not scan_ids:
        return []
    conn = get_db()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in scan_ids)
    cursor.execute(f"SELECT * FROM scans WHERE id IN ({placeholders})", scan_ids)
    rows = cursor.fetchall()
    conn.close()
    scans_dict = {}
    for r in rows:
        d = dict(r)
        d['analysis'] = json.loads(d['analysis_json'])
        scans_dict[d['id']] = d
    # Preserve order requested
    return [scans_dict[sid] for sid in scan_ids if sid in scans_dict]

def save_scan(user_id, product_name, category, packet_price, servings, cost_per_serving,
              image_path, raw_text, clean_ingredients, overall_score, star_rating, verdict, verdict_badge, analysis_dict,
              device_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO scans (
        user_id, device_id, product_name, category, packet_price, servings, cost_per_serving,
        image_path, raw_text, clean_ingredients, overall_score, star_rating, verdict, verdict_badge, analysis_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, device_id, product_name, category, packet_price, servings, cost_per_serving,
        image_path, raw_text, clean_ingredients, overall_score, star_rating, verdict, verdict_badge, json.dumps(analysis_dict)
    ))
    scan_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return scan_id

def get_scan_by_id(scan_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scans WHERE id = ?", (scan_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        scan = dict(row)
        scan['analysis'] = json.loads(scan['analysis_json'])
        return scan
    return None

def claim_device_scans_for_user(user_id, device_id):
    """
    Associates any previous anonymous scans made on this device with the user's account.
    """
    if not user_id or not device_id:
        return
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE scans SET user_id = ? WHERE device_id = ? AND user_id IS NULL", (user_id, device_id))
    conn.commit()
    conn.close()

def restore_scans_from_session(scans_list):
    """
    Restores or synchronizes scans from session or client storage into the current container SQLite DB.
    Ensures scans persist across ephemeral serverless micro-VMs on Vercel.
    """
    if not scans_list:
        return
    conn = get_db()
    cursor = conn.cursor()
    for s in scans_list:
        if not s or not s.get("product_name"):
            continue
        try:
            cursor.execute("SELECT id FROM scans WHERE id = ?", (s.get("id"),))
            if cursor.fetchone():
                continue

            analysis_val = s.get("analysis") or s.get("analysis_result") or {}
            if isinstance(analysis_val, dict):
                analysis_json = json.dumps(analysis_val)
            else:
                analysis_json = str(analysis_val)

            cursor.execute("""
            INSERT OR REPLACE INTO scans (
                id, user_id, device_id, product_name, category, packet_price,
                servings, cost_per_serving, image_path, raw_text, clean_ingredients,
                overall_score, star_rating, verdict, verdict_badge, analysis_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s.get("id"),
                s.get("user_id"),
                s.get("device_id"),
                s.get("product_name"),
                s.get("category", "General Packaged Food"),
                s.get("packet_price", 0.0) or 0.0,
                s.get("servings", 1.0) or 1.0,
                s.get("cost_per_serving", 0.0) or 0.0,
                s.get("image_path"),
                s.get("raw_text", ""),
                s.get("clean_ingredients", ""),
                s.get("overall_score", 50) or 50,
                s.get("star_rating", 2.5) or 2.5,
                s.get("verdict", "Evaluated"),
                s.get("verdict_badge", "caution"),
                analysis_json,
                s.get("created_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            ))
        except Exception as e:
            print(f"Error restoring scan: {e}")
    conn.commit()
    conn.close()

def get_user_scans(user_id=None, device_id=None, limit=50):
    conn = get_db()
    cursor = conn.cursor()
    if user_id and device_id:
        # Show all scans associated with this user profile OR this physical device
        cursor.execute("""
            SELECT * FROM scans 
            WHERE user_id = ? OR device_id = ? 
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, device_id, limit))
    elif user_id:
        cursor.execute("SELECT * FROM scans WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
    elif device_id:
        cursor.execute("SELECT * FROM scans WHERE device_id = ? ORDER BY created_at DESC LIMIT ?", (device_id, limit))
    else:
        cursor.execute("SELECT * FROM scans WHERE 1 = 0")
    rows = cursor.fetchall()
    conn.close()
    scans = []
    for r in rows:
        d = dict(r)
        d['analysis'] = json.loads(d['analysis_json']) if d.get('analysis_json') else {}
        scans.append(d)
    return scans

def get_scans_by_category(category, exclude_id=None, limit=10):
    conn = get_db()
    cursor = conn.cursor()
    if exclude_id:
        cursor.execute("SELECT * FROM scans WHERE category = ? AND id != ? ORDER BY created_at DESC LIMIT ?", (category, exclude_id, limit))
    else:
        cursor.execute("SELECT * FROM scans WHERE category = ? ORDER BY created_at DESC LIMIT ?", (category, limit))
    rows = cursor.fetchall()
    conn.close()
    scans = []
    for r in rows:
        d = dict(r)
        d['analysis'] = json.loads(d['analysis_json'])
        scans.append(d)
    return scans

def update_scan(scan_id, product_name, category, packet_price, servings, cost_per_serving,
                raw_text, clean_ingredients, overall_score, star_rating, verdict, verdict_badge, analysis_dict):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE scans SET
        product_name = ?,
        category = ?,
        packet_price = ?,
        servings = ?,
        cost_per_serving = ?,
        raw_text = ?,
        clean_ingredients = ?,
        overall_score = ?,
        star_rating = ?,
        verdict = ?,
        verdict_badge = ?,
        analysis_json = ?
    WHERE id = ?
    """, (
        product_name, category, packet_price, servings, cost_per_serving,
        raw_text, clean_ingredients, overall_score, star_rating, verdict, verdict_badge,
        json.dumps(analysis_dict), scan_id
    ))
    conn.commit()
    conn.close()

def delete_scan(scan_id, user_id=None, device_id=None):
    conn = get_db()
    cursor = conn.cursor()
    if user_id:
        # A logged-in user can delete their own scan, or any unassigned scan from their device
        if device_id:
            cursor.execute("""
                DELETE FROM scans 
                WHERE id = ? AND (user_id = ? OR (user_id IS NULL AND device_id = ?) OR (user_id IS NULL AND device_id IS NULL))
            """, (scan_id, user_id, device_id))
        else:
            cursor.execute("""
                DELETE FROM scans 
                WHERE id = ? AND (user_id = ? OR (user_id IS NULL AND device_id IS NULL))
            """, (scan_id, user_id))
    elif device_id:
        # An anonymous device session can delete scans created on this device (or legacy unassigned scans)
        cursor.execute("""
            DELETE FROM scans 
            WHERE id = ? AND (device_id = ? OR (device_id IS NULL AND user_id IS NULL))
        """, (scan_id, device_id))
    else:
        cursor.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
