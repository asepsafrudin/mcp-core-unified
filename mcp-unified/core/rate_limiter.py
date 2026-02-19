from collections import defaultdict
import time
from observability.logger import logger

class BudgetExceededError(Exception):
    pass

class TokenBudgetLimiter:
    """
    Prevent budget overrun by tracking usage against daily/hourly limits.
    """
    
    def __init__(self):
        self.daily_limit = 100_000  # tokens
        self.hourly_limit = 10_000
        self.usage = defaultdict(int)
        self.reset_times = {}
    
    def check_and_consume(self, tokens: int) -> bool:
        now = time.time()
        day_key = time.strftime("%Y-%m-%d", time.localtime(now))
        hour_key = time.strftime("%Y-%m-%d-%H", time.localtime(now))
        
        # Reset daily counter if new day
        # In a real distributed system this would be Redis.
        # Here we just rely on in-memory and keys.
        # We don't explicitly clear old keys to keep it simple, 
        # but in long run we should cleanup.
        
        # Check limits
        # Note: defaultdict(int) returns 0 if key missing, so it works.
        
        if self.usage[day_key] + tokens > self.daily_limit:
             logger.warning("daily_budget_exceeded", 
                            current=self.usage[day_key], 
                            request=tokens, 
                            limit=self.daily_limit)
             raise BudgetExceededError(f"Daily limit exceeded: {self.usage[day_key]}/{self.daily_limit}")
        
        if self.usage[hour_key] + tokens > self.hourly_limit:
             logger.warning("hourly_budget_exceeded", 
                            current=self.usage[hour_key], 
                            request=tokens, 
                            limit=self.hourly_limit)
             raise BudgetExceededError(f"Hourly limit exceeded: {self.usage[hour_key]}/{self.hourly_limit}")
        
        # Consume
        self.usage[day_key] += tokens
        self.usage[hour_key] += tokens
        
        return True
    
    def adjust(self, difference: int):
        """Adjust usage if estimate was wrong."""
        # Simple adjust current hour/day
        now = time.time()
        day_key = time.strftime("%Y-%m-%d", time.localtime(now))
        hour_key = time.strftime("%Y-%m-%d-%H", time.localtime(now))
        
        self.usage[day_key] += difference
        self.usage[hour_key] += difference

budget_limiter = TokenBudgetLimiter()
