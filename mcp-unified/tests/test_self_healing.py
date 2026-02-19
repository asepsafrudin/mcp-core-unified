import pytest
from intelligence.self_healing import self_healing
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_retry_logic():
    # Mock a function that fails twice then succeeds
    mock_func = AsyncMock(side_effect=[Exception("fail1"), Exception("fail2"), "success"])
    
    result = await self_healing.execute_with_healing(mock_func)
    
    assert result == "success"
    assert mock_func.call_count == 3

@pytest.mark.asyncio
async def test_max_retries_exceeded():
    mock_func = AsyncMock(side_effect=[Exception("fail")] * 3)
    
    with pytest.raises(Exception):
        await self_healing.execute_with_healing(mock_func)
    
    assert mock_func.call_count == 3
