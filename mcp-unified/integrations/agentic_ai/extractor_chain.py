"""
Extractor Chain & ML-Based Selection

Advanced extractor system dengan:
1. Chain of Extractors - Multiple extractors per URL
2. ML-Based Selection - AI pilih extractor terbaik
3. Quality Scoring - Score hasil extraction
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

try:
    from .extractors.base_extractor import BaseExtractor
except ImportError:
    from extractors.base_extractor import BaseExtractor

logger = logging.getLogger('ExtractorChain')


@dataclass
class ExtractionResult:
    """Hasil extraction dengan metadata"""
    items: List[Dict[str, Any]]
    extractor_name: str
    score: float  # Quality score 0-1
    execution_time: float  # Seconds
    metadata: Dict[str, Any]


class ExtractorChain:
    """
    Chain multiple extractors untuk satu URL.
    
    Strategies:
    - sequential: Jalankan satu per satu, ambil terbaik
    - parallel: Jalankan semua, merge results
    - smart: ML-based selection
    """
    
    def __init__(self, extractors: List[BaseExtractor]):
        self.extractors = extractors
    
    async def extract_sequential(
        self, 
        page,
        min_quality_score: float = 0.5
    ) -> ExtractionResult:
        """
        Jalankan extractors secara sequential.
        Return first result yang memenuhi quality threshold.
        
        Args:
            page: Playwright page
            min_quality_score: Minimum quality score (0-1)
            
        Returns:
            Best extraction result
        """
        for extractor in self.extractors:
            try:
                start_time = asyncio.get_event_loop().time()
                
                # Pre-process
                await extractor.pre_process(page)
                
                # Extract
                items = await extractor.extract(page)
                
                # Post-process
                items = await extractor.post_process(items)
                
                execution_time = asyncio.get_event_loop().time() - start_time
                
                # Score result
                score = self._score_result(items, extractor)
                
                logger.info(
                    f"🔗 Chain: {extractor.name} = {len(items)} items, "
                    f"score={score:.2f}, time={execution_time:.2f}s"
                )
                
                if score >= min_quality_score and len(items) > 0:
                    return ExtractionResult(
                        items=items,
                        extractor_name=extractor.name,
                        score=score,
                        execution_time=execution_time,
                        metadata={"strategy": "sequential", "position": self.extractors.index(extractor)}
                    )
                    
            except Exception as e:
                logger.error(f"❌ Chain failed for {extractor.name}: {e}")
                continue
        
        # Return empty result jika semua gagal
        return ExtractionResult(
            items=[],
            extractor_name="none",
            score=0.0,
            execution_time=0.0,
            metadata={"strategy": "sequential", "failed": True}
        )
    
    async def extract_parallel(
        self,
        page,
        merge_strategy: str = "best"  # best, concat, unique
    ) -> ExtractionResult:
        """
        Jalankan semua extractors parallel.
        Merge results berdasarkan strategy.
        
        Args:
            page: Playwright page
            merge_strategy: How to merge results
            
        Returns:
            Merged extraction result
        """
        results = []
        
        # Jalankan semua extractors
        for extractor in self.extractors:
            try:
                start_time = asyncio.get_event_loop().time()
                
                await extractor.pre_process(page)
                items = await extractor.extract(page)
                items = await extractor.post_process(items)
                
                execution_time = asyncio.get_event_loop().time() - start_time
                score = self._score_result(items, extractor)
                
                result = ExtractionResult(
                    items=items,
                    extractor_name=extractor.name,
                    score=score,
                    execution_time=execution_time,
                    metadata={}
                )
                results.append(result)
                
                logger.info(
                    f"⚡ Parallel: {extractor.name} = {len(items)} items, "
                    f"score={score:.2f}"
                )
                
            except Exception as e:
                logger.error(f"❌ Parallel failed for {extractor.name}: {e}")
        
        # Merge berdasarkan strategy
        if merge_strategy == "best":
            return self._merge_best(results)
        elif merge_strategy == "concat":
            return self._merge_concat(results)
        elif merge_strategy == "unique":
            return self._merge_unique(results)
        else:
            return self._merge_best(results)
    
    def _merge_best(self, results: List[ExtractionResult]) -> ExtractionResult:
        """Return result dengan score tertinggi"""
        if not results:
            return ExtractionResult([], "none", 0.0, 0.0, {})
        
        best = max(results, key=lambda r: r.score)
        return ExtractionResult(
            items=best.items,
            extractor_name=f"best:{best.extractor_name}",
            score=best.score,
            execution_time=sum(r.execution_time for r in results),
            metadata={
                "strategy": "merge_best",
                "candidates": len(results),
                "best_extractor": best.extractor_name
            }
        )
    
    def _merge_concat(self, results: List[ExtractionResult]) -> ExtractionResult:
        """Concatenate semua results"""
        all_items = []
        for result in results:
            all_items.extend(result.items)
        
        avg_score = sum(r.score for r in results) / len(results) if results else 0
        
        return ExtractionResult(
            items=all_items,
            extractor_name="concat",
            score=avg_score,
            execution_time=sum(r.execution_time for r in results),
            metadata={
                "strategy": "merge_concat",
                "sources": [r.extractor_name for r in results]
            }
        )
    
    def _merge_unique(self, results: List[ExtractionResult]) -> ExtractionResult:
        """Merge dengan deduplication by title"""
        seen_titles = set()
        unique_items = []
        
        for result in results:
            for item in result.items:
                title = item.get("title", "").lower()[:50]
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    unique_items.append(item)
        
        avg_score = sum(r.score for r in results) / len(results) if results else 0
        
        return ExtractionResult(
            items=unique_items,
            extractor_name="unique",
            score=avg_score,
            execution_time=sum(r.execution_time for r in results),
            metadata={
                "strategy": "merge_unique",
                "total_items": sum(len(r.items) for r in results),
                "unique_items": len(unique_items)
            }
        )
    
    def _score_result(
        self,
        items: List[Dict[str, Any]],
        extractor: BaseExtractor
    ) -> float:
        """
        Score extraction result berdasarkan quality metrics.
        
        Metrics:
        - Item count (jumlah items)
        - Field completeness (rata-rata fields yang terisi)
        - Title quality (panjang title rata-rata)
        - URL presence (persentase item dengan URL)
        """
        if not items:
            return 0.0
        
        scores = []
        
        # 1. Item count score (max 10 items = 1.0)
        count_score = min(len(items) / 10, 1.0)
        scores.append(count_score * 0.25)
        
        # 2. Field completeness
        total_fields = 0
        filled_fields = 0
        for item in items:
            for key in ["title", "content", "url", "date"]:
                total_fields += 1
                if item.get(key):
                    filled_fields += 1
        
        completeness = filled_fields / total_fields if total_fields > 0 else 0
        scores.append(completeness * 0.35)
        
        # 3. Title quality
        title_lengths = [len(str(item.get("title", ""))) for item in items]
        avg_title_length = sum(title_lengths) / len(title_lengths) if title_lengths else 0
        title_score = min(avg_title_length / 50, 1.0)  # 50 chars = 1.0
        scores.append(title_score * 0.25)
        
        # 4. URL presence
        urls_present = sum(1 for item in items if item.get("url"))
        url_score = urls_present / len(items) if items else 0
        scores.append(url_score * 0.15)
        
        return sum(scores)


class MLExtractorSelector:
    """
    ML-Based extractor selection.
    
    Pattern: Bandit Algorithm (Epsilon-Greedy)
    - Explore: Try different extractors
    - Exploit: Use best performing extractor
    """
    
    def __init__(self, extractors: List[BaseExtractor]):
        self.extractors = {ext.name: ext for ext in extractors}
        self.performance_history: Dict[str, List[float]] = {}  # name -> scores
        self.epsilon = 0.2  # Exploration rate
    
    def select_extractor(self, url: str) -> BaseExtractor:
        """
        Select extractor berdasarkan historical performance.
        
        Args:
            url: Target URL
            
        Returns:
            Selected extractor
        """
        import random
        
        # Exploration: random selection
        if random.random() < self.epsilon:
            selected = random.choice(list(self.extractors.values()))
            logger.info(f"🎲 ML Select (explore): {selected.name}")
            return selected
        
        # Exploitation: select best performer
        best_extractor = None
        best_score = -1
        
        for name, history in self.performance_history.items():
            if name in self.extractors:
                avg_score = sum(history) / len(history) if history else 0
                if avg_score > best_score:
                    best_score = avg_score
                    best_extractor = self.extractors[name]
        
        if best_extractor:
            logger.info(f"🎯 ML Select (exploit): {best_extractor.name} (avg_score={best_score:.2f})")
            return best_extractor
        
        # Fallback: random
        return random.choice(list(self.extractors.values()))
    
    def update_performance(self, extractor_name: str, score: float):
        """
        Update performance history setelah extraction.
        
        Args:
            extractor_name: Name of extractor
            score: Quality score (0-1)
        """
        if extractor_name not in self.performance_history:
            self.performance_history[extractor_name] = []
        
        self.performance_history[extractor_name].append(score)
        
        # Keep only last 10 scores
        self.performance_history[extractor_name] = self.performance_history[extractor_name][-10:]
        
        logger.info(f"📊 Updated performance: {extractor_name} = {score:.2f}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get selection statistics"""
        stats = {}
        for name, history in self.performance_history.items():
            if history:
                stats[name] = {
                    "avg_score": sum(history) / len(history),
                    "attempts": len(history),
                    "last_score": history[-1]
                }
        return stats
