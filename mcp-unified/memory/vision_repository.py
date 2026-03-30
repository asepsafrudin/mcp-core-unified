"""
Vision Results Repository Module

Repository untuk operasi CRUD pada tabel vision_results.
Mendukung confidence-based filtering dan integrasi dengan LTM.
"""

import asyncio
import json
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import asdict

import psycopg
from psycopg_pool import AsyncConnectionPool

from observability.logger import logger
from core.secrets import load_runtime_secrets
from core.vision_config import (
    VisionStorageConfig, 
    ProcessingResult, 
    get_config,
    DB_TABLE_CONFIG
)

# Database connection pool (shared dengan longterm.py)
# atau create dedicated pool untuk vision_results

load_runtime_secrets()

DB_PARAMS = {
    'host': os.getenv('POSTGRES_HOST') or os.getenv('PG_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT') or os.getenv('PG_PORT', '5433')),
    'dbname': os.getenv('POSTGRES_DB') or os.getenv('PG_DATABASE', 'mcp_knowledge'),
    'user': os.getenv('POSTGRES_USER') or os.getenv('PG_USER', 'mcp_user'),
    'password': os.getenv('POSTGRES_PASSWORD') or os.getenv('PG_PASSWORD', ''),
    'autocommit': True
}

_pool = None


async def get_pool() -> AsyncConnectionPool:
    """Get or create connection pool"""
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(min_size=2, max_size=10, kwargs=DB_PARAMS, open=False)
        await _pool.open()
    return _pool


async def close_pool():
    """Close connection pool"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# =============================================================================
# CORE CRUD OPERATIONS
# =============================================================================

async def save_vision_result(
    result: ProcessingResult,
    config: VisionStorageConfig = None
) -> Dict[str, Any]:
    """
    Save vision processing result ke database dengan confidence filtering.
    
    Args:
        result: ProcessingResult object dengan data hasil processing
        config: Optional custom configuration
        
    Returns:
        Dict dengan success status dan result details
    """
    if config is None:
        config = get_config()
    
    # Confidence-based filtering
    confidence = result.confidence_score
    storage_decision = config.get_storage_decision(confidence)
    
    logger.info("vision_storage_decision", 
                file=result.file_name,
                confidence=confidence,
                decision=storage_decision)
    
    if storage_decision == 'reject':
        logger.warning("vision_result_rejected_low_confidence",
                      file=result.file_name,
                      confidence=confidence)
        return {
            "success": False,
            "saved_to_sql": False,
            "reason": "confidence_below_threshold",
            "confidence": confidence,
            "threshold": config.get_threshold('medium')
        }
    
    # Prepare data
    table_name = DB_TABLE_CONFIG['table_name']
    
    try:
        pool = await get_pool()
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Check for duplicates jika deduplication enabled
                if config.storage_policy.get('deduplication_enabled', True) and result.file_hash:
                    await cur.execute(f"""
                        SELECT id, confidence_score FROM {table_name}
                        WHERE file_hash = %s AND namespace = %s
                    """, (result.file_hash, result.namespace))
                    
                    existing = await cur.fetchone()
                    
                    if existing:
                        existing_id, existing_confidence = existing
                        
                        if config.storage_policy.get('update_on_duplicate', True):
                            # Update jika confidence lebih tinggi
                            if confidence > existing_confidence:
                                logger.info("updating_existing_record",
                                           existing_id=str(existing_id),
                                           old_confidence=existing_confidence,
                                           new_confidence=confidence)
                                
                                await cur.execute(f"""
                                    UPDATE {table_name} SET
                                        confidence_score = %s,
                                        confidence_threshold = %s,
                                        extracted_text = %s,
                                        extracted_entities = %s,
                                        processing_metadata = %s,
                                        processing_time_ms = %s,
                                        status = %s,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = %s
                                    RETURNING id
                                """, (
                                    confidence,
                                    config.get_threshold('high'),
                                    result.extracted_text,
                                    json.dumps(result.extracted_entities),
                                    json.dumps(result.processing_metadata),
                                    result.processing_time_ms,
                                    result.status,
                                    existing_id
                                ))
                                
                                return {
                                    "success": True,
                                    "saved_to_sql": True,
                                    "operation": "update",
                                    "id": str(existing_id),
                                    "confidence": confidence,
                                    "storage_decision": storage_decision
                                }
                            else:
                                logger.info("skipping_update_lower_confidence",
                                           existing_id=str(existing_id))
                                return {
                                    "success": True,
                                    "saved_to_sql": False,
                                    "operation": "skipped",
                                    "reason": "existing_higher_confidence",
                                    "id": str(existing_id)
                                }
                
                # Insert new record
                await cur.execute(f"""
                    INSERT INTO {table_name} (
                        file_name, file_path, file_hash, file_size_bytes, mime_type,
                        namespace, processing_time_ms,
                        extracted_text, confidence_score, confidence_threshold,
                        processing_method, model_used,
                        document_type, status,
                        extracted_entities, processing_metadata,
                        ltm_key, tenant_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    result.file_name,
                    result.file_path,
                    result.file_hash,
                    result.file_size_bytes,
                    result.mime_type,
                    result.namespace,
                    result.processing_time_ms,
                    result.extracted_text,
                    confidence,
                    config.get_threshold('high'),
                    result.processing_method,
                    result.model_used,
                    result.document_type,
                    result.status,
                    json.dumps(result.extracted_entities),
                    json.dumps(result.processing_metadata),
                    result.ltm_key,
                    result.tenant_id
                ))
                
                row = await cur.fetchone()
                result_id = row[0]
                
                logger.info("vision_result_saved_to_sql",
                           id=str(result_id),
                           file=result.file_name,
                           confidence=confidence)
                
                return {
                    "success": True,
                    "saved_to_sql": True,
                    "operation": "insert",
                    "id": str(result_id),
                    "confidence": confidence,
                    "storage_decision": storage_decision
                }
                
    except Exception as e:
        logger.error("vision_save_to_sql_failed", 
                    error=str(e),
                    file=result.file_name)
        return {
            "success": False,
            "saved_to_sql": False,
            "error": str(e),
            "confidence": confidence
        }


