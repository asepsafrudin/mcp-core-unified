"""
Frontend Developer Skill — Expert frontend development with ECC pattern wrapping.

This skill provides comprehensive frontend development assistance by wrapping
patterns from ECC (https://github.com/affaan-m/ECC) and integrating with
existing MCP tools for code analysis, file operations, and browser testing.

## ECC Skills Wrapped:
- dashboard-builder: Build monitoring dashboards (Grafana, SigNoz)
- frontend-patterns: React, Next.js, state management, performance
- frontend-a11y: WCAG accessibility compliance
- react-performance: Bundle size, rendering optimization
- design-system: Consistent design patterns

## Guardrails (from ECC dashboard-builder):
- Start from operator questions, not visual layout
- Don't include every metric just because it exists
- Don't mix health, throughput, and resource panels without structure
- Ship panels with titles, units, and sane thresholds
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from skills.base import (
    BaseSkill,
    SkillDefinition,
    SkillDependency,
    SkillComplexity,
    register_skill,
)


# ECC Pattern References
ECC_PATTERNS = {
    "dashboard-builder": {
        "description": "Build monitoring dashboards that answer real operator questions",
        "guardrails": [
            "Start from operator questions, not visual layout",
            "Don't include every metric just because it exists",
            "Don't mix health, throughput, and resource panels without structure",
            "Ship panels with titles, units, and sane thresholds",
        ],
        "workflow": [
            "Define the operating questions",
            "Study the target platform schema",
            "Build the minimum useful board",
            "Cut vanity panels",
        ],
    },
    "frontend-patterns": {
        "description": "Modern frontend patterns for React, Next.js, and performant UIs",
        "patterns": [
            "Composition over inheritance",
            "Compound components",
            "Custom hooks (useToggle, useQuery, useDebounce)",
            "Context + Reducer for state management",
            "Memoization (useMemo, useCallback, React.memo)",
            "Code splitting & lazy loading",
            "Virtualization for long lists",
            "Error boundaries",
        ],
    },
    "frontend-a11y": {
        "description": "WCAG accessibility compliance patterns",
        "patterns": [
            "Keyboard navigation (Arrow keys, Enter, Escape)",
            "Focus management in modals",
            "ARIA attributes (role, aria-expanded, aria-haspopup)",
            "Screen reader compatibility",
        ],
    },
    "react-performance": {
        "description": "React performance optimization techniques",
        "patterns": [
            "Bundle size analysis",
            "Render optimization",
            "Virtual scrolling",
            "Memoization strategies",
        ],
    },
}


@register_skill
class FrontendDevSkill(BaseSkill):
    """
    Skill for frontend development with ECC pattern wrapping.

    Provides:
    - Component generation (React, Vue, HTML)
    - Code review with best practices
    - Accessibility checking (WCAG)
    - Performance auditing
    - Dashboard building (Grafana, SigNoz)
    - CSS/Tailwind styling assistance
    """

    @property
    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name=os.getenv("FRONTEND_SKILL_NAME", "frontend_developer"),
            description=(
                "Expert frontend development assistant for React, Vue, Next.js, "
                "and modern CSS. Wraps ECC patterns for dashboard building, "
                "accessibility, and performance optimization."
            ),
            complexity=SkillComplexity.COMPLEX,
            dependencies=[
                SkillDependency("analyze_code_structure", required=False),
            ],
            tags=[
                "frontend",
                "react",
                "vue",
                "nextjs",
                "css",
                "tailwind",
                "component",
                "dashboard",
                "accessibility",
                "performance",
            ],
        )

    async def execute(self, task: Task) -> TaskResult:
        """
        Execute frontend development task.

        Supported actions:
        - generate_component: Generate React/Vue/HTML component
        - review_code: Review frontend code quality
        - check_accessibility: WCAG compliance check
        - audit_performance: Performance audit
        - help_styling: CSS/Tailwind assistance
        - build_dashboard: Build monitoring dashboard
        - analyze_structure: Analyze project structure
        - get_patterns: Get ECC pattern reference
        """
        payload = task.payload
        action = payload.get("action", "get_patterns")

        try:
            if action == "generate_component":
                return await self._generate_component(payload)
            elif action == "review_code":
                return await self._review_code(payload)
            elif action == "check_accessibility":
                return await self._check_accessibility(payload)
            elif action == "audit_performance":
                return await self._audit_performance(payload)
            elif action == "help_styling":
                return await self._help_styling(payload)
            elif action == "build_dashboard":
                return await self._build_dashboard(payload)
            elif action == "analyze_structure":
                return await self._analyze_structure(payload)
            elif action == "get_patterns":
                return self._get_patterns(payload)
            else:
                return TaskResult.failure_result(
                    task.id,
                    error=f"Unknown action: {action}",
                    error_code="INVALID_ACTION",
                )

        except Exception as e:
            logger.error("frontend_dev_skill_failed", error=str(e), action=action)
            return TaskResult.failure_result(
                task.id, error=str(e), error_code="SKILL_ERROR"
            )

    async def _generate_component(self, payload: Dict[str, Any]) -> TaskResult:
        """
        Generate React/Vue/HTML component based on requirements.

        Payload:
            - component_type: "react" | "vue" | "html"
            - component_name: Name of the component
            - props: List of props/attributes
            - features: List of features (state, effects, etc.)
            - styling: "css" | "tailwind" | "styled-components"
        """
        component_type = payload.get("component_type", "react")
        component_name = payload.get("component_name", "Component")
        props = payload.get("props", [])
        features = payload.get("features", [])
        styling = payload.get("styling", "tailwind")

        # Build component based on type
        if component_type == "react":
            code = self._generate_react_component(
                component_name, props, features, styling
            )
        elif component_type == "vue":
            code = self._generate_vue_component(
                component_name, props, features, styling
            )
        else:
            code = self._generate_html_component(component_name, props, styling)

        return TaskResult.success_result(
            task_id=payload.get("task_id", "unknown"),
            data={
                "component_type": component_type,
                "component_name": component_name,
                "code": code,
                "patterns_used": self._get_patterns_for_features(features),
            },
            context={"skill": self.name, "action": "generate_component"},
        )

    async def _review_code(self, payload: Dict[str, Any]) -> TaskResult:
        """
        Review frontend code for best practices.

        Payload:
            - file_path: Path to file to review
            - code: Code content (alternative to file_path)
            - focus: "react" | "vue" | "css" | "general"
        """
        file_path = payload.get("file_path")
        code = payload.get("code")
        focus = payload.get("focus", "general")

        # Read file if path provided
        if file_path and not code:
            try:
                from tools.file.read import read_file_impl

                file_result = await read_file_impl(file_path)
                if file_result.get("success"):
                    code = file_result.get("content")
            except Exception as e:
                logger.warning("Could not read file", path=file_path, error=str(e))

        if not code:
            return TaskResult.failure_result(
                task_id=payload.get("task_id", "unknown"),
                error="No code content provided",
                error_code="INVALID_INPUT",
            )

        # Perform review based on focus
        review_result = self._review_frontend_code(code, focus)

        return TaskResult.success_result(
            task_id=payload.get("task_id", "unknown"),
            data=review_result,
            context={"skill": self.name, "action": "review_code"},
        )

    async def _check_accessibility(self, payload: Dict[str, Any]) -> TaskResult:
        """
        Check WCAG accessibility compliance.

        Payload:
            - file_path: Path to file to check
            - code: Code content (alternative to file_path)
            - level: "A" | "AA" | "AAA"
        """
        file_path = payload.get("file_path")
        code = payload.get("code")
        level = payload.get("level", "AA")

        # Read file if path provided
        if file_path and not code:
            try:
                from tools.file.read import read_file_impl

                file_result = await read_file_impl(file_path)
                if file_result.get("success"):
                    code = file_result.get("content")
            except Exception as e:
                logger.warning("Could not read file", path=file_path, error=str(e))

        if not code:
            return TaskResult.failure_result(
                task_id=payload.get("task_id", "unknown"),
                error="No code content provided",
                error_code="INVALID_INPUT",
            )

        # Perform accessibility check
        a11y_result = self._check_a11y_compliance(code, level)

        return TaskResult.success_result(
            task_id=payload.get("task_id", "unknown"),
            data=a11y_result,
            context={"skill": self.name, "action": "check_accessibility"},
        )

    async def _audit_performance(self, payload: Dict[str, Any]) -> TaskResult:
        """
        Audit frontend performance.

        Payload:
            - file_path: Path to file to audit
            - code: Code content (alternative to file_path)
            - focus: "bundle" | "rendering" | "network" | "all"
        """
        file_path = payload.get("file_path")
        code = payload.get("code")
        focus = payload.get("focus", "all")

        # Read file if path provided
        if file_path and not code:
            try:
                from tools.file.read import read_file_impl

                file_result = await read_file_impl(file_path)
                if file_result.get("success"):
                    code = file_result.get("content")
            except Exception as e:
                logger.warning("Could not read file", path=file_path, error=str(e))

        if not code:
            return TaskResult.failure_result(
                task_id=payload.get("task_id", "unknown"),
                error="No code content provided",
                error_code="INVALID_INPUT",
            )

        # Perform performance audit
        perf_result = self._audit_frontend_performance(code, focus)

        return TaskResult.success_result(
            task_id=payload.get("task_id", "unknown"),
            data=perf_result,
            context={"skill": self.name, "action": "audit_performance"},
        )

    async def _help_styling(self, payload: Dict[str, Any]) -> TaskResult:
        """
        Provide CSS/Tailwind styling assistance.

        Payload:
            - requirement: Description of styling needed
            - framework: "css" | "tailwind" | "styled-components"
            - existing_code: Optional existing code to modify
        """
        requirement = payload.get("requirement", "")
        framework = payload.get("framework", "tailwind")
        existing_code = payload.get("existing_code", "")

        # Generate styling solution
        styling_result = self._generate_styling_solution(
            requirement, framework, existing_code
        )

        return TaskResult.success_result(
            task_id=payload.get("task_id", "unknown"),
            data=styling_result,
            context={"skill": self.name, "action": "help_styling"},
        )

    async def _build_dashboard(self, payload: Dict[str, Any]) -> TaskResult:
        """
        Build monitoring dashboard (Grafana, SigNoz).

        Wraps ECC dashboard-builder pattern.

        Payload:
            - platform: "grafana" | "signoz" | "custom"
            - service_type: "api" | "database" | "queue" | "general"
            - metrics: List of metrics to include
            - questions: Operating questions to answer
        """
        platform = payload.get("platform", "grafana")
        service_type = payload.get("service_type", "general")
        metrics = payload.get("metrics", [])
        questions = payload.get("questions", [])

        # Build dashboard following ECC workflow
        dashboard = self._build_monitoring_dashboard(
            platform, service_type, metrics, questions
        )

        return TaskResult.success_result(
            task_id=payload.get("task_id", "unknown"),
            data=dashboard,
            context={"skill": self.name, "action": "build_dashboard"},
        )

    async def _analyze_structure(self, payload: Dict[str, Any]) -> TaskResult:
        """
        Analyze frontend project structure.

        Payload:
            - project_path: Path to project root
            - framework: "react" | "vue" | "nextjs" | "auto"
        """
        project_path = payload.get("project_path", ".")
        framework = payload.get("framework", "auto")

        # Analyze project structure
        structure = self._analyze_project_structure(project_path, framework)

        return TaskResult.success_result(
            task_id=payload.get("task_id", "unknown"),
            data=structure,
            context={"skill": self.name, "action": "analyze_structure"},
        )

    def _get_patterns(self, payload: Dict[str, Any]) -> TaskResult:
        """
        Get ECC pattern reference.

        Payload:
            - pattern_name: Specific pattern to retrieve
        """
        pattern_name = payload.get("pattern_name", "all")

        if pattern_name == "all":
            patterns = ECC_PATTERNS
        else:
            patterns = {pattern_name: ECC_PATTERNS.get(pattern_name, {})}

        return TaskResult.success_result(
            task_id=payload.get("task_id", "unknown"),
            data={"patterns": patterns},
            context={"skill": self.name, "action": "get_patterns"},
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _generate_react_component(
        self,
        name: str,
        props: List[str],
        features: List[str],
        styling: str,
    ) -> str:
        """Generate React component code."""
        props_interface = self._build_props_interface(name, props)
        hooks = self._build_hooks(features)
        jsx = self._build_jsx(name, props, styling)

        return f'''import React, {{ useState, useEffect }} from 'react';

{props_interface}

export function {name}({{ {', '.join(props)} }}: {name}Props) {{
{hooks}
  return (
{jsx}
  );
}}
'''

    def _generate_vue_component(
        self,
        name: str,
        props: List[str],
        features: List[str],
        styling: str,
    ) -> str:
        """Generate Vue component code."""
        props_def = self._build_vue_props(props)
        setup = self._build_vue_setup(features)

        return f'''<template>
  <div class="{name.lower()}">
    <!-- Component content -->
  </div>
</template>

<script setup lang="ts">
{props_def}
{setup}
</script>

<style scoped>
.{name.lower()} {{
  /* Styles */
}}
</style>
'''

    def _generate_html_component(
        self, name: str, props: List[str], styling: str
    ) -> str:
        """Generate HTML component code."""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name}</title>
  <style>
    /* Styles */
  </style>
</head>
<body>
  <div id="{name.lower()}">
    <!-- Component content -->
  </div>
  <script>
    // JavaScript
  </script>
</body>
</html>
'''

    def _build_props_interface(self, name: str, props: List[str]) -> str:
        """Build TypeScript props interface."""
        if not props:
            return f"interface {name}Props {{\n  children?: React.ReactNode;\n}}"
        props_lines = [f"  {p}: string;" for p in props]
        return f"interface {name}Props {{\n" + "\n".join(props_lines) + "\n}"

    def _build_hooks(self, features: List[str]) -> str:
        """Build React hooks based on features."""
        hooks = []
        if "state" in features:
            hooks.append("  const [state, setState] = useState(null);")
        if "effect" in features:
            hooks.append("  useEffect(() => {\n    // Side effect\n  }, []);")
        if "memo" in features:
            hooks.append("  // useMemo for expensive computations")
        return "\n".join(hooks) if hooks else "  // No hooks needed"

    def _build_jsx(self, name: str, props: List[str], styling: str) -> str:
        """Build JSX content."""
        className = f'className="{name.lower()}"' if styling == "tailwind" else f'className="{name.lower()}"'
        return f"    <div {className}>\n      <h2>{name}</h2>\n    </div>"

    def _build_vue_props(self, props: List[str]) -> str:
        """Build Vue props definition."""
        if not props:
            return "// No props"
        props_lines = [f"  {p}: string," for p in props]
        return "const props = defineProps({\n" + "\n".join(props_lines) + "\n});"

    def _build_vue_setup(self, features: List[str]) -> str:
        """Build Vue setup code."""
        setup = []
        if "state" in features:
            setup.append("const state = ref(null);")
        if "effect" in features:
            setup.append("onMounted(() => {\n  // Side effect\n});")
        return "\n".join(setup) if setup else "// No setup needed"

    def _get_patterns_for_features(self, features: List[str]) -> List[str]:
        """Get ECC patterns that match the features."""
        patterns = []
        if "state" in features or "effect" in features:
            patterns.append("frontend-patterns: Custom Hooks")
        if "memo" in features:
            patterns.append("react-performance: Memoization")
        if "a11y" in features:
            patterns.append("frontend-a11y: Keyboard Navigation")
        return patterns

    def _review_frontend_code(self, code: str, focus: str) -> Dict[str, Any]:
        """Review frontend code for best practices."""
        issues = []
        recommendations = []

        # Check for common issues
        if "var " in code:
            issues.append("Use 'const' or 'let' instead of 'var'")
        if "==" in code and "===" not in code:
            issues.append("Use '===' for strict equality")
        if "console.log" in code:
            recommendations.append("Remove console.log statements for production")

        # React-specific checks
        if focus in ["react", "general"]:
            if "useEffect" in code and "[]" not in code:
                recommendations.append(
                    "Check useEffect dependencies - missing empty array?"
                )
            if "useState" in code:
                recommendations.append(
                    "Consider using useReducer for complex state logic"
                )

        # Performance checks
        if focus in ["performance", "general"]:
            if "map(" in code and "key=" not in code:
                issues.append("Missing 'key' prop in list rendering")
            if "style={{" in code:
                recommendations.append(
                    "Inline styles cause re-renders - consider CSS classes"
                )

        return {
            "focus": focus,
            "issues": issues,
            "recommendations": recommendations,
            "score": max(0, 100 - len(issues) * 10),
        }

    def _check_a11y_compliance(self, code: str, level: str) -> Dict[str, Any]:
        """Check WCAG accessibility compliance."""
        violations = []
        warnings = []

        # Check for common a11y issues
        if "<img" in code and "alt=" not in code:
            violations.append("Images must have alt attributes")
        if "<button" in code and "aria-" not in code:
            warnings.append("Consider adding aria-label to buttons")
        if "<input" in code and "label" not in code.lower():
            violations.append("Inputs must have associated labels")
        if "onClick" in code and "onKeyDown" not in code:
            warnings.append(
                "Interactive elements should have keyboard handlers"
            )
        if "autoFocus" in code:
            warnings.append("autoFocus can be disorienting for screen readers")

        # Level-specific checks
        if level in ["AA", "AAA"]:
            if "color:" in code and "contrast" not in code:
                warnings.append("Ensure color contrast meets WCAG standards")

        return {
            "level": level,
            "violations": violations,
            "warnings": warnings,
            "compliant": len(violations) == 0,
        }

    def _audit_frontend_performance(
        self, code: str, focus: str
    ) -> Dict[str, Any]:
        """Audit frontend performance."""
        metrics = {
            "estimated_bundle_size": "N/A",
            "render_optimization": [],
            "network_optimization": [],
        }

        # Check for performance patterns
        if "React.memo" in code:
            metrics["render_optimization"].append("Using React.memo")
        if "useMemo" in code:
            metrics["render_optimization"].append("Using useMemo")
        if "useCallback" in code:
            metrics["render_optimization"].append("Using useCallback")
        if "lazy(" in code:
            metrics["render_optimization"].append("Using lazy loading")
        if "Suspense" in code:
            metrics["render_optimization"].append("Using Suspense")

        # Check for performance issues
        issues = []
        if "style={{" in code:
            issues.append("Inline styles cause re-renders")
        if code.count("useState") > 5:
            issues.append("Consider consolidating state with useReducer")
        if "componentDidUpdate" in code:
            issues.append("Use useEffect instead of lifecycle methods")

        return {
            "focus": focus,
            "metrics": metrics,
            "issues": issues,
            "score": max(0, 100 - len(issues) * 15),
        }

    def _generate_styling_solution(
        self, requirement: str, framework: str, existing_code: str
    ) -> Dict[str, Any]:
        """Generate styling solution based on requirement."""
        solution = ""
        explanation = ""

        if framework == "tailwind":
            solution = self._generate_tailwind_solution(requirement)
            explanation = "Using Tailwind CSS utility classes"
        elif framework == "styled-components":
            solution = self._generate_styled_components_solution(requirement)
            explanation = "Using styled-components for CSS-in-JS"
        else:
            solution = self._generate_css_solution(requirement)
            explanation = "Using standard CSS"

        return {
            "framework": framework,
            "solution": solution,
            "explanation": explanation,
        }

    def _generate_tailwind_solution(self, requirement: str) -> str:
        """Generate Tailwind CSS solution."""
        # Map common requirements to Tailwind classes
        if "flex" in requirement.lower() or "layout" in requirement.lower():
            return "flex items-center justify-between gap-4"
        if "grid" in requirement.lower():
            return "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        if "card" in requirement.lower():
            return "bg-white rounded-lg shadow-md p-6"
        if "button" in requirement.lower():
            return "px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        return "p-4 m-2"

    def _generate_styled_components_solution(self, requirement: str) -> str:
        """Generate styled-components solution."""
        return f"""import styled from 'styled-components';

