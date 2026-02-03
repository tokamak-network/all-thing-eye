import os
import json
import httpx
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Protocol


class DiagnosisResultProtocol(Protocol):
    member_found: bool
    member_name: Optional[str]
    github_username: str
    identifiers: Dict[str, List[str]]
    activities_found: Dict[str, int]
    issues: List[str]
    recommendations: List[str]


@dataclass
class FixAction:
    action_type: str
    description: str
    script: Optional[str] = None


@dataclass
class FixResult:
    diagnosis_summary: str
    actions: List[FixAction] = field(default_factory=list)
    comment_body: str = ""


class AIFixer:
    DEFAULT_API_URL = "https://api.ai.tokamak.network"
    DEFAULT_MODEL = "litellm/claude-opus-4.5"

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("AI_API_KEY", "")
        self.api_url = api_url or os.environ.get("AI_API_URL", self.DEFAULT_API_URL)
        self.model = os.environ.get("AI_MODEL", self.DEFAULT_MODEL)

    def generate_identifier_insert_script(
        self, member_name: str, source: str, identifier_value: str
    ) -> str:
        return f"""// MongoDB script: add {source} identifier for {member_name}
db.member_identifiers.insertOne({{
    "member_name": "{member_name}",
    "source": "{source}",
    "identifier_value": "{identifier_value}"
}})
"""

    def generate_fix_without_ai(self, diagnosis: DiagnosisResultProtocol) -> FixResult:
        actions = []
        summary_parts = []

        if not diagnosis.member_found:
            summary_parts.append(
                f"Member not found for GitHub user '{diagnosis.github_username}'"
            )
            actions.append(
                FixAction(
                    action_type="manual_check",
                    description=(
                        f"Need to identify which member corresponds to "
                        f"GitHub user '{diagnosis.github_username}'"
                    ),
                )
            )
        else:
            summary_parts.append(f"Member: {diagnosis.member_name}")
            activity_sources = {s.lower() for s in diagnosis.activities_found.keys()}

            for source in ["github", "slack", "notion"]:
                has_identifier = (
                    source in diagnosis.identifiers
                    and diagnosis.identifiers.get(source)
                )

                if not has_identifier and source in activity_sources:
                    actions.append(
                        FixAction(
                            action_type="add_identifier",
                            description=(
                                f"Missing {source} identifier for "
                                f"{diagnosis.member_name}"
                            ),
                            script=None,
                        )
                    )

            for source, count in diagnosis.activities_found.items():
                if count == 0:
                    summary_parts.append(f"No {source} activities found")
                else:
                    summary_parts.append(f"{source}: {count} activities found")

        if not actions:
            actions.append(
                FixAction(
                    action_type="no_action",
                    description=(
                        "No automated fix needed - data may need manual investigation"
                    ),
                )
            )

        comment_body = self._generate_comment_body(diagnosis, actions)

        return FixResult(
            diagnosis_summary="; ".join(summary_parts),
            actions=actions,
            comment_body=comment_body,
        )

    def _generate_comment_body(
        self, diagnosis: DiagnosisResultProtocol, actions: List[FixAction]
    ) -> str:
        lines = ["## Automated Diagnosis Report\n"]

        if diagnosis.member_found:
            lines.append(f"**Member identified:** {diagnosis.member_name}")
            lines.append(f"**GitHub username:** {diagnosis.github_username}\n")

            if diagnosis.identifiers:
                lines.append("**Registered identifiers:**")
                for source, values in diagnosis.identifiers.items():
                    if values:
                        lines.append(f"- {source}: {', '.join(values)}")
                lines.append("")

            if diagnosis.activities_found:
                lines.append("**Activity check (last 30 days):**")
                for source, count in diagnosis.activities_found.items():
                    status = "found" if count > 0 else "not found"
                    emoji = "+" if count > 0 else "-"
                    lines.append(f"- {source}: {count} activities {status} [{emoji}]")
                lines.append("")
        else:
            lines.append(
                f"**Warning:** No member found for GitHub username "
                f"`{diagnosis.github_username}`"
            )
            lines.append("")

        if diagnosis.issues:
            lines.append("**Issues found:**")
            for issue in diagnosis.issues:
                lines.append(f"- {issue}")
            lines.append("")

        if diagnosis.recommendations:
            lines.append("**Recommendations:**")
            for rec in diagnosis.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        if actions:
            lines.append("**Suggested actions:**")
            for action in actions:
                action_emoji = {
                    "add_identifier": "[+]",
                    "manual_check": "[?]",
                    "no_action": "[-]",
                }.get(action.action_type, "[ ]")
                lines.append(f"- {action_emoji} {action.description}")
            lines.append("")

        lines.append("---")
        lines.append("*This report was generated automatically by issue-automation.*")

        return "\n".join(lines)

    async def generate_fix(self, diagnosis: DiagnosisResultProtocol) -> FixResult:
        if not self.api_key:
            return self.generate_fix_without_ai(diagnosis)

        prompt = self._build_claude_prompt(diagnosis)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/v1/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 1024,
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code != 200:
                    return self.generate_fix_without_ai(diagnosis)

                data = response.json()
                content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )

                if not content:
                    return self.generate_fix_without_ai(diagnosis)

                return self._parse_claude_response(content, diagnosis)

        except Exception:
            return self.generate_fix_without_ai(diagnosis)

    def _build_claude_prompt(self, diagnosis: DiagnosisResultProtocol) -> str:
        return f"""You are analyzing a data issue report for All-Thing-Eye, a team activity tracking system.

Diagnosis:
- Member found: {diagnosis.member_found}
- Member name: {diagnosis.member_name}
- GitHub username: {diagnosis.github_username}
- Registered identifiers: {json.dumps(diagnosis.identifiers, indent=2)}
- Activities found: {json.dumps(diagnosis.activities_found, indent=2)}
- Issues: {diagnosis.issues}
- Recommendations: {diagnosis.recommendations}

Based on this diagnosis, suggest specific actions to fix the data issue.
Focus on:
1. Missing identifier mappings in member_identifiers collection
2. Whether data collection might be failing
3. Whether this is a false alarm (data actually exists)

Respond in JSON format:
{{
    "summary": "brief summary of the situation",
    "actions": [
        {{"type": "add_identifier|manual_check|no_action", "description": "what to do"}}
    ]
}}"""

    def _parse_claude_response(
        self, content: str, diagnosis: DiagnosisResultProtocol
    ) -> FixResult:
        try:
            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))

                actions = []
                for action_data in data.get("actions", []):
                    actions.append(
                        FixAction(
                            action_type=action_data.get("type", "manual_check"),
                            description=action_data.get("description", ""),
                        )
                    )

                if not actions:
                    actions.append(
                        FixAction(
                            action_type="no_action",
                            description="No specific action recommended by AI",
                        )
                    )

                comment_body = self._generate_comment_body(diagnosis, actions)

                return FixResult(
                    diagnosis_summary=data.get("summary", "AI analysis complete"),
                    actions=actions,
                    comment_body=comment_body,
                )
        except (json.JSONDecodeError, KeyError):
            pass

        return self.generate_fix_without_ai(diagnosis)