async def get_vision_result_by_id(result_id: str) -> Optional[Dict[str, Any]]:
    """Get single vision result by ID"""
    try:
        pool = await get_pool()
        table_name = DB_TABLE_CONFIG['table_name']
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    SELECT * FROM {table_name}
                    WHERE id = %s
                """, (result_id,))
                
                row = await cur.fetchone()
                
                if row:
                    return _row_to_dict(row, cur.description)
                return None
                
    except Exception as e:
        logger.error("get_vision_result_failed", error=str(e), id=result_id)
        return None


async def get_high_confidence_results(
    min_confidence: float = 0.8,
    namespace: str = "default",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get results with confidence >= threshold
    
    Args:
        min_confidence: Minimum confidence score (default 0.8)
        namespace: Filter by namespace
        limit: Maximum results to return
    """
    try:
        pool = await get_pool()
        table_name = DB_TABLE_CONFIG['table_name']
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    SELECT * FROM {table_name}
                    WHERE confidence_score >= %s
                      AND namespace = %s
                      AND status IN ('success', 'verified')
                    ORDER BY confidence_score DESC, processed_at DESC
                    LIMIT %s
                """, (min_confidence, namespace, limit))
                
                rows = await cur.fetchall()
                return [_row_to_dict(row, cur.description) for row in rows]
                
    except Exception as e:
        logger.error("get_high_confidence_results_failed", error=str(e))
        return []


async def get_results_by_document_type(
    document_type: str,
    namespace: str = "default",
    min_confidence: float = 0.7,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Get results filtered by document type"""
    try:
        pool = await get_pool()
        table_name = DB_TABLE_CONFIG['table_name']
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    SELECT * FROM {table_name}
                    WHERE document_type = %s
                      AND namespace = %s
                      AND confidence_score >= %s
                    ORDER BY processed_at DESC
                    LIMIT %s
                """, (document_type, namespace, min_confidence, limit))
                
                rows = await cur.fetchall()
                return [_row_to_dict(row, cur.description) for row in rows]
                
    except Exception as e:
        logger.error("get_results_by_document_type_failed", 
                    error=str(e), document_type=document_type)
        return []


async def get_results_by_date_range(
    start_date: datetime,
    end_date: datetime,
    namespace: str = "default",
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get results within date range"""
    try:
        pool = await get_pool()
        table_name = DB_TABLE_CONFIG['table_name']
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    SELECT * FROM {table_name}
                    WHERE processed_at BETWEEN %s AND %s
                      AND namespace = %s
                    ORDER BY processed_at DESC
                    LIMIT %s
                """, (start_date, end_date, namespace, limit))
                
                rows = await cur.fetchall()
                return [_row_to_dict(row, cur.description) for row in rows]
                
    except Exception as e:
        logger.error("get_results_by_date_range_failed", error=str(e))
        return []


# =============================================================================
# ANALYTICS & STATS
# =============================================================================

async def get_processing_stats(
    days: int = 30,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Get processing statistics for analytics
    
    Returns:
        Dict dengan summary statistics
    """
    try:
        pool = await get_pool()
        table_name = DB_TABLE_CONFIG['table_name']
        
        start_date = datetime.now() - timedelta(days=days)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Overall stats
                await cur.execute(f"""
                    SELECT 
                        COUNT(*) as total_count,
                        AVG(confidence_score) as avg_confidence,
                        MIN(confidence_score) as min_confidence,
                        MAX(confidence_score) as max_confidence,
                        AVG(processing_time_ms) as avg_processing_time
                    FROM {table_name}
                    WHERE processed_at >= %s
                      AND namespace = %s
                """, (start_date, namespace))
                
                overall = await cur.fetchone()
                
                # By document type
                await cur.execute(f"""
                    SELECT 
                        document_type,
                        COUNT(*) as count,
                        AVG(confidence_score) as avg_confidence
                    FROM {table_name}
                    WHERE processed_at >= %s
                      AND namespace = %s
                    GROUP BY document_type
                    ORDER BY count DESC
                """, (start_date, namespace))
                
                by_type = await cur.fetchall()
                
                # By status
                await cur.execute(f"""
                    SELECT 
                        status,
                        COUNT(*) as count
                    FROM {table_name}
                    WHERE processed_at >= %s
                      AND namespace = %s
                    GROUP BY status
                    ORDER BY count DESC
                """, (start_date, namespace))
                
                by_status = await cur.fetchall()
                
                return {
                    "success": True,
                    "period_days": days,
                    "namespace": namespace,
                    "overall": {
                        "total_count": overall[0] or 0,
                        "avg_confidence": float(overall[1]) if overall[1] else 0,
                        "min_confidence": float(overall[2]) if overall[2] else 0,
                        "max_confidence": float(overall[3]) if overall[3] else 0,
                        "avg_processing_time_ms": float(overall[4]) if overall[4] else 0
                    },
                    "by_document_type": [
                        {"type": row[0], "count": row[1], "avg_confidence": float(row[2])}
                        for row in by_type
                    ],
                    "by_status": [
                        {"status": row[0], "count": row[1]}
                        for row in by_status
                    ]
                }
                
    except Exception as e:
        logger.error("get_processing_stats_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def get_confidence_distribution(
    namespace: str = "default",
    bins: int = 10
) -> List[Dict[str, Any]]:
    """
    Get confidence score distribution untuk visualisasi
    
    Returns:
        List of bins dengan count
    """
    try:
        pool = await get_pool()
        table_name = DB_TABLE_CONFIG['table_name']
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Create bins
                bin_size = 1.0 / bins
                distribution = []
                
                for i in range(bins):
                    min_val = i * bin_size
                    max_val = (i + 1) * bin_size
                    
                    await cur.execute(f"""
                        SELECT COUNT(*) FROM {table_name}
                        WHERE confidence_score >= %s
                          AND confidence_score < %s
                          AND namespace = %s
                    """, (min_val, max_val, namespace))
                    
                    count = (await cur.fetchone())[0]
                    
                    distribution.append({
                        "range": f"{min_val:.1f} - {max_val:.1f}",
                        "min": min_val,
                        "max": max_val,
                        "count": count
                    })
                
                return distribution
                
    except Exception as e:
        logger.error("get_confidence_distribution_failed", error=str(e))
        return []