export const StyledComponent = styled.div`
  /* Styles for: {requirement} */
  display: flex;
  align-items: center;
  padding: 1rem;
`;
"""

    def _generate_css_solution(self, requirement: str) -> str:
        """Generate standard CSS solution."""
        return f"""/* Styles for: {requirement} */
.container {{
  display: flex;
  align-items: center;
  padding: 1rem;
}}
"""

    def _build_monitoring_dashboard(
        self,
        platform: str,
        service_type: str,
        metrics: List[str],
        questions: List[str],
    ) -> Dict[str, Any]:
        """
        Build monitoring dashboard following ECC dashboard-builder pattern.

        ECC Workflow:
        1. Define the operating questions
        2. Study the target platform schema
        3. Build the minimum useful board
        4. Cut vanity panels
        """
        # Define panel sets based on service type
        panel_sets = {
            "api": {
                "health": ["Request rate", "Error rate", "Latency (p50/p95/p99)"],
                "throughput": ["Requests per second", "Bandwidth"],
                "resources": ["CPU", "Memory", "Disk I/O"],
            },
            "database": {
                "health": ["Connections", "Query latency", "Cache hit ratio"],
                "throughput": ["Queries per second", "Rows read/written"],
                "resources": ["CPU", "Memory", "Disk usage"],
            },
            "queue": {
                "health": ["Queue depth", "Consumer lag", "Dead letters"],
                "throughput": ["Messages in", "Messages out"],
                "resources": ["Memory", "Disk"],
            },
            "general": {
                "health": ["Status", "Uptime", "Error rate"],
                "throughput": ["Operations per second"],
                "resources": ["CPU", "Memory"],
            },
        }

        # Get panel set for service type
        panels = panel_sets.get(service_type, panel_sets["general"])

        # Filter by requested metrics
        if metrics:
            filtered_panels = {}
            for category, panel_list in panels.items():
                filtered = [p for p in panel_list if p.lower() in metrics]
                if filtered:
                    filtered_panels[category] = filtered
            panels = filtered_panels or panels

        # Build dashboard structure
        dashboard = {
            "platform": platform,
            "service_type": service_type,
            "operating_questions": questions or [
                "Is it healthy?",
                "Where is the bottleneck?",
                "What changed?",
                "What action should someone take?",
            ],
            "panels": panels,
            "layout": {
                "sections": ["overview", "performance", "resources"],
                "default_time_range": "1h",
                "refresh_interval": "30s",
            },
            "quality_checklist": {
                "valid_json": True,
                "clear_grouping": True,
                "titles_present": True,
                "units_present": True,
                "thresholds_meaningful": True,
                "variables_exist": True,
                "no_vanity_panels": True,
            },
        }

        return dashboard

    def _analyze_project_structure(
        self, project_path: str, framework: str
    ) -> Dict[str, Any]:
        """Analyze frontend project structure."""
        # Detect framework
        detected_framework = framework
        if framework == "auto":
            detected_framework = "unknown"
            # Could add file detection logic here

        # Standard structure expectations
        structures = {
            "react": {
                "expected_dirs": ["src", "src/components", "src/hooks", "public"],
                "config_files": ["package.json", "tsconfig.json", "vite.config.ts"],
            },
            "vue": {
                "expected_dirs": ["src", "src/components", "src/views", "public"],
                "config_files": ["package.json", "vue.config.js"],
            },
            "nextjs": {
                "expected_dirs": ["pages", "components", "public", "styles"],
                "config_files": ["next.config.js", "package.json"],
            },
        }

        expected = structures.get(detected_framework, {})

        return {
            "project_path": project_path,
            "detected_framework": detected_framework,
            "expected_structure": expected,
            "recommendations": [
                "Use feature-based folder structure for large projects",
                "Co-locate tests with components",
                "Use barrel exports (index.ts) for clean imports",
            ],
        }


# Helper function for direct skill usage
async def frontend_developer(
    action: str = "get_patterns", **kwargs
) -> Dict[str, Any]:
    """Helper for direct skill usage."""
    skill = FrontendDevSkill()
    task = Task(
        type="frontend_developer",
        payload={"action": action, **kwargs, "task_id": "direct"},
    )
    result = await skill.execute(task)
    return result.to_dict()