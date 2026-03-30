from execution import prompt_registry
from execution.prompt_registry import PromptArgument

def register_default_prompts():
    """Register some default prompts for the MCP server."""
    
    prompt_registry.register(
        name="code_review",
        template="""Review the follow code:

{code}

Please focus on:
1. Security vulnerabilities
2. Performance optimizations
3. Readability and best practices

Context: {context}""",
        description="A specialized prompt for reviewing code with focus on security and performance.",
        arguments=[
            PromptArgument(name="code", description="The source code to review", required=True),
            PromptArgument(name="context", description="Optional background info about the code", required=False)
        ]
    )

    prompt_registry.register(
        name="bug_report_generator",
        template="""Generate a structured bug report from the following logs:

{logs}

The report should include:
- Title
- Severity
- Description
- Steps to Reproduce
- Environment: {environment}""",
        description="Converts logs into a standard bug report format.",
        arguments=[
            PromptArgument(name="logs", description="The log output containing the error", required=True),
            PromptArgument(name="environment", description="Target environment (prod/staging/local)", required=False)
        ]
    )

    prompt_registry.register(
        name="explain_regulation",
        template="""Jelaskan peraturan perundang-undangan berikut dengan bahasa yang mudah dipahami oleh staf teknis di daerah:

{regulation_text}

Fokus pada:
1. Kewenangan Daerah (Sub-Urusan)
2. NSPK (Norma, Standar, Prosedur, Kriteria) yang diatur.
3. Dampak terhadap UU 23/2014.""",
        description="Menjelaskan UU/Peraturan kepada staf teknis PEMDA (Spesifik urusan Bangda).",
        arguments=[
            PromptArgument(name="regulation_text", description="Teks peraturan atau bagian dari UU", required=True)
        ]
    )
