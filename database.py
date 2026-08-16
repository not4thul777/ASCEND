import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_NAME = "ascend.db"

def now_utc():
    return datetime.now(timezone.utc)

def iso_now():
    return now_utc().isoformat()

def connect():
    con = sqlite3.connect(DB_NAME)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = connect()
    cur = con.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY,
        name TEXT DEFAULT 'Player',
        player_id TEXT DEFAULT '',
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        rank TEXT DEFAULT 'E-RANK',
        arena_points INTEGER DEFAULT 1000,
        created_at TEXT DEFAULT '',
        equipped_badge TEXT DEFAULT ''
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_time TEXT,
        category TEXT,
        item TEXT,
        value REAL DEFAULT 0,
        unit TEXT DEFAULT '',
        xp INTEGER DEFAULT 0,
        stat TEXT DEFAULT ''
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        category TEXT,
        target REAL,
        unit TEXT,
        xp INTEGER,
        stat TEXT,
        done INTEGER DEFAULT 0,
        cycle_started TEXT
    )""")

    # Simple migrations for earlier ASCEND databases.
    cols = [r["name"] for r in cur.execute("PRAGMA table_info(profile)").fetchall()]
    if "player_id" not in cols:
        cur.execute("ALTER TABLE profile ADD COLUMN player_id TEXT DEFAULT ''")
    if "arena_points" not in cols:
        cur.execute("ALTER TABLE profile ADD COLUMN arena_points INTEGER DEFAULT 1000")
    if "created_at" not in cols:
        cur.execute("ALTER TABLE profile ADD COLUMN created_at TEXT DEFAULT ''")
    if "equipped_badge" not in cols:
        cur.execute("ALTER TABLE profile ADD COLUMN equipped_badge TEXT DEFAULT ''")

    log_cols = [r["name"] for r in cur.execute("PRAGMA table_info(logs)").fetchall()]
    if "log_time" not in log_cols:
        cur.execute("ALTER TABLE logs ADD COLUMN log_time TEXT DEFAULT ''")
        cur.execute("UPDATE logs SET log_time=log_date || 'T12:00:00+00:00' WHERE log_time IS NULL OR log_time=''")

    quest_cols = [r["name"] for r in cur.execute("PRAGMA table_info(quests)").fetchall()]
    if "cycle_started" not in quest_cols:
        cur.execute("ALTER TABLE quests ADD COLUMN cycle_started TEXT DEFAULT ''")

    profile = cur.execute("SELECT * FROM profile WHERE id=1").fetchone()
    if not profile:
        cur.execute(
            "INSERT INTO profile (name, player_id, arena_points, created_at) VALUES (?,?,?,?)",
            ("Player", make_player_id("Player"), 1000, iso_now())
        )
    elif not profile["player_id"]:
        cur.execute(
            "UPDATE profile SET player_id=? WHERE id=1",
            (make_player_id(profile["name"] or "Player"),)
        )
    if not profile or not profile["created_at"]:
        cur.execute("UPDATE profile SET created_at=? WHERE id=1", (iso_now(),))

    # Convert the original prototype placeholder name into a practical default.
    current_name = (profile["name"] or "").strip() if profile else ""
    if current_name.lower() == "hunter":
        cur.execute("UPDATE profile SET name='Player' WHERE id=1")

    # Normalize progression from lifetime XP for older ASCEND databases.
    p = cur.execute("SELECT xp, level, rank FROM profile WHERE id=1").fetchone()
    if p:
        normalized_level = level_for_xp(p["xp"])
        normalized_rank = rank_for_level(normalized_level)
        cur.execute(
            "UPDATE profile SET level=?, rank=? WHERE id=1",
            (normalized_level, normalized_rank)
        )

    con.commit()
    con.close()

def make_player_id(name):
    clean = "".join(ch for ch in name.upper() if ch.isalnum())[:8] or "PLAYER"
    suffix = str(abs(hash(datetime.now().timestamp())))[-4:]
    return f"{clean}-{suffix}"

def get_profile():
    # Always normalize the displayed level/rank from lifetime XP.
    con = connect()
    row = con.execute("SELECT * FROM profile WHERE id=1").fetchone()
    if row:
        level = level_for_xp(row["xp"])
        rank = rank_for_xp(row["xp"])
        if row["level"] != level or row["rank"] != rank:
            con.execute(
                "UPDATE profile SET level=?, rank=? WHERE id=1",
                (level, rank)
            )
            con.commit()
            row = con.execute("SELECT * FROM profile WHERE id=1").fetchone()
    con.close()
    return row



def set_name(name):
    name = name.strip()[:20]
    if not name:
        return False
    con = connect()
    p = con.execute("SELECT * FROM profile WHERE id=1").fetchone()
    player_id = p["player_id"] or make_player_id(name)
    con.execute("UPDATE profile SET name=?, player_id=? WHERE id=1", (name, player_id))
    con.commit()
    con.close()
    return True

def rank_for_xp(total_xp):
    """Rank is based directly on lifetime XP and can never reset."""
    thresholds = [
        (0, "E-RANK"),
        (1500, "D-RANK"),
        (4000, "C-RANK"),
        (8000, "B-RANK"),
        (14000, "A-RANK"),
        (22000, "S-RANK"),
        (35000, "NATIONAL"),
    ]
    rank = "E-RANK"
    for minimum, name in thresholds:
        if total_xp >= minimum:
            rank = name
    return rank



def rank_for_level(level):
    thresholds = [
        (1, "E-RANK"), (5, "D-RANK"), (10, "C-RANK"),
        (20, "B-RANK"), (35, "A-RANK"), (50, "S-RANK"),
        (75, "NATIONAL")
    ]
    rank = "E-RANK"
    for minimum, name in thresholds:
        if level >= minimum:
            rank = name
    return rank



def level_for_xp(total_xp):
    """Convert lifetime XP to a stable level using cumulative thresholds."""
    level = 1
    spent = 0
    while True:
        # Increasing effort per level: 250, 350, 450...
        needed = 250 + (level - 1) * 100
        if total_xp < spent + needed:
            break
        spent += needed
        level += 1
    return level

def current_rank():
    con = connect()
    row = con.execute("SELECT xp, rank FROM profile WHERE id=1").fetchone()
    con.close()
    return rank_for_xp(row["xp"] if row else 0)

def add_xp(amount):
    con = connect()
    p = con.execute("SELECT * FROM profile WHERE id=1").fetchone()

    old_level = int(p["level"])
    old_rank = p["rank"]

    total = int(p["xp"]) + int(amount)
    new_level = level_for_xp(total)
    new_rank = rank_for_xp(total)

    con.execute(
        "UPDATE profile SET xp=?, level=?, rank=? WHERE id=1",
        (total, new_level, new_rank)
    )
    con.commit()
    con.close()

    return {
        "leveled_up": new_level > old_level,
        "ranked_up": new_rank != old_rank,
        "level": new_level,
        "rank": new_rank,
        "xp": total,
    }



def recalculate_progression():
    con = connect()
    p = con.execute("SELECT xp FROM profile WHERE id=1").fetchone()
    if p:
        level = level_for_xp(p["xp"])
        rank = rank_for_xp(p["xp"])
        con.execute(
            "UPDATE profile SET level=?, rank=? WHERE id=1",
            (level, rank)
        )
        con.commit()
    con.close()



def badge_minimum_rank(badge_name):
    order = {
        "E-RANK": 0, "D-RANK": 1, "C-RANK": 2,
        "B-RANK": 3, "A-RANK": 4, "S-RANK": 5, "NATIONAL": 6
    }
    return order.get(badge_name, 99)

def badge_unlocked(badge_rank, player_rank):
    order = {
        "E-RANK": 0, "D-RANK": 1, "C-RANK": 2,
        "B-RANK": 3, "A-RANK": 4, "S-RANK": 5, "NATIONAL": 6
    }
    return order.get(player_rank, 0) >= order.get(badge_rank, 99)

def get_equipped_badge():
    con = connect()
    row = con.execute("SELECT equipped_badge FROM profile WHERE id=1").fetchone()
    con.close()
    return row["equipped_badge"] if row else ""

def equip_badge(badge_rank):
    con = connect()
    p = con.execute("SELECT rank FROM profile WHERE id=1").fetchone()
    if not p or not badge_unlocked(badge_rank, p["rank"]):
        con.close()
        return False
    con.execute("UPDATE profile SET equipped_badge=? WHERE id=1", (badge_rank,))
    con.commit()
    con.close()
    return True

def add_arena_points(amount):
    con = connect()
    p = con.execute("SELECT arena_points FROM profile WHERE id=1").fetchone()
    new_points = max(0, (p["arena_points"] or 1000) + int(amount))
    con.execute("UPDATE profile SET arena_points=? WHERE id=1", (new_points,))
    con.commit()
    con.close()

def add_arena_points(amount):
    con = connect()
    p = con.execute("SELECT arena_points FROM profile WHERE id=1").fetchone()
    new_points = max(0, (p["arena_points"] or 1000) + int(amount))
    con.execute("UPDATE profile SET arena_points=? WHERE id=1", (new_points,))
    con.commit()
    con.close()

def add_log(category, item, value, unit, xp, stat, extra=None):
    con = connect()
    con.execute(
        """INSERT INTO logs
        (log_time, category, item, value, unit, xp, stat)
        VALUES (?,?,?,?,?,?,?)""",
        (iso_now(), category, item, value, unit, xp, stat)
    )
    con.commit()
    con.close()
    return add_xp(xp)


def today_logs():
    # Kept for compatibility; now means current 24-hour window.
    start = (now_utc() - timedelta(hours=24)).isoformat()
    con = connect()
    rows = con.execute(
        "SELECT * FROM logs WHERE log_time>=? ORDER BY id DESC", (start,)
    ).fetchall()
    con.close()
    return rows

def logs_for_category(category, days=30):
    start = (now_utc() - timedelta(days=days)).isoformat()
    con = connect()
    rows = con.execute(
        """SELECT * FROM logs
           WHERE category=? AND log_time>=?
           ORDER BY id ASC""",
        (category, start)
    ).fetchall()
    con.close()
    return rows

def gym_history():
    con = connect()
    rows = con.execute(
        """SELECT log_time, item, value, unit, xp
           FROM logs
           WHERE category='Gym'
           ORDER BY id ASC"""
    ).fetchall()
    con.close()
    return rows

def gym_summary():
    rows = gym_history()
    if not rows:
        return {"sessions": 0, "best_weight": 0, "first_weight": 0, "improvement": 0}
    weights = [float(r["value"]) for r in rows if r["unit"] == "kg"]
    first = weights[0] if weights else 0
    best = max(weights) if weights else 0
    return {
        "sessions": len(rows),
        "best_weight": best,
        "first_weight": first,
        "improvement": best - first
    }

def category_totals_24h():
    start = (now_utc() - timedelta(hours=24)).isoformat()
    con = connect()
    rows = con.execute(
        "SELECT category, SUM(value) total FROM logs WHERE log_time>=? GROUP BY category",
        (start,)
    ).fetchall()
    con.close()
    return {r["category"]: r["total"] for r in rows}

def stat_totals():
    con = connect()
    rows = con.execute(
        "SELECT stat, SUM(xp) total FROM logs WHERE stat!='' GROUP BY stat"
    ).fetchall()
    con.close()
    return {r["stat"]: int(r["total"] or 0) for r in rows}

def quest_cycle():
    """Quest cycle resets exactly every 24 hours based on the cycle start."""
    con = connect()
    row = con.execute(
        "SELECT MIN(cycle_started) start FROM quests"
    ).fetchone()
    con.close()
    if not row or not row["start"]:
        return None
    try:
        return datetime.fromisoformat(row["start"])
    except ValueError:
        return None

def seed_quests():
    con = connect()
    now = now_utc()

    row = con.execute(
        "SELECT cycle_started FROM quests ORDER BY id DESC LIMIT 1"
    ).fetchone()

    cycle = None
    if row and row["cycle_started"]:
        try:
            cycle = datetime.fromisoformat(row["cycle_started"])
        except (ValueError, TypeError):
            cycle = None

    needs_reset = cycle is None or (now - cycle) >= timedelta(hours=24)

    if needs_reset:
        # Delete the previous cycle completely so its DONE flags cannot carry over.
        con.execute("DELETE FROM quests")
        started = now.isoformat()

        data = [
            ("IRON BODY", "Gym", 1, "workout", 35, "STR"),
            ("FOCUS MODE", "Study", 2, "hours", 25, "INT"),
            ("SOCIAL RAID", "Social", 5, "people", 20, "SOC"),
        ]

        con.executemany(
            """INSERT INTO quests
            (title, category, target, unit, xp, stat, done, cycle_started)
            VALUES (?,?,?,?,?,?,0,?)""",
            [item + (started,) for item in data]
        )
        con.commit()

    con.close()

def quests_today():
    seed_quests()
    con = connect()
    rows = con.execute("SELECT * FROM quests ORDER BY id").fetchall()
    con.close()
    return rows

def quest_time_left():
    cycle = quest_cycle()
    if cycle is None:
        return timedelta(hours=24)
    end = cycle + timedelta(hours=24)
    remaining = end - now_utc()
    return max(remaining, timedelta(0))

def quest_progress(q):
    """Return actual progress for a quest from logs in the current 24h cycle."""
    cycle = None
    try:
        if q["cycle_started"]:
            cycle = datetime.fromisoformat(q["cycle_started"])
    except (ValueError, TypeError):
        cycle = None

    if cycle is None:
        return 0.0

    con = connect()
    rows = con.execute(
        """SELECT category, item, value, unit
           FROM logs
           WHERE log_time>=? AND category=?""",
        (cycle.isoformat(), q["category"])
    ).fetchall()
    con.close()

    if q["category"] == "Gym":
        # One or more workout logs count toward the workout quest.
        return min(float(q["target"]), float(len(rows)))

    if q["category"] == "Study":
        return min(float(q["target"]),
                   sum(float(r["value"]) for r in rows if r["unit"] == "hours"))

    if q["category"] == "Social":
        return min(float(q["target"]),
                   sum(float(r["value"]) for r in rows if r["unit"] == "people"))

    return 0.0


def complete_quest(qid):
    seed_quests()
    con = connect()
    row = con.execute("SELECT * FROM quests WHERE id=?", (qid,)).fetchone()
    con.close()

    if not row or row["done"]:
        return 0, False

    progress = quest_progress(row)
    if progress < float(row["target"]):
        return 0, False

    con = connect()
    con.execute("UPDATE quests SET done=1 WHERE id=?", (qid,))
    con.commit()
    con.close()

    progress_event = add_xp(row["xp"])
    add_arena_points(max(2, row["xp"] // 8))
    return row["xp"], progress_event
