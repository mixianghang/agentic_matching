"""
Dynamic Schema Registry — runtime demand type management.

Replaces the V1 hardcoded TEMPLATE_REGISTRY (backend/demand_templates.py).
DemandSchema records are persisted in a demand_schemas SQLite table and can be
created, queried, and evolved at runtime. Three default schemas (rental_v1,
dating_v1, gaming_v1) are seeded on first use.

New schema lifecycle:
    1. LLM proposes a schema (status="pending") when a novel demand type is encountered.
    2. After 3 successful uses, auto-activated to status="active".
    3. Active schemas are returned by list_active() and used for matching.

Singleton pattern ensures all modules share the same registry instance.

Design doc: design/demand_definition_design_v2.0.md §2.3
"""
import json
import sqlite3
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional
from threading import Lock

from backend.demand_models import DemandSchema, SchemaField, MatchingDimension

logger = logging.getLogger(__name__)


class SchemaRegistry:
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            return
        self._initialized = True
        self._schemas: Dict[str, DemandSchema] = {}
        self._db_path = db_path or os.getenv("DATABASE_URL", "agentic_matching.db")
        self._conn: Optional[sqlite3.Connection] = None
        try:
            self._init_db()
            self._load_all()
        except Exception as e:
            logger.warning(f"SchemaRegistry DB init failed, using in-memory: {e}")
            self._seed_defaults()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS demand_schemas (
                schema_id TEXT PRIMARY KEY,
                data_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_demand_schemas_type
            ON demand_schemas(schema_id)
        """)
        conn.commit()

    def _load_all(self):
        conn = self._get_conn()
        rows = conn.execute("SELECT data_json FROM demand_schemas").fetchall()
        for row in rows:
            schema = DemandSchema.from_dict(json.loads(row["data_json"]))
            self._schemas[schema.schema_id] = schema
        if not self._schemas:
            self._seed_defaults()

    def _seed_defaults(self):
        defaults = _build_default_schemas()
        for schema in defaults:
            self._schemas[schema.schema_id] = schema
            try:
                conn = self._get_conn()
                conn.execute(
                    "INSERT OR REPLACE INTO demand_schemas (schema_id, data_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (schema.schema_id, json.dumps(schema.to_dict(), ensure_ascii=False),
                     schema.created_at.isoformat(), schema.updated_at.isoformat()),
                )
                conn.commit()
            except Exception:
                pass

    def register(self, schema: DemandSchema) -> DemandSchema:
        schema.updated_at = datetime.now()
        self._schemas[schema.schema_id] = schema
        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO demand_schemas (schema_id, data_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (schema.schema_id, json.dumps(schema.to_dict(), ensure_ascii=False),
                 schema.created_at.isoformat(), schema.updated_at.isoformat()),
            )
            conn.commit()
        except Exception as e:
            logger.warning(f"SchemaRegistry persist failed: {e}")
        return schema

    def get(self, schema_id: str) -> Optional[DemandSchema]:
        return self._schemas.get(schema_id)

    def get_by_type(self, demand_type: str) -> List[DemandSchema]:
        return [s for s in self._schemas.values() if s.demand_type == demand_type and s.status == "active"]

    def list_all(self) -> List[DemandSchema]:
        return list(self._schemas.values())

    def list_active(self) -> List[DemandSchema]:
        return [s for s in self._schemas.values() if s.status == "active"]

    def list_by_status(self, status: str) -> List[DemandSchema]:
        return [s for s in self._schemas.values() if s.status == status]

    def increment_usage(self, schema_id: str) -> Optional[DemandSchema]:
        schema = self._schemas.get(schema_id)
        if schema:
            schema.usage_count += 1
            schema.updated_at = datetime.now()
            if schema.usage_count >= 3 and schema.status == "pending":
                schema.status = "active"
            try:
                conn = self._get_conn()
                conn.execute(
                    "UPDATE demand_schemas SET data_json = ?, updated_at = ? WHERE schema_id = ?",
                    (json.dumps(schema.to_dict(), ensure_ascii=False),
                     schema.updated_at.isoformat(), schema_id),
                )
                conn.commit()
            except Exception:
                pass
        return schema

    def delete(self, schema_id: str) -> bool:
        if schema_id in self._schemas:
            del self._schemas[schema_id]
            try:
                conn = self._get_conn()
                conn.execute("DELETE FROM demand_schemas WHERE schema_id = ?", (schema_id,))
                conn.commit()
            except Exception:
                pass
            return True
        return False

    def reset_for_test(self):
        self._schemas.clear()
        self._seed_defaults()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


def schema_registry(db_path: str = None) -> SchemaRegistry:
    return SchemaRegistry(db_path)


def _build_default_schemas() -> List[DemandSchema]:
    now = datetime.now()
    return [
        DemandSchema(
            schema_id="rental_v1",
            demand_type="rental",
            roles=["tenant", "landlord"],
            fields=[
                SchemaField(key="property_type", display_name="房源类型", value_type="enum", options=["apartment", "house", "studio", "room", "any"], prompt="您想租什么类型的房子？", required=True, matching_dimension="property_type"),
                SchemaField(key="bedrooms", display_name="卧室数量", value_type="integer", prompt="您需要几间卧室？", required=True, matching_dimension="bedrooms_match"),
                SchemaField(key="max_price", display_name="预算上限", value_type="price", prompt="您的预算是多少（每周）？", required=True, matching_dimension="price_compat"),
                SchemaField(key="location", display_name="位置", value_type="geo", prompt="您希望住在哪里？", required=True, matching_dimension="city_match"),
                SchemaField(key="move_in_date", display_name="入住时间", value_type="date", prompt="计划什么时候入住？", required=True),
                SchemaField(key="furnished", display_name="家具", value_type="enum", options=["furnished", "unfurnished", "partial", "any"], prompt="需要带家具吗？", required=False),
                SchemaField(key="parking", display_name="车位", value_type="boolean", prompt="需要停车位吗？", required=False),
            ],
            matching_dimensions=[
                MatchingDimension(dimension_id="city_match", name="城市匹配", field_keys={"tenant": ["location"], "landlord": ["address"]}, comparator="geo_proximity", weight=0.30, is_hard_filter=True),
                MatchingDimension(dimension_id="bedrooms_match", name="卧室匹配", field_keys={"tenant": ["bedrooms"], "landlord": ["bedrooms"]}, comparator="exact", weight=0.25),
                MatchingDimension(dimension_id="price_compat", name="价格兼容", field_keys={"tenant": ["max_price"], "landlord": ["price"]}, comparator="numeric_compatibility", weight=0.30),
                MatchingDimension(dimension_id="property_type", name="房源类型", field_keys={"tenant": ["property_type"], "landlord": ["property_type"]}, comparator="enum_compatible", weight=0.15),
            ],
            status="active", usage_count=5, created_at=now, updated_at=now,
        ),
        DemandSchema(
            schema_id="dating_v1",
            demand_type="dating",
            roles=["seeker"],
            fields=[
                SchemaField(key="gender_preference", display_name="对方性别", value_type="enum", options=["male", "female", "any"], prompt="您希望对方的性别是？", required=True, matching_dimension="gender_match"),
                SchemaField(key="age_range", display_name="年龄范围", value_type="range", prompt="您希望对方年龄在什么范围？", required=True, matching_dimension="age_overlap"),
                SchemaField(key="location", display_name="位置", value_type="geo", prompt="您希望对方在哪个城市？", required=True, matching_dimension="city_match"),
                SchemaField(key="purpose", display_name="交友目的", value_type="enum", options=["marriage", "long_term", "short_term", "friendship"], prompt="交友目的是？", required=True),
                SchemaField(key="education", display_name="学历", value_type="enum", options=["high_school", "bachelor", "master", "phd", "any"], prompt="学历要求？", required=False),
                SchemaField(key="hobbies", display_name="爱好", value_type="tags", prompt="希望对方有什么爱好？", required=False),
            ],
            matching_dimensions=[
                MatchingDimension(dimension_id="gender_match", name="性别匹配", field_keys={"seeker": ["gender_preference"]}, comparator="enum_compatible", weight=0.45, is_hard_filter=True),
                MatchingDimension(dimension_id="age_overlap", name="年龄重叠", field_keys={"seeker": ["age_range"]}, comparator="range_overlap", weight=0.35),
                MatchingDimension(dimension_id="city_match", name="城市匹配", field_keys={"seeker": ["location"]}, comparator="geo_proximity", weight=0.20, is_hard_filter=True),
            ],
            status="active", usage_count=5, created_at=now, updated_at=now,
        ),
        DemandSchema(
            schema_id="gaming_v1",
            demand_type="gaming",
            roles=["player"],
            fields=[
                SchemaField(key="game_name", display_name="游戏", value_type="text", prompt="玩什么游戏？", required=True, matching_dimension="game_match"),
                SchemaField(key="rank", display_name="段位", value_type="text", prompt="什么段位？", required=True, matching_dimension="rank_match"),
                SchemaField(key="play_time", display_name="在线时间", value_type="text", prompt="通常什么时候在线？", required=True),
                SchemaField(key="play_style", display_name="风格", value_type="enum", options=["casual", "competitive", "any"], prompt="游戏风格？", required=False),
            ],
            matching_dimensions=[
                MatchingDimension(dimension_id="game_match", name="游戏匹配", field_keys={"player": ["game_name"]}, comparator="exact", weight=0.85, is_hard_filter=True),
                MatchingDimension(dimension_id="rank_match", name="段位匹配", field_keys={"player": ["rank"]}, comparator="exact", weight=0.15),
            ],
            status="active", usage_count=5, created_at=now, updated_at=now,
        ),
    ]