# =============================================================================
# UPDATE OPERATIONS
# =============================================================================

async def update_vision_status(
    result_id: str,
    new_status: str,
    updated_by: str = "system"
) -> Dict[str, Any]:
    """Update status of a vision result (e.g., verified, rejected)"""
    try:
        pool = await get_pool()
        table_name = DB_TABLE_CONFIG['table_name']
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    UPDATE {table_name}
                    SET status = %s,
                        updated_by = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id
                """, (new_status, updated_by, result_id))
                
                row = await cur.fetchone()
                
                if row:
                    logger.info("vision_status_updated",
                               id=result_id,
                               new_status=new_status)
                    return {
                        "success": True,
                        "id": result_id,
                        "new_status": new_status
                    }
                else:
                    return {
                        "success": False,
                        "error": "Record not found"
                    }
                    
    except Exception as e:
        logger.error("update_vision_status_failed", error=str(e), id=result_id)
        return {"success": False, "error": str(e)}


async def update_ltm_link(
    result_id: str,
    ltm_key: str
) -> Dict[str, Any]:
    """Update LTM key reference untuk linking"""
    try:
        pool = await get_pool()
        table_name = DB_TABLE_CONFIG['table_name']
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    UPDATE {table_name}
                    SET ltm_key = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id
                """, (ltm_key, result_id))
                
                row = await cur.fetchone()
                
                if row:
                    return {
                        "success": True,
                        "id": result_id,
                        "ltm_key": ltm_key
                    }
                else:
                    return {
                        "success": False,
                        "error": "Record not found"
                    }
                    
    except Exception as e:
        logger.error("update_ltm_link_failed", error=str(e))
        return {"success": False, "error": str(e)}


