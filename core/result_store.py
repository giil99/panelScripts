"""
ResultStore — Disk-based storage for large execution results.

Instead of holding 1M+ rows as Python objects in session_state (1-2 GB RAM),
results are persisted to a temp SQLite file as soon as execution completes.
All subsequent operations read only what they need via SQL.

Key benefits vs in-memory DataFrame:
  • Pagination  → LIMIT/OFFSET — instant, independent of dataset size
  • Charts      → GROUP BY aggregation — accurate (all rows), tiny result sent to browser
  • Exports     → read-then-write, avoids duplicate RAM peak
  • Memory      → Python keeps almost nothing after save(); SQLite uses OS disk cache
"""

import os
import sqlite3
import uuid
import pandas as pd
from typing import Optional

_TABLE = 'result'
_RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'exports')


# ── Write ───────────────────────────────────────────────────────────────────

def save(df: pd.DataFrame, result_id: Optional[str] = None) -> str:
    """
    Persist df to a SQLite file.  Returns the file path.
    All object-dtype columns are cast to str (prevents PyArrow int64 errors).
    """
    if result_id is None:
        result_id = uuid.uuid4().hex[:12]

    os.makedirs(_RESULTS_DIR, exist_ok=True)
    db_path = os.path.join(_RESULTS_DIR, f'result_{result_id}.db')

    # Cast objects → str (also fixes any Salesforce Id columns)
    clean = df.copy()
    for col in clean.select_dtypes(include='object').columns:
        clean[col] = clean[col].astype(str)

    conn = sqlite3.connect(db_path)
    try:
        # index=False — we don't need the pandas index in SQLite
        clean.to_sql(_TABLE, conn, if_exists='replace', index=False)
        # Indexes on common Salesforce columns speed up GROUP BY / filter
        cur = conn.cursor()
        # Create a single integer rowid for fast OFFSET queries
        conn.commit()
    finally:
        conn.close()

    return db_path


# ── Metadata ─────────────────────────────────────────────────────────────────

def count(db_path: str) -> int:
    """Total number of rows."""
    with sqlite3.connect(db_path) as conn:
        return conn.execute(f'SELECT COUNT(*) FROM "{_TABLE}"').fetchone()[0]


def get_columns(db_path: str) -> list:
    """Column names in insertion order."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f'PRAGMA table_info("{_TABLE}")').fetchall()
        return [r[1] for r in rows]


def get_column_types(db_path: str) -> dict:
    """Map {column_name: sqlite_type_str}."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f'PRAGMA table_info("{_TABLE}")').fetchall()
        return {r[1]: r[2].upper() for r in rows}


# ── Read ─────────────────────────────────────────────────────────────────────

def read_page(db_path: str, page: int, page_size: int,
              filters: Optional[dict] = None) -> pd.DataFrame:
    """
    Return a single page of rows.
    filters: {col: [val1, val2, ...]}  →  WHERE col IN (val1, val2, ...)
    """
    where, params = _build_where(filters)
    sql = f'SELECT * FROM "{_TABLE}"{where} LIMIT ? OFFSET ?'
    params += [page_size, page * page_size]
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def count_filtered(db_path: str, filters: Optional[dict] = None) -> int:
    """Row count after applying filters."""
    where, params = _build_where(filters)
    sql = f'SELECT COUNT(*) FROM "{_TABLE}"{where}'
    with sqlite3.connect(db_path) as conn:
        return conn.execute(sql, params).fetchone()[0]


def get_distinct_values(db_path: str, col: str, limit: int = 200) -> list:
    """
    Distinct values for a column — for filter dropdowns.
    Fast: SQLite B-tree scan, never touches Python objects.
    """
    c = _q(col)
    sql = f'SELECT DISTINCT {c} FROM "{_TABLE}" WHERE {c} IS NOT NULL ORDER BY {c} LIMIT ?'
    with sqlite3.connect(db_path) as conn:
        return [r[0] for r in conn.execute(sql, [limit]).fetchall()]


def get_categorical_values(db_path: str, col: str, max_vals: int = 200) -> list:
    """
    Returns a list of distinct values if the column has <= max_vals unique values.
    Returns None if there are > max_vals (high cardinality).
    This is extremely fast for high-cardinality columns because the query short-circuits.
    """
    c = _q(col)
    sql = f'SELECT DISTINCT {c} FROM "{_TABLE}" WHERE {c} IS NOT NULL LIMIT ?'
    with sqlite3.connect(db_path) as conn:
        vals = [r[0] for r in conn.execute(sql, [max_vals + 1]).fetchall()]
    
    if len(vals) > max_vals:
        return None  # Too many unique values
    return sorted(vals, key=lambda x: str(x) if x is not None else "")


# ── Aggregations (all rows, no sampling) ────────────────────────────────────

def aggregate_counts(db_path: str, col: str, top_n: int = 200) -> pd.DataFrame:
    """
    GROUP BY col → COUNT(*).  Reflects ALL rows accurately.
    Returns tiny DataFrame [col, 'Cantidad'] — safe to send to Plotly.
    """
    c = _q(col)
    sql = (f'SELECT {c} AS __val, COUNT(*) AS Cantidad '
           f'FROM "{_TABLE}" GROUP BY {c} '
           f'ORDER BY Cantidad DESC LIMIT ?')
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(sql, conn, params=[top_n])
    df.columns = [col, 'Cantidad']
    return df


