🔍 Starting security scan of: /home/aseps/MCP/mcp-unified
================================================================================
⚠️  'safety' not installed. Skipping dependency scan.
   Install with: pip install safety
================================================================================
SECURITY SCAN REPORT
================================================================================

Files Scanned: 462
Total Vulnerabilities: 834

Severity Breakdown:
  🔴 CRITICAL: 37
  🔴 HIGH: 47
  🟡 MEDIUM: 750

Category Breakdown:
  • secret: 739
  • injection: 57
  • input_validation: 38

================================================================================
VULNERABILITIES DETAIL
================================================================================

🔴 [CRITICAL] Dangerous exec() call
   File: /home/aseps/MCP/mcp-unified/skills/healing/self_healing.py:85
   Category: injection
   Code: proc = await asyncio.create_subprocess_exec(...
   Fix: Use parameterized queries, input validation, and avoid dynamic code execution....

🔴 [CRITICAL] Hardcoded API key
   File: /home/aseps/MCP/mcp-unified/integrations/telegram/tests/conftest.py:17
   Category: secret
   Code: ai=AIConfig(groq_api_key="test-key"),...
   Fix: Move secrets to environment variables or use a secret management service like HashiCorp Vault or AWS...

🔴 [CRITICAL] Hardcoded token
   File: /home/aseps/MCP/mcp-unified/integrations/telegram/tests/conftest.py:15
   Category: secret
   Code: bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",...
   Fix: Move secrets to environment variables or use a secret management service like HashiCorp Vault or AWS...

🔴 [CRITICAL] Hardcoded token
   File: /home/aseps/MCP/mcp-unified/integrations/telegram/tests/test_config.py:46
   Category: secret
   Code: TelegramConfig(bot_token="invalid-token")...
   Fix: Move secrets to environment variables or use a secret management service like HashiCorp Vault or AWS...

🔴 [CRITICAL] Hardcoded token
   File: /home/aseps/MCP/mcp-unified/integrations/telegram/tests/test_config.py:53
   Category: secret
   Code: bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",...
   Fix: Move secrets to environment variables or use a secret management service like HashiCorp Vault or AWS...

🔴 [CRITICAL] Hardcoded token
   File: /home/aseps/MCP/mcp-unified/integrations/telegram/tests/test_config.py:64
   Category: secret
   Code: bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",...
   Fix: Move secrets to environment variables or use a secret management service like HashiCorp Vault or AWS...

🔴 [CRITICAL] Dangerous exec() call
   File: /home/aseps/MCP/mcp-unified/integrations/agentic_ai/extractor_marketplace.py:206
   Category: injection
   Code: exec(package.code, namespace)...
   Fix: Use parameterized queries, input validation, and avoid dynamic code execution....

🔴 [CRITICAL] Dangerous exec() call
   File: /home/aseps/MCP/mcp-unified/integrations/agentic_ai/extractor_marketplace.py:206
   Category: injection
   Code: exec(package.code, namespace)...
   Fix: Avoid using exec(). Use safer alternatives like ast.literal_eval()...

🔴 [CRITICAL] Hardcoded token
   File: /home/aseps/MCP/mcp-unified/services/llm_api/dependencies.py:39
   Category: secret
   Code: self.config = TelegramConfig(bot_token="dummy:token")...
   Fix: Move secrets to environment variables or use a secret management service like HashiCorp Vault or AWS...

🔴 [CRITICAL] Dangerous eval() call
   File: /home/aseps/MCP/mcp-unified/security/scanner.py:89
   Category: injection
   Code: (r'eval\s*\(', "Dangerous eval() call", Severity.CRITICAL),...
   Fix: Use parameterized queries, input validation, and avoid dynamic code execution....

🔴 [CRITICAL] Dangerous eval() call
   File: /home/aseps/MCP/mcp-unified/security/scanner.py:185
   Category: injection
   Code: remediation=f"Avoid using {node.func.id}(). Use safer alternatives like ast.lite...
   Fix: Use parameterized queries, input validation, and avoid dynamic code execution....

🔴 [CRITICAL] Dangerous exec() call
   File: /home/aseps/MCP/mcp-unified/security/scanner.py:90
   Category: injection
   Code: (r'exec\s*\(', "Dangerous exec() call", Severity.CRITICAL),...
   Fix: Use parameterized queries, input validation, and avoid dynamic code execution....

🔴 [CRITICAL] Dangerous exec() call
   File: /home/aseps/MCP/mcp-unified/intelligence/self_healing.py:111
   Category: injection
   Code: proc = await asyncio.create_subprocess_exec(...
   Fix: Use parameterized queries, input validation, and avoid dynamic code execution....

🔴 [CRITICAL] Dangerous exec() call
   File: /home/aseps/MCP/mcp-unified/tools/media/vision.py:44
   Category: injection
   Code: proc = await asyncio.create_subprocess_exec(...
   Fix: Use parameterized queries, input validation, and avoid dynamic code execution....

🔴 [CRITICAL] Dangerous exec() call
   File: /home/aseps/MCP/mcp-unified/knowledge/embeddings.py:84
   Category: injection
   Code: proc = await asyncio.create_subprocess_exec(...
   Fix: Use parameterized queries, input validation, and avoid dynamic code execution....

🔴 [CRITICAL] Hardcoded token
   File: /home/aseps/MCP/mcp-unified/knowledge/admin/auth.py:217
   Category: secret
   Code: token="FORCE_PASSWORD_CHANGE",...
   Fix: Move secrets to environment variables or use a secret management service like HashiCorp Vault or AWS...

🔴 [CRITICAL] Dangerous exec() call
   File: /home/aseps/MCP/mcp-unified/memory/longterm.py:200
   Category: injection
   Code: proc = await asyncio.create_subprocess_exec(...
   Fix: Use parameterized queries, input validation, and avoid dynamic code execution....

🔴 [CRITICAL] Dangerous eval() call
   File: /home/aseps/MCP/mcp-unified/agents/profiles/research_agent.py:48
   Category: injection
   Code: - Information retrieval (RAG)...
   Fix: Use parameterized queries, input validation, and avoid dynamic code execution....

🔴 [CRITICAL] Hardcoded secret
   File: /home/aseps/MCP/mcp-unified/core/advanced_features/security_audit.py:112
   Category: secret
   Code: 'secret=',...
   Fix: Move secrets to environment variables or use a secret management service like HashiCorp Vault or AWS...

🔴 [CRITICAL] Hardcoded API key
   File: /home/aseps/MCP/mcp-unified/core/advanced_features/security_audit.py:113
   Category: secret
   Code: 'api_key=',...
   Fix: Move secrets to environment variables or use a secret management service like HashiCorp Vault or AWS...

================================================================================