# =============================================================================
# DELETE OPERATIONS
# =============================================================================

async def delete_vision_result(result_id: str) -> Dict[str, Any]:
    """Delete vision result by ID"""
    try:
        pool = await get_pool()
        table_name = DB_TABLE_CONFIG['table_name']
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    DELETE FROM {table_name}
                    WHERE id = %s
                    RETURNING id, file_name
                """, (result_id,))
                
                row = await cur.fetchone()
                
                if row:
                    logger.info("vision_result_deleted",
                               id=result_id,
                               file=row[1])
                    return {
                        "success": True,
                        "deleted_id": result_id,
                        "file_name": row[1]
                    }
                else:
                    return {
                        "success": False,
                        "error": "Record not found"
                    }
                    
    except Exception as e:
        logger.error("delete_vision_result_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def cleanup_old_results(
    days: int = None,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Cleanup old results berdasarkan retention policy
    
    Args:
        days: Override retention days (optional)
        namespace: Target namespace
    """
    if days is None:
        days = get_config().retention_policy['sql_results_days']
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    try:
        pool = await get_pool()
        table_name = DB_TABLE_CONFIG['table_name']
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    DELETE FROM {table_name}
                    WHERE processed_at < %s
                      AND namespace = %s
                    RETURNING id
                """, (cutoff_date, namespace))
                
                deleted_rows = await cur.fetchall()
                deleted_count = len(deleted_rows)
                
                logger.info("vision_results_cleaned_up",
                           count=deleted_count,
                           older_than_days=days)
                
                return {
                    "success": True,
                    "deleted_count": deleted_count,
                    "older_than_days": days,
                    "cutoff_date": cutoff_date.isoformat()
                }
                
    except Exception as e:
        logger.error("cleanup_old_results_failed", error=str(e))
        return {"success": False, "error": str(e)}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _row_to_dict(row, description) -> Dict[str, Any]:
    """Convert database row ke dictionary"""
    result = {}
    for i, col in enumerate(description):
        col_name = col.name
        value = row[i]
        
        # Handle datetime
        if isinstance(value, datetime):
            value = value.isoformat()
        
        # Handle JSON
        if col_name in ['extracted_entities', 'processing_metadata'] and isinstance(value, str):
            try:
                value = json.loads(value)
            except:
                pass
        
        result[col_name] = value
    
    return result


async def check_duplicate(file_hash: str, namespace: str = "default") -> Optional[Dict[str, Any]]:
    """Check if file already processed (by hash)"""
    try:
        pool = await get_pool()
        table_name = DB_TABLE_CONFIG['table_name']
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    SELECT id, confidence_score, processed_at
                    FROM {table_name}
                    WHERE file_hash = %s AND namespace = %s
                """, (file_hash, namespace))
                
                row = await cur.fetchone()
                
                if row:
                    return {
                        "exists": True,
                        "id": str(row[0]),
                        "confidence_score": float(row[1]),
                        "processed_at": row[2].isoformat() if row[2] else None
                    }
                return {"exists": False}
                
    except Exception as e:
        logger.error("check_duplicate_failed", error=str(e))
        return {"exists": False, "error": str(e)}


# =============================================================================
# EXPORT
# =============================================================================

__all__ = [
    'save_vision_result',
    'get_vision_result_by_id',
    'get_high_confidence_results',
    'get_results_by_document_type',
    'get_results_by_date_range',
    'get_processing_stats',
    'get_confidence_distribution',
    'update_vision_status',
    'update_ltm_link',
    'delete_vision_result',
    'cleanup_old_results',
    'check_duplicate',
    'get_pool',
    'close_pool',
]