def aggregate_numeric_stats(db_path: str, col: str) -> dict:
    """MIN / MAX / AVG / COUNT for a numeric column."""
    c = _q(col)
    sql = (f'SELECT COUNT({c}), AVG({c}), MIN({c}), MAX({c}) '
           f'FROM "{_TABLE}" WHERE {c} IS NOT NULL')
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(sql).fetchone()
    return {'count': row[0], 'mean': row[1], 'min': row[2], 'max': row[3]}


def aggregate_histogram(db_path: str, col: str, bins: int = 30) -> pd.DataFrame:
    """
    Compute histogram bin counts in SQL — no Python data needed.
    Returns DataFrame [BinCenter, Cantidad].
    """
    c = _q(col)
    with sqlite3.connect(db_path) as conn:
        mn, mx = conn.execute(
            f'SELECT MIN({c}), MAX({c}) FROM "{_TABLE}" WHERE {c} IS NOT NULL'
        ).fetchone()
        if mn is None or mn == mx:
            return pd.DataFrame({'BinCenter': [], 'Cantidad': []})
        width = (mx - mn) / bins
        sql = (
            f'SELECT CAST(CAST(({c} - {mn}) / {width} AS INTEGER) AS REAL) AS bin, '
            f'COUNT(*) AS Cantidad '
            f'FROM "{_TABLE}" WHERE {c} IS NOT NULL '
            f'GROUP BY bin ORDER BY bin'
        )
        df = pd.read_sql_query(sql, conn)
    df['BinCenter'] = mn + (df['bin'].clip(0, bins - 1) + 0.5) * width
    return df[['BinCenter', 'Cantidad']]


def groupby_agg(db_path: str, group_col: str, agg_col: str, agg_func: str,
                top_n: int = 100) -> pd.DataFrame:
    """GROUP BY + aggregate — returns compact result for display/chart."""
    gc, ac = _q(group_col), _q(agg_col)
    func_map = {'count': 'COUNT', 'sum': 'SUM', 'mean': 'AVG', 'max': 'MAX', 'min': 'MIN'}
    fn = func_map.get(agg_func, 'COUNT')
    label = f'{agg_func.title()} de {agg_col}'
    sql = (f'SELECT {gc}, {fn}({ac}) AS val '
           f'FROM "{_TABLE}" GROUP BY {gc} ORDER BY val DESC LIMIT ?')
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(sql, conn, params=[top_n])
    df.columns = [group_col, label]
    return df


def column_unique_count(db_path: str, col: str) -> int:
    """COUNT(DISTINCT col) — used for analysis KPIs."""
    c = _q(col)
    # Fast path: check if it exceeds 10,000 to avoid full table scan on huge tables if not needed
    # But for an exact KPI we need the full scan... 
    # Since KPIs only run on the first 3 columns, it's acceptable to full scan.
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            f'SELECT COUNT(DISTINCT {c}) FROM "{_TABLE}"'
        ).fetchone()[0]


# ── Export ───────────────────────────────────────────────────────────────────

def export_csv_bytes(db_path: str, max_rows: int,
                     filters: Optional[dict] = None) -> bytes:
    """Read up to max_rows and return CSV bytes."""
    where, params = _build_where(filters)
    sql = f'SELECT * FROM "{_TABLE}"{where} LIMIT ?'
    params.append(max_rows)
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    return df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')


def export_excel_bytes(db_path: str, max_rows: int,
                       filters: Optional[dict] = None) -> bytes:
    """Read up to max_rows and return Excel bytes."""
    from io import BytesIO
    where, params = _build_where(filters)
    sql = f'SELECT * FROM "{_TABLE}"{where} LIMIT ?'
    params.append(max_rows)
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return buf.getvalue()


# ── Cleanup ──────────────────────────────────────────────────────────────────

def cleanup(db_path: str) -> None:
    """Delete the SQLite file (call when result is no longer needed)."""
    try:
        if db_path and os.path.exists(db_path):
            os.remove(db_path)
    except OSError:
        pass


def cleanup_old(max_files: int = 10) -> None:
    """Keep only the N most recent result files to free disk space."""
    if not os.path.isdir(_RESULTS_DIR):
        return
    files = sorted(
        [os.path.join(_RESULTS_DIR, f)
         for f in os.listdir(_RESULTS_DIR)
         if f.startswith('result_') and f.endswith('.db')],
        key=os.path.getmtime
    )
    for old in files[:-max_files]:
        try:
            os.remove(old)
        except OSError:
            pass


# ── Helpers ──────────────────────────────────────────────────────────────────

def _q(col: str) -> str:
    """Quote a column name for SQLite."""
    return '"' + col.replace('"', '""') + '"'


def _build_where(filters: Optional[dict]) -> tuple:
    """Build WHERE clause.  Returns (sql_fragment, params_list)."""
    if not filters:
        return '', []
    clauses, params = [], []
    for col, values in filters.items():
        if not values:
            continue
        placeholders = ','.join('?' * len(values))
        clauses.append(f'{_q(col)} IN ({placeholders})')
        params.extend([str(v) for v in values])
    if not clauses:
        return '', []
    return ' WHERE ' + ' AND '.join(clauses), params
