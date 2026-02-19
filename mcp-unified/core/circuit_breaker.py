import time
from enum import Enum
from dataclasses import dataclass
from observability.logger import logger

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreakerOpenError(Exception):
    pass

@dataclass
class CircuitBreaker:
    """
    Prevent cascade failures.
    Tracks failures and opens circuit if threshold exceeded.
    """
    failure_threshold: int = 5
    timeout: int = 60  # seconds
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = 0.0
    
    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("circuit_breaker_half_open")
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            
            # Success - reset circuit
            if self.state != CircuitState.CLOSED:
                self.state = CircuitState.CLOSED
                self.failures = 0
                logger.info("circuit_breaker_reset")
            
            return result
        
        except Exception as e:
            # We assume any exception is a failure. 
            # In production we might want to filter only specific error types (e.g. ConnectionError)
            self.failures += 1
            self.last_failure_time = time.time()
            
            if self.failures >= self.failure_threshold and self.state != CircuitState.OPEN:
                self.state = CircuitState.OPEN
                logger.critical("circuit_breaker_opened", failures=self.failures)
            
            raise e

# Global instance could be created here or in server
circuit_breaker = CircuitBreaker()
