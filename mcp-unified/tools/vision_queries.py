"""
Vision Query Tools

Query interface untuk mengakses dan menganalisis vision results dari database.
Mendukung filtering, export, dan analytics.
"""

import csv
import io
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from observability.logger import logger
from tools.base import register_tool
from memory.vision_repository import (
    get_high_confidence_results,
    get_results_by_document_type,
    get_results_by_date_range,
    get_processing_stats,
    get_confidence_distribution,
    get_vision_result_by_id,
    update_vision_status,
    cleanup_old_results
)
from core.vision_config import get_config


# =============================================================================
# QUERY TOOLS
# =============================================================================

@register_tool
def query_vision_by_confidence(
    min_confidence: float = 0.8,
    max_confidence: float = 1.0,
    namespace: str = "default",
    limit: int = 50
) -> Dict[str, Any]:
    """
    Query vision results filtered by confidence score range.
    
    Args:
        min_confidence: Minimum confidence (0.0 - 1.0)
        max_confidence: Maximum confidence (0.0 - 1.0)
        namespace: Namespace to query
        limit: Maximum results (max 100)
        
    Returns:
        Filtered vision results
    """
    try:
        limit = min(limit, 100)  # Cap at 100
        
        # Get high confidence results (>= min_confidence)
        results = get_high_confidence_results(
            min_confidence=min_confidence,
            namespace=namespace,
            limit=limit
        )
        
        # Additional filter for max_confidence
        filtered = [
            r for r in results 
            if r.get('confidence_score', 0) <= max_confidence
        ]
        
        logger.info("vision_query_by_confidence",
                   min=min_confidence,
                   max=max_confidence,
                   results=len(filtered))
        
        return {
            "success": True,
            "count": len(filtered),
            "filters": {
                "min_confidence": min_confidence,
                "max_confidence": max_confidence,
                "namespace": namespace
            },
            "results": filtered
        }
        
    except Exception as e:
        logger.error("query_vision_by_confidence_failed", error=str(e))
        return {"success": False, "error": str(e)}


