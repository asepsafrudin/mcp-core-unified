"""
self_learning_engine.py — Continuous Self-Learning & Auto-Improvement Pipeline for SATRIA.
Analyzes interaction logs from storage/admin_data/satria_interactions/, auto-tunes tool timeouts based on P95,
optimizes tool selection priorities, processes user corrections, and generates evaluation insights.
"""

import time
import json
import logging
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from integrations.whatsapp.interaction_logger import satria_interaction_logger
from integrations.whatsapp.timeout_guard import satria_timeout_guard
from integrations.whatsapp.tool_selector import satria_tool_selector

logger = logging.getLogger("satria_self_learning")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
STORAGE_BASE = PROJECT_ROOT / "storage" / "admin_data"
REPORTS_DIR = PROJECT_ROOT / "storage" / "reports"
BACKLOG_DIR = STORAGE_BASE / "satria_backlog"


class SelfLearningEngine:
    """
    Mesin pembelajaran mandiri berkelanjutan (*continuous evaluation & self-improvement*).
    Menganalisis performa empiris nyata untuk menyempurnakan konfigurasi adapter secara adaptif.
    """

    def __init__(self):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def generate_evaluation_report(self, days: int = 7) -> Dict[str, Any]:
        """
        Menghasilkan laporan evaluasi performa menyeluruh berdasarkan log interaksi N hari terakhir.
        """
        interactions = satria_interaction_logger.load_recent_interactions(days=days)
        if not interactions:
            return {
                "status": "insufficient_data",
                "message": "Belum ada catatan interaksi yang cukup untuk dianalisis.",
                "total_interactions": 0
            }

        total_count = len(interactions)
        unique_users = len(set(i.get("user_phone", "") for i in interactions if i.get("user_phone")))

        # 1. Klasifikasi Service vs Non-Service
        non_service_count = sum(1 for i in interactions if i.get("is_non_service"))
        service_count = total_count - non_service_count

        # 2. Distribusi Intent
        intent_counts: Dict[str, int] = {}
        low_confidence_count = 0
        for i in interactions:
            it = i.get("intent", "unknown")
            intent_counts[it] = intent_counts.get(it, 0) + 1
            if float(i.get("confidence", 1.0)) < 0.6:
                low_confidence_count += 1

        # 3. Analisis Latensi Respons
        latencies = [float(i.get("response_time_ms", 0)) for i in interactions if i.get("response_time_ms")]
        mean_lat = statistics.mean(latencies) if latencies else 0.0
        p95_lat = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else (max(latencies) if latencies else 0.0)

        # 4. Penggunaan Tools & Fallback Rate
        tool_counts: Dict[str, int] = {}
        fallback_invocations = 0
        for i in interactions:
            tools = i.get("tools_called", [])
            for t in tools:
                tool_counts[t] = tool_counts.get(t, 0) + 1
            if i.get("fallback_used"):
                fallback_invocations += 1

        fallback_rate = round(fallback_invocations / max(1, total_count), 3)

        # 5. Rekomendasi Perbaikan Otomatis
        recommendations = []
        if low_confidence_count / max(1, total_count) > 0.15:
            recommendations.append(
                f"Tingkat low-confidence intent mencapai {low_confidence_count/total_count*100:.1f}%. "
                "Perlu penambahan kata kunci regulasi atau sinonim pada DomainIntentClassifier."
            )
        if fallback_rate > 0.10:
            recommendations.append(
                f"Tingkat fallback mencapai {fallback_rate*100:.1f}%. "
                "Periksa stabilitas koneksi pgvector atau naikkan timeout perkakas terkait."
            )
        if p95_lat > 8000:
            recommendations.append(
                f"Latensi P95 ({p95_lat:.0f}ms) mendekati 8 detik. Disarankan auto-tuning timeout atau optimalisasi Fast-Path."
            )

        report = {
            "generated_at": datetime.now().isoformat(),
            "period_days": days,
            "total_interactions": total_count,
            "unique_users": unique_users,
            "distribution": {
                "service_requests": service_count,
                "non_service_requests": non_service_count
            },
            "intent_distribution": intent_counts,
            "low_confidence_count": low_confidence_count,
            "latency_metrics_ms": {
                "mean": round(mean_lat, 1),
                "p95": round(p95_lat, 1)
            },
            "tool_usage": tool_counts,
            "fallback_rate": fallback_rate,
            "recommendations": recommendations
        }

        # Simpan laporan resmi ke storage/reports/
        report_file = REPORTS_DIR / f"self_learning_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save report: {e}")

        return report

    def auto_tune_timeouts(self) -> List[Dict[str, Any]]:
        """
        Menyesuaikan batas waktu timeout perkakas secara otomatis berdasarkan P95 riil.
        """
        interactions = satria_interaction_logger.load_recent_interactions(days=7)
        tool_latencies: Dict[str, List[float]] = {}

        for i in interactions:
            tool_called = i.get("tool_called")
            lat_sec = float(i.get("tool_latency_sec", 0.0))
            if tool_called and lat_sec > 0:
                if tool_called not in tool_latencies:
                    tool_latencies[tool_called] = []
                tool_latencies[tool_called].append(lat_sec)

        adjustments = []
        for tool_name, lats in tool_latencies.items():
            if len(lats) >= 5:
                p95 = statistics.quantiles(lats, n=20)[18] if len(lats) >= 20 else max(lats)
                current_cfg = satria_timeout_guard.get_config(tool_name)
                curr_timeout = float(current_cfg.get("timeout", 5.0))

                # Jika P95 melampaui 80% dari batas timeout saat ini, berikan buffer 20%
                if p95 > curr_timeout * 0.80:
                    new_timeout = min(10.0, round(p95 * 1.25, 1))
                    satria_timeout_guard.tool_configs[tool_name]["timeout"] = new_timeout
                    adjustments.append({
                        "tool": tool_name,
                        "old_timeout": curr_timeout,
                        "new_timeout": new_timeout,
                        "observed_p95": round(p95, 2),
                        "action": "INCREASED"
                    })
                    logger.info(f"⚡ [SELF-LEARNING] Auto-tuned timeout for {tool_name}: {curr_timeout}s -> {new_timeout}s")

        return adjustments

    def optimize_tool_weights(self) -> List[Dict[str, Any]]:
        """
        Menyesuaikan prioritas perkakas di tool_selector berdasarkan frekuensi keberhasilan.
        """
        interactions = satria_interaction_logger.load_recent_interactions(days=7)
        tool_success: Dict[str, int] = {}
        tool_total: Dict[str, int] = {}

        for i in interactions:
            t = i.get("tool_called")
            if t:
                tool_total[t] = tool_total.get(t, 0) + 1
                if not i.get("fallback_used"):
                    tool_success[t] = tool_success.get(t, 0) + 1

        optimizations = []
        for tool_name, total in tool_total.items():
            if total >= 10:
                success_ratio = tool_success.get(tool_name, 0) / total
                tool_obj = satria_tool_selector.tools.get(tool_name)
                if tool_obj:
                    old_p = tool_obj.priority
                    if success_ratio >= 0.90 and old_p < 10:
                        tool_obj.priority += 1
                        optimizations.append({"tool": tool_name, "old_priority": old_p, "new_priority": tool_obj.priority, "reason": "High success rate"})
                    elif success_ratio < 0.60 and old_p > 3:
                        tool_obj.priority -= 1
                        optimizations.append({"tool": tool_name, "old_priority": old_p, "new_priority": tool_obj.priority, "reason": "Low success rate"})

        return optimizations


# Singleton instance global
satria_self_learning_engine = SelfLearningEngine()
