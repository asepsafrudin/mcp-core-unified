import asyncio
import sys
import os
import uuid

# Add parent directory to path
sys.path.append(os.getcwd())

from intelligence.planner import planner
from memory.longterm import initialize_db

async def run_verification():
    print("--- Starting LTM Verification ---")
    
    # 1. Initialize DB
    await initialize_db()
    
    # Generate a unique request to avoid collision with previous runs
    unique_id = str(uuid.uuid4())[:8]
    test_request = f"deploy secret agent {unique_id}"
    print(f"Test Request: {test_request}")
    
    # 2. First Plan (Should be Heuristic)
    print("\n[Step 1] Initial Planning (Expecting Heuristic)...")
    plan1 = await planner.plan(test_request)
    print(f"Plan Result: {plan1}")
    
    # Verify it's heuristic (usually 1 step for simple request)
    if len(plan1) == 1 and plan1[0]['description'] == test_request:
        print(">> SUCCESS: Initial plan used heuristics.")
    else:
        print(f">> WARNING: Unexpected initial plan structure: {plan1}")

    # 3. Save Experience
    print("\n[Step 2] Saving Experience to Memory...")
    custom_plan = [
        {"step": 1, "description": "Initialize stealth mode", "tool_hint": "run_shell"},
        {"step": 2, "description": "Deploy agent payload", "tool_hint": "write_file"},
        {"step": 3, "description": "Clear tracks", "tool_hint": "run_shell"}
    ]
    save_result = await planner.save_experience(test_request, custom_plan)
    print(f"Save Result: {save_result}")
    
    if save_result.get("success"):
        print(">> SUCCESS: Experience saved.")
    else:
        print(">> FAILED: Could not save experience.")
        return

    # 4. Recall Plan (Should be from Memory)
    print("\n[Step 3] Recall Planning (Expecting Memory Hit)...")
    # Wait a moment for DB commitment/indexing if needed (usually instant for small data)
    await asyncio.sleep(1) 
    
    plan2 = await planner.plan(test_request)
    print(f"Plan Result: {plan2}")
    
    # Verify it matches custom_plan
    if len(plan2) == 3 and plan2[0]['description'] == "Initialize stealth mode":
        print(">> SUCCESS: Plan retrieved from memory!")
    else:
        print(">> FAILED: Plan did not match saved experience. Might be scoring issue or retrieval failure.")

if __name__ == "__main__":
    current_dir = os.getcwd()
    if not current_dir.endswith("mcp-unified"):
        print("Please run this script from the 'mcp-unified' root directory.")
        # Try to change dir if running from top level
        if os.path.exists("mcp-unified"):
            os.chdir("mcp-unified")
        else:
            # Maybe inside tests?
            pass
            
    asyncio.run(run_verification())