@register_tool
def query_vision_by_document_type(
    document_type: str,
    min_confidence: float = 0.7,
    namespace: str = "default",
    limit: int = 20
) -> Dict[str, Any]:
    """
    Query vision results by document type (invoice, receipt, form, etc.)
    
    Args:
        document_type: Type of document (invoice, receipt, form, id_card, contract, report)
        min_confidence: Minimum confidence threshold
        namespace: Namespace to query
        limit: Maximum results
        
    Returns:
        Vision results of specified document type
    """
    try:
        results = get_results_by_document_type(
            document_type=document_type,
            namespace=namespace,
            min_confidence=min_confidence,
            limit=limit
        )
        
        logger.info("vision_query_by_document_type",
                   type=document_type,
                   results=len(results))
        
        return {
            "success": True,
            "document_type": document_type,
            "count": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error("query_vision_by_document_type_failed", error=str(e))
        return {"success": False, "error": str(e)}


@register_tool
def query_vision_by_date_range(
    start_date: str,
    end_date: str,
    namespace: str = "default",
    limit: int = 100
) -> Dict[str, Any]:
    """
    Query vision results within a date range.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        namespace: Namespace to query
        limit: Maximum results
        
    Returns:
        Vision results within date range
    """
    try:
        # Parse dates
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        end = end.replace(hour=23, minute=59, second=59)  # Include full end day
        
        results = get_results_by_date_range(
            start_date=start,
            end_date=end,
            namespace=namespace,
            limit=limit
        )
        
        logger.info("vision_query_by_date_range",
                   start=start_date,
                   end=end_date,
                   results=len(results))
        
        return {
            "success": True,
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "count": len(results),
            "results": results
        }
        
    except ValueError as e:
        return {
            "success": False,
            "error": f"Invalid date format. Use YYYY-MM-DD: {str(e)}"
        }
    except Exception as e:
        logger.error("query_vision_by_date_range_failed", error=str(e))
        return {"success": False, "error": str(e)}


@register_tool
def query_vision_recent(
    days: int = 7,
    namespace: str = "default",
    limit: int = 50
) -> Dict[str, Any]:
    """
    Query recent vision results from last N days.
    
    Args:
        days: Number of days to look back
        namespace: Namespace to query
        limit: Maximum results
        
    Returns:
        Recent vision results
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        results = get_results_by_date_range(
            start_date=start_date,
            end_date=end_date,
            namespace=namespace,
            limit=limit
        )
        
        logger.info("vision_query_recent",
                   days=days,
                   results=len(results))
        
        return {
            "success": True,
            "period": f"Last {days} days",
            "count": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error("query_vision_recent_failed", error=str(e))
        return {"success": False, "error": str(e)}


@register_tool
def get_vision_analytics(
    days: int = 30,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Get analytics and statistics for vision processing.
    
    Args:
        days: Analysis period in days
        namespace: Namespace to analyze
        
    Returns:
        Analytics data including counts, averages, distributions
    """
    try:
        # Get processing stats
        stats = get_processing_stats(days=days, namespace=namespace)
        
        # Get confidence distribution
        distribution = get_confidence_distribution(namespace=namespace, bins=10)
        
        if not stats.get("success"):
            return stats
        
        return {
            "success": True,
            "period_days": days,
            "namespace": namespace,
            "summary": stats.get("overall", {}),
            "by_document_type": stats.get("by_document_type", []),
            "by_status": stats.get("by_status", []),
            "confidence_distribution": distribution
        }
        
    except Exception as e:
        logger.error("get_vision_analytics_failed", error=str(e))
        return {"success": False, "error": str(e)}


@register_tool
def get_vision_result_detail(result_id: str) -> Dict[str, Any]:
    """
    Get detailed information for a specific vision result.
    
    Args:
        result_id: UUID of the vision result
        
    Returns:
        Detailed result data
    """
    try:
        result = get_vision_result_by_id(result_id)
        
        if result:
            return {
                "success": True,
                "result": result
            }
        else:
            return {
                "success": False,
                "error": f"Vision result with ID {result_id} not found"
            }
            
    except Exception as e:
        logger.error("get_vision_result_detail_failed", error=str(e))
        return {"success": False, "error": str(e)}


# =============================================================================
# EXPORT TOOLS
# =============================================================================

@register_tool
def export_vision_results_csv(
    output_path: str,
    start_date: str = None,
    end_date: str = None,
    min_confidence: float = 0.0,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Export vision results to CSV file.
    
    Args:
        output_path: Path for output CSV file
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)
        min_confidence: Minimum confidence filter
        namespace: Namespace to export
        
    Returns:
        Export status and file details
    """
    try:
        # Get results based on filters
        if start_date and end_date:
            data = query_vision_by_date_range(
                start_date=start_date,
                end_date=end_date,
                namespace=namespace,
                limit=10000
            )
            results = data.get("results", [])
        else:
            results = get_high_confidence_results(
                min_confidence=min_confidence,
                namespace=namespace,
                limit=10000
            )
        
        if not results:
            return {
                "success": False,
                "error": "No results found matching criteria"
            }
        
        # Write CSV
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            if results:
                # Get headers from first result
                headers = [
                    'id', 'file_name', 'file_path', 'document_type',
                    'confidence_score', 'processing_method', 'model_used',
                    'processed_at', 'status', 'extracted_text'
                ]
                
                writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
                writer.writeheader()
                
                for result in results:
                    row = {k: result.get(k, '') for k in headers}
                    # Truncate long text fields
                    if len(str(row.get('extracted_text', ''))) > 1000:
                        row['extracted_text'] = str(row['extracted_text'])[:997] + '...'
                    writer.writerow(row)
        
        logger.info("vision_results_exported_csv",
                   path=str(output_file),
                   count=len(results))
        
        return {
            "success": True,
            "file_path": str(output_file),
            "record_count": len(results),
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "min_confidence": min_confidence,
                "namespace": namespace
            }
        }
        
    except Exception as e:
        logger.error("export_vision_results_csv_failed", error=str(e))
        return {"success": False, "error": str(e)}


@register_tool
def export_vision_results_json(
    output_path: str,
    start_date: str = None,
    end_date: str = None,
    min_confidence: float = 0.0,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Export vision results to JSON file.
    
    Args:
        output_path: Path for output JSON file
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)
        min_confidence: Minimum confidence filter
        namespace: Namespace to export
        
    Returns:
        Export status and file details
    """
    try:
        # Get results based on filters
        if start_date and end_date:
            data = query_vision_by_date_range(
                start_date=start_date,
                end_date=end_date,
                namespace=namespace,
                limit=10000
            )
            results = data.get("results", [])
        else:
            results = get_high_confidence_results(
                min_confidence=min_confidence,
                namespace=namespace,
                limit=10000
            )
        
        if not results:
            return {
                "success": False,
                "error": "No results found matching criteria"
            }
        
        # Write JSON
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        export_data = {
            "export_date": datetime.now().isoformat(),
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "min_confidence": min_confidence,
                "namespace": namespace
            },
            "record_count": len(results),
            "results": results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info("vision_results_exported_json",
                   path=str(output_file),
                   count=len(results))
        
        return {
            "success": True,
            "file_path": str(output_file),
            "record_count": len(results)
        }
        
    except Exception as e:
        logger.error("export_vision_results_json_failed", error=str(e))
        return {"success": False, "error": str(e)}


# =============================================================================
# ADMIN TOOLS
# =============================================================================

@register_tool
def update_vision_result_status(
    result_id: str,
    new_status: str,
    updated_by: str = "system"
) -> Dict[str, Any]:
    """
    Update the status of a vision result (for manual verification).
    
    Args:
        result_id: UUID of the vision result
        new_status: New status (verified, rejected, pending_review)
        updated_by: Who made the update
        
    Returns:
        Update status
    """
    try:
        result = update_vision_status(result_id, new_status, updated_by)
        return result
        
    except Exception as e:
        logger.error("update_vision_result_status_failed", error=str(e))
        return {"success": False, "error": str(e)}


@register_tool
def cleanup_old_vision_results(
    days: int = None,
    namespace: str = "default",
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Cleanup old vision results based on retention policy.
    
    Args:
        days: Override retention days (default from config)
        namespace: Target namespace
        dry_run: If True, only show what would be deleted
        
    Returns:
        Cleanup summary
    """
    try:
        if days is None:
            days = get_config().retention_policy['sql_results_days']
        
        if dry_run:
            # Just count without deleting
            from datetime import datetime, timedelta
            from memory.vision_repository import get_pool, DB_TABLE_CONFIG
            
            cutoff_date = datetime.now() - timedelta(days=days)
            table_name = DB_TABLE_CONFIG['table_name']
            
            pool = get_pool()
            import asyncio
            
            async def count_old():
                async with pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(f"""
                            SELECT COUNT(*) FROM {table_name}
                            WHERE processed_at < %s AND namespace = %s
                        """, (cutoff_date, namespace))
                        return (await cur.fetchone())[0]
            
            count = asyncio.run(count_old())
            
            return {
                "success": True,
                "dry_run": True,
                "would_delete": count,
                "older_than_days": days,
                "cutoff_date": cutoff_date.isoformat(),
                "namespace": namespace,
                "message": f"{count} records would be deleted. Set dry_run=False to actually delete."
            }
        else:
            # Actually delete
            result = cleanup_old_results(days=days, namespace=namespace)
            return result
        
    except Exception as e:
        logger.error("cleanup_old_vision_results_failed", error=str(e))
        return {"success": False, "error": str(e)}


@register_tool
def get_vision_config_info() -> Dict[str, Any]:
    """
    Get current vision storage configuration.
    
    Returns:
        Current configuration settings
    """
    try:
        config = get_config()
        
        return {
            "success": True,
            "configuration": {
                "confidence_thresholds": config.confidence_thresholds,
                "storage_policy": config.storage_policy,
                "retention_policy": config.retention_policy,
                "processing_config": config.processing_config
            }
        }
        
    except Exception as e:
        logger.error("get_vision_config_info_failed", error=str(e))
        return {"success": False, "error": str(e)}


# =============================================================================
# EXPORT
# =============================================================================

__all__ = [
    'query_vision_by_confidence',
    'query_vision_by_document_type',
    'query_vision_by_date_range',
    'query_vision_recent',
    'get_vision_analytics',
    'get_vision_result_detail',
    'export_vision_results_csv',
    'export_vision_results_json',
    'update_vision_result_status',
    'cleanup_old_vision_results',
    'get_vision_config_info',
]
