"""
Report Agent service
Implements ReACT-pattern simulation report generation using LangChain + Zep

Features:
1. Generate reports based on simulation requirements and Zep graph info
2. Plan outline structure first, then generate sections
3. Each section uses ReACT multi-round thinking and reflection
4. Support user conversation with autonomous retrieval tool invocation
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..models.prediction_ledger import PredictionLedgerManager
from ..utils.llm_client import LLMClient, UsageAccumulator
from ..utils.logger import get_logger
from ..utils.locale import get_llm_language_instruction, normalize_locale_code
from .artifact_store import REPORT_NAMESPACE, get_artifact_store
from .live_evidence import LiveEvidenceService
from .perplexity_provider import PerplexityProvider
from .source_manifest import SourceEntry, SourceManifest
from .zep_tools import (
    ZepToolsService, 
    SearchResult, 
    InsightForgeResult, 
    PanoramaResult,
    InterviewResult
)

logger = get_logger('agenikpredict.report_agent')


ANALYSIS_MODE_QUICK = "quick"
ANALYSIS_MODE_GLOBAL = "global"
ALLOWED_ANALYSIS_MODES = {ANALYSIS_MODE_QUICK, ANALYSIS_MODE_GLOBAL}


def normalize_analysis_mode(mode: Optional[str]) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized in ALLOWED_ANALYSIS_MODES:
        return normalized
    return ANALYSIS_MODE_GLOBAL


class ReportLogger:
    """
    Report Agent detailed logger
    
    Generates agent_log.jsonl file in report folder, recording each detailed action.
    Each line is a complete JSON object containing timestamp, action type, detailed content, etc.
    """
    
    def __init__(self, report_id: str):
        """
        Initialize logger
        
        Args:
            report_id: Report ID, used to determine log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            ReportManager._get_report_folder(report_id, ensure=True), 'agent_log.jsonl'
        )
        self.start_time = datetime.now()
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """Ensure log file directory exists"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _get_elapsed_time(self) -> float:
        """Get elapsed time from start (seconds)"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def log(
        self, 
        action: str, 
        stage: str,
        details: Dict[str, Any],
        section_title: str = None,
        section_index: int = None
    ):
        """
        Log an entry
        
        Args:
            action: Action type, e.g. 'start', 'tool_call', 'llm_response', 'section_complete'
            stage: Current stage, e.g. 'planning', 'generating', 'completed'
            details: Detail dictionary, not truncated
            section_title: Current section title (optional)
            section_index: Current section index (optional)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(self._get_elapsed_time(), 2),
            "report_id": self.report_id,
            "action": action,
            "stage": stage,
            "section_title": section_title,
            "section_index": section_index,
            "details": details
        }
        
        # Append to JSONL file
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        ReportManager.flush_report(self.report_id)
    
    def log_start(self, simulation_id: str, graph_id: str, simulation_requirement: str, analysis_mode: str = ANALYSIS_MODE_GLOBAL):
        """Log report generation start"""
        self.log(
            action="report_start",
            stage="pending",
            details={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "analysis_mode": analysis_mode,
                "simulation_requirement": simulation_requirement,
                "message": "Report generation task started"
            }
        )
    
    def log_planning_start(self):
        """Log outline planning start"""
        self.log(
            action="planning_start",
            stage="planning",
            details={"message": "Starting report outline planning"}
        )
    
    def log_planning_context(self, context: Dict[str, Any]):
        """Log context info obtained during planning"""
        self.log(
            action="planning_context",
            stage="planning",
            details={
                "message": "Obtaining simulation context info",
                "context": context
            }
        )
    
    def log_planning_complete(self, outline_dict: Dict[str, Any]):
        """Log outline planning complete"""
        self.log(
            action="planning_complete",
            stage="planning",
            details={
                "message": "Outline planning complete",
                "outline": outline_dict
            }
        )
    
    def log_section_start(self, section_title: str, section_index: int):
        """Log section generation start"""
        self.log(
            action="section_start",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={"message": f"Starting section generation: {section_title}"}
        )
    
    def log_react_thought(self, section_title: str, section_index: int, iteration: int, thought: str):
        """Log ReACT thinking process"""
        self.log(
            action="react_thought",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "thought": thought,
                "message": f"ReACT iteration {iteration} thinking"
            }
        )
    
    def log_tool_call(
        self, 
        section_title: str, 
        section_index: int,
        tool_name: str, 
        parameters: Dict[str, Any],
        iteration: int
    ):
        """Log tool call"""
        self.log(
            action="tool_call",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "parameters": parameters,
                "message": f"Tool call: {tool_name}"
            }
        )
    
    def log_tool_result(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        result: str,
        iteration: int
    ):
        """Log tool call result (full content, not truncated)"""
        self.log(
            action="tool_result",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "result": result,  # Full result, no truncation
                "result_length": len(result),
                "message": f"Tool {tool_name} returned result"
            }
        )
    
    def log_llm_response(
        self,
        section_title: str,
        section_index: int,
        response: str,
        iteration: int,
        has_tool_calls: bool,
        has_final_answer: bool
    ):
        """Log LLM response (full content, not truncated)"""
        self.log(
            action="llm_response",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "response": response,  # Full response, no truncation
                "response_length": len(response),
                "has_tool_calls": has_tool_calls,
                "has_final_answer": has_final_answer,
                "message": f"LLM response (tool calls: {has_tool_calls}, final answer: {has_final_answer})"
            }
        )
    
    def log_section_content(
        self,
        section_title: str,
        section_index: int,
        content: str,
        tool_calls_count: int
    ):
        """Log section content generation complete (content only, does not mean entire section is complete)"""
        self.log(
            action="section_content",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": content,  # Full content, no truncation
                "content_length": len(content),
                "tool_calls_count": tool_calls_count,
                "message": f"Section {section_title} content generation complete"
            }
        )
    
    def log_section_full_complete(
        self,
        section_title: str,
        section_index: int,
        full_content: str
    ):
        """
        Log section generation complete

        Frontend should listen to this log to determine if a section is truly complete and get full content
        """
        self.log(
            action="section_complete",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": full_content,
                "content_length": len(full_content),
                "message": f"Section {section_title} generation complete"
            }
        )
    
    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        """Log report generation complete"""
        self.log(
            action="report_complete",
            stage="completed",
            details={
                "total_sections": total_sections,
                "total_time_seconds": round(total_time_seconds, 2),
                "message": "Report generation complete"
            }
        )
    
    def log_error(self, error_message: str, stage: str, section_title: str = None):
        """Log error"""
        self.log(
            action="error",
            stage=stage,
            section_title=section_title,
            section_index=None,
            details={
                "error": error_message,
                "message": f"Error occurred: {error_message}"
            }
        )


class ReportConsoleLogger:
    """
    Report Agent console logger
    
    Writes console-style logs (INFO, WARNING, etc.) to console_log.txt file in report folder.
    These logs are different from agent_log.jsonl, being plain text console output.
    """
    
    def __init__(self, report_id: str):
        """
        Initialize console logger
        
        Args:
            report_id: Report ID, used to determine log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            ReportManager._get_report_folder(report_id, ensure=True), 'console_log.txt'
        )
        self._ensure_log_file()
        self._file_handler = None
        self._setup_file_handler()
    
    def _ensure_log_file(self):
        """Ensure log file directory exists"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _setup_file_handler(self):
        """Set up file handler to write logs to file simultaneously"""
        import logging

        report_id = self.report_id

        class _ArtifactFlushingFileHandler(logging.FileHandler):
            def emit(self_inner, record):
                super().emit(record)
                self_inner.flush()
                ReportManager.flush_report(report_id)
        
        # Create file handler
        self._file_handler = _ArtifactFlushingFileHandler(
            self.log_file_path,
            mode='a',
            encoding='utf-8'
        )
        self._file_handler.setLevel(logging.INFO)
        
        # Use same concise format as console
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self._file_handler.setFormatter(formatter)
        
        # Add to report_agent related loggers
        loggers_to_attach = [
            'agenikpredict.report_agent',
            'agenikpredict.zep_tools',
        ]
        
        for logger_name in loggers_to_attach:
            target_logger = logging.getLogger(logger_name)
            # Avoid duplicate adding
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)
    
    def close(self):
        """Close file handler and remove from loggers"""
        import logging
        
        if self._file_handler:
            loggers_to_detach = [
                'agenikpredict.report_agent',
                'agenikpredict.zep_tools',
            ]
            
            for logger_name in loggers_to_detach:
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)
            
            self._file_handler.close()
            self._file_handler = None
    
    def __del__(self):
        """Ensure file handler is closed on destruction"""
        self.close()


class ReportStatus(str, Enum):
    """Report status"""
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """Report section"""
    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content
        }

    def to_markdown(self, level: int = 2) -> str:
        """Convert to Markdown format"""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """Report outline"""
    title: str
    summary: str
    sections: List[ReportSection]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    def to_markdown(self) -> str:
        """Convert to Markdown format"""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """Complete report"""
    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    prediction_summary: Optional[Dict[str, Any]] = None
    language_used: str = "en"
    analysis_mode: str = ANALYSIS_MODE_GLOBAL
    source_manifest_summary: Dict[str, Any] = field(default_factory=dict)
    explainability: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "usage": self.usage,
            "prediction_summary": self.prediction_summary,
            "language_used": self.language_used,
            "analysis_mode": normalize_analysis_mode(self.analysis_mode),
            "source_manifest_summary": dict(self.source_manifest_summary or {}),
            "explainability": dict(self.explainability or {}),
        }


@dataclass
class ToolExecutionResult:
    text: str
    sources: List[SourceEntry] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# Prompt template constants
# ═══════════════════════════════════════════════════════════════

# -- Tool descriptions --

TOOL_DESC_INSIGHT_FORGE = """\
[Deep Insight Retrieval - Powerful retrieval tool]
This is our powerful retrieval function, designed for deep analysis. It will:
1. Automatically decompose your question into multiple sub-questions
2. Retrieve information from multiple dimensions in the simulation graph
3. Integrate results from semantic search, entity analysis, and relationship chain tracking
4. Return the most comprehensive and in-depth retrieval content

[Use cases]
- Need to deeply analyze a topic
- Need to understand multiple aspects of an event
- Need to obtain rich material supporting report sections

[Return content]
- Related fact texts (can be directly quoted)
- Core entity insights
- Relationship chain analysis"""

TOOL_DESC_PANORAMA_SEARCH = """\
[Breadth Search - Get full picture view]
This tool is used to get a complete overview of simulation results, especially suitable for understanding event evolution. It will:
1. Get all related nodes and relationships
2. Distinguish between currently valid facts and historical/expired facts
3. Help you understand how public opinion evolved

[Use cases]
- Need to understand the complete development trajectory of an event
- Need to compare public opinion changes across different stages
- Need comprehensive entity and relationship information

[Return content]
- Currently valid facts (latest simulation results)
- Historical/expired facts (evolution records)
- All involved entities"""

TOOL_DESC_QUICK_SEARCH = """\
[Simple Search - Quick retrieval]
Lightweight quick retrieval tool, suitable for simple, direct information queries.

[Use cases]
- Need to quickly find specific information
- Need to verify a fact
- Simple information retrieval

[Return content]
- List of facts most relevant to the query"""

TOOL_DESC_INTERVIEW_AGENTS = """\
[Deep Interview - Real Agent Interview (dual platform)]
Calls the OASIS simulation environment interview API to conduct real interviews with running simulation Agents!
This is not LLM simulation, but calls the real interview interface to get simulation Agent original responses.
By default interviews on both Twitter and Reddit platforms simultaneously for more comprehensive perspectives.

Workflow:
1. Automatically reads persona files to learn about all simulation Agents
2. Intelligently selects Agents most relevant to the interview topic (e.g., students, media, officials)
3. Automatically generates interview questions
4. Calls /api/simulation/interview/batch endpoint for real interviews on both platforms
5. Integrates all interview results, providing multi-perspective analysis

[Use cases]
- Need to understand event perspectives from different roles (How do students see it? Media? Officials?)
- Need to collect opinions and positions from multiple parties
- Need to get real responses from simulation Agents (from OASIS simulation environment)
- Want to make reports more vivid with "interview transcripts"

[Return content]
- Identity information of interviewed Agents
- Each Agent's interview responses on both Twitter and Reddit platforms
- Key quotes (can be directly quoted)
- Interview summary and viewpoint comparison

[Important] Requires OASIS simulation environment to be running!"""

TOOL_DESC_LIVE_NEWS_BRIEF = """\
[Live News Brief - Current-world headlines]
Retrieves recent public headlines for a query from a live news RSS provider.
Use this to validate whether the outside world has materially changed since the
uploaded documents were collected.

[Use cases]
- Need to check current public developments around a company, issue, or event
- Need recent headlines to compare with graph/simulation output
- Need external evidence with timestamps and source links

[Return content]
- Recent headlines
- Source names
- Published timestamps
- Source links
- Retrieval warnings if live data is unavailable"""

TOOL_DESC_LIVE_MARKET_SNAPSHOT = """\
[Live Market Snapshot - Current market context]
Retrieves current quotes for ticker symbols detected in the query or report context.
Use this to anchor the report in current market conditions, not only simulated reactions.

[Use cases]
- Need to validate current stock/market context
- Need price/change context for a ticker already mentioned in the analysis
- Need to compare simulation expectations with live market movement

[Return content]
- Detected ticker symbols
- Current quotes and percent changes
- Exchange and currency info
- Retrieval warnings if market data is unavailable"""

TOOL_DESC_WEB_SEARCH = """\
[Web Search - Discovery only]
Retrieves structured web search results from an external discovery provider.
Use this only to widen discovery and synthesis around recent public information.
It is not the canonical source of market truth.

[Use cases]
- Need discovery across current public web coverage
- Need corroborating external sources for non-market developments
- Need a fast synthesis pass on recent outside-world reporting

[Return content]
- Search result titles
- Snippets
- Published/updated timestamps when available
- Source links
- Retrieval warnings if web search is unavailable"""

PROBABILITY_SUMMARY_SYSTEM_PROMPT = """\
You are converting a simulation report into a structured scenario summary.

Your job is to produce a concise JSON object with exactly three scenarios:
- Bull case
- Base case
- Bear case

Requirements:
1. Return valid JSON only.
2. Use integer probabilities that sum to 100 after your best effort.
3. Stay grounded in the report content and simulation requirement; do not invent unsupported claims.
4. Keep each summary concise and specific.
5. Use arrays for drivers, risks, and assumptions (3-5 items each when possible).
6. Keep the scenario `name` values exactly as English keys: `Bull case`, `Base case`, `Bear case`.
7. All other descriptive fields may follow the requested report language.

Output schema:
{
  "forecast_horizon": "string",
  "confidence_note": "string",
  "scenarios": [
    {
      "name": "Bull case",
      "probability": 0,
      "timeframe": "string",
      "summary": "string",
      "key_drivers": ["string"],
      "key_risks": ["string"],
      "assumptions": ["string"]
    },
    {
      "name": "Base case",
      "probability": 0,
      "timeframe": "string",
      "summary": "string",
      "key_drivers": ["string"],
      "key_risks": ["string"],
      "assumptions": ["string"]
    },
    {
      "name": "Bear case",
      "probability": 0,
      "timeframe": "string",
      "summary": "string",
      "key_drivers": ["string"],
      "key_risks": ["string"],
      "assumptions": ["string"]
    }
  ],
  "caveats": ["string"]
}"""

EXPLAINABILITY_SYSTEM_PROMPT = """\
You are generating a compact explainability block for a completed simulation report.

Requirements:
1. Return valid JSON only.
2. Keep all descriptive text in the requested report language.
3. Stay grounded in the report content and provided source shortlist.
4. `why_this_conclusion` must be one concise paragraph.
5. `basis_summary` must be 3-5 short bullet-style strings.
6. `source_ids` must reference source IDs from the provided shortlist only.
7. Do not invent source IDs or unsupported claims.

Output schema:
{
  "why_this_conclusion": "string",
  "basis_summary": ["string"],
  "source_ids": ["src_123"]
}"""

# -- Outline planning prompt --

PLAN_SYSTEM_PROMPT = """\
You are an expert in writing "Future Prediction Reports", with a "God's eye view" of the simulated world - you can observe every Agent's behavior, speech, and interactions in the simulation.

[Core Philosophy]
We have built a simulated world and injected specific "simulation requirements" as variables. The evolution results of the simulated world are predictions of what may happen in the future. What you are observing is not "experimental data", but a "rehearsal of the future".

[Your Task]
Write a "Future Prediction Report" answering:
1. Under our set conditions, what happened in the future?
2. How did various types of Agents (groups) react and act?
3. What noteworthy future trends and risks does this simulation reveal?

[Report Positioning]
- This is a simulation-based future prediction report, revealing "if this happens, what will the future look like"
- Focus on prediction results: event trajectory, group reactions, emergent phenomena, potential risks
- Agent behaviors in the simulated world are predictions of future group behavior
- NOT an analysis of current real-world conditions
- NOT a generic public opinion overview

[Section Count Limit]
- Minimum 2 sections, maximum 5 sections
- No sub-sections needed, each section has complete content
- Content should be concise, focusing on core prediction findings
- Section structure is designed by you based on prediction results

Please output the report outline in JSON format as follows:
{
    "title": "Report title",
    "summary": "Report summary (one sentence summarizing core prediction findings)",
    "sections": [
        {
            "title": "Section title",
            "description": "Section content description"
        }
    ]
}

Note: sections array must have at least 2 and at most 5 elements!"""

PLAN_USER_PROMPT_TEMPLATE = """\
[Prediction Scenario Setup]
Variable injected into the simulated world (simulation requirement): {simulation_requirement}

[Simulated World Scale]
- Number of entities in simulation: {total_nodes}
- Number of relationships between entities: {total_edges}
- Entity type distribution: {entity_types}
- Number of active Agents: {total_entities}

[Simulated future fact samples]
{related_facts_json}

Review this future rehearsal from a "God's eye view":
1. Under our set conditions, what state did the future present?
2. How did various groups (Agents) react and act?
3. What noteworthy future trends does this simulation reveal?

Design the most suitable report section structure based on prediction results.

[Reminder] Report section count: minimum 2, maximum 5, content should be concise and focused on core prediction findings."""

# -- Section generation prompt --

SECTION_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert in writing "Future Prediction Reports", currently writing one section of the report.

Report title: {report_title}
Report summary: {report_summary}
Prediction scenario (simulation requirement): {simulation_requirement}

Current section to write: {section_title}

═══════════════════════════════════════════════════════════════
[Core Philosophy]
═══════════════════════════════════════════════════════════════

The simulated world is a rehearsal of the future. We injected specific conditions (simulation requirements) into the simulated world.
The behavior and interactions of Agents in the simulation are predictions of future group behavior.

Your task is to:
- Reveal what happened in the future under the set conditions
- Predict how various groups (Agents) reacted and acted
- Discover noteworthy future trends, risks, and opportunities

Do NOT write it as an analysis of current real-world conditions
DO focus on "what will the future look like" - simulation results ARE the predicted future

═══════════════════════════════════════════════════════════════
[Most Important Rules - Must Follow]
═══════════════════════════════════════════════════════════════

1. [Must call tools to observe the simulated world]
   - You are observing the future rehearsal from a "God's eye view"
   - All content must come from events and Agent behaviors in the simulated world
   - Do NOT use your own knowledge to write report content
   - Each section must call tools at least {min_tool_calls} times (max {max_tool_calls}) to observe the simulated world representing the future

2. [Must quote Agents' original speech and actions]
   - Agent speech and behavior are predictions of future group behavior
   - Use quote format in the report to present these predictions, e.g.:
     > "A certain group would say: original content..."
   - These quotes are core evidence of simulation predictions

3. [Language consistency - quoted content must be translated to report language]
   - Tool-returned content may contain English or mixed language expressions
   - The report language should match the simulation requirement language
   - When quoting content returned by tools, translate it to match the report language
   - Maintain original meaning during translation, ensure natural and fluent expression
   - This rule applies to both body text and quote blocks (> format)

4. [Faithfully present prediction results]
   - Report content must reflect simulation results representing the future
   - Do not add information that does not exist in the simulation
   - If information is insufficient in some aspects, state this honestly

═══════════════════════════════════════════════════════════════
[Format Specification - Extremely Important!]
═══════════════════════════════════════════════════════════════

[One section = minimum content unit]
- Each section is the smallest unit of the report
- DO NOT use any Markdown headings (#, ##, ###, #### etc.) within a section
- DO NOT add section title at the beginning of content
- Section title is automatically added by the system, you only write plain body text
- Use **bold**, paragraph breaks, quotes, and lists to organize content, but no headings

[Correct example]
```
This section analyzes the public opinion propagation trends. Through in-depth analysis of simulation data, we found...

**Initial Outbreak Phase**

The platform served as the first scene of public opinion, taking on the core function of information release:

> "The platform contributed 68% of the initial voice volume..."

**Sentiment Amplification Phase**

Short-video platforms further amplified the event's impact:

- Strong visual impact
- High emotional resonance
```

[Wrong example]
```
## Executive Summary          <- Wrong! Do not add any headings
### 1. Initial Phase          <- Wrong! Do not use ### for subsections
#### 1.1 Detailed Analysis    <- Wrong! Do not use #### for sub-subsections

This section analyzes...
```

═══════════════════════════════════════════════════════════════
[Available Retrieval Tools] (call {min_tool_calls}-{max_tool_calls} times per section)
═══════════════════════════════════════════════════════════════

{tools_description}

[Tool Usage Tips - Mix different tools, do not use only one]
- Mix graph retrieval, agent interviews, and live-current-world evidence when useful
- Prefer graph tools for structural simulation reasoning and causal chains
- Use live tools to validate current headlines and market context, not to replace graph evidence
- Use quick retrieval for fact checks and deeper tools for synthesis

═══════════════════════════════════════════════════════════════
[Workflow]
═══════════════════════════════════════════════════════════════

Each response you can only do one of the following two things (not both):

Option A - Call a tool:
Output your thinking, then call a tool using the following format:
<tool_call>
{{"name": "tool_name", "parameters": {{"param_name": "param_value"}}}}
</tool_call>
The system will execute the tool and return results to you. You do not need to and cannot write tool results yourself.

Option B - Output final content:
When you have obtained sufficient information through tools, output section content starting with "Final Answer:".

Strict prohibitions:
- Do NOT include both tool calls and Final Answer in one response
- Do NOT fabricate tool return results (Observation), all tool results are injected by the system
- Call at most one tool per response

═══════════════════════════════════════════════════════════════
[Section Content Requirements]
═══════════════════════════════════════════════════════════════

1. Content must be based on simulation data retrieved by tools
2. Extensively quote original text to demonstrate simulation effects
3. Use Markdown format (but headings are prohibited):
   - Use **bold text** to mark key points (instead of sub-headings)
   - Use lists (- or 1.2.3.) to organize points
   - Use blank lines to separate paragraphs
   - DO NOT use #, ##, ###, #### or any heading syntax
4. [Quote format specification - must be standalone paragraphs]
   Quotes must be standalone paragraphs with blank lines before and after, not mixed in paragraphs:

   Correct format:
   ```
   The response was considered lacking substance.

   > "The response pattern appeared rigid and slow in the fast-changing social media environment."

   This assessment reflects widespread public dissatisfaction.
   ```

   Wrong format:
   ```
   The response was considered lacking substance. > "The response pattern..." This assessment reflects...
   ```
5. Maintain logical coherence with other sections
6. [Avoid repetition] Carefully read completed sections below, do not repeat the same information
7. [Emphasis] Do not add any headings! Use **bold** instead of subsection headings"""

SECTION_USER_PROMPT_TEMPLATE = """\
Completed section content (read carefully to avoid repetition):
{previous_content}

═══════════════════════════════════════════════════════════════
[Current Task] Write section: {section_title}
═══════════════════════════════════════════════════════════════

[Important Reminders]
1. Carefully read the completed sections above to avoid repeating the same content!
2. You must call tools to get simulation data before starting
3. Mix different tools, do not use only one
4. Report content must come from retrieval results, do not use your own knowledge

[Format Warning - Must Follow]
- DO NOT write any headings (#, ##, ###, #### are all prohibited)
- DO NOT write "{section_title}" as the beginning
- Section title is automatically added by the system
- Write body text directly, use **bold** instead of subsection headings

Please begin:
1. First think (Thought) about what information this section needs
2. Then call tools (Action) to get simulation data
3. After collecting enough information, output Final Answer (pure body text, no headings)"""

# -- ReACT loop message templates --

REACT_OBSERVATION_TEMPLATE = """\
Observation (retrieval results):

=== Tool {tool_name} returned ===
{result}

═══════════════════════════════════════════════════════════════
Tools called {tool_calls_count}/{max_tool_calls} times (used: {used_tools_str}) {unused_hint}
- If information is sufficient: output section content starting with "Final Answer:" (must cite the above original text)
- If more information is needed: call a tool to continue retrieval
═══════════════════════════════════════════════════════════════"""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "[Note] You have only called {tool_calls_count} tools, at least {min_tool_calls} times required. "
    "Please call more tools to get more simulation data before outputting Final Answer. {unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    "Currently only {tool_calls_count} tool calls made, at least {min_tool_calls} required. "
    "Please call tools to get simulation data. {unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "Tool call limit reached ({tool_calls_count}/{max_tool_calls}), no more tool calls allowed."
    'Please immediately output section content starting with "Final Answer:" based on obtained information.'
)

REACT_UNUSED_TOOLS_HINT = "\n Tip: You have not used: {unused_list}, try different tools for multi-angle information"

REACT_FORCE_FINAL_MSG = "Tool call limit reached, please directly output Final Answer: and generate section content."

# -- Chat prompt --

CHAT_SYSTEM_PROMPT_TEMPLATE = """\
You are a concise and efficient simulation prediction assistant.

[Background]
Prediction conditions: {simulation_requirement}

[Generated Analysis Report]
{report_content}

[Rules]
1. Prioritize answering based on the above report content
2. Answer questions directly, avoid lengthy reasoning
3. Only call tools for more data when report content is insufficient
4. Answers should be concise, clear, and organized

[Available Tools] (use only when needed, max 1-2 calls)
{tools_description}

[Tool Call Format]
<tool_call>
{{"name": "tool_name", "parameters": {{"param_name": "param_value"}}}}
</tool_call>

[Answer Style]
- Concise and direct, avoid lengthy discourse
- Use > format to quote key content
- Give conclusion first, then explain reasons"""

CHAT_OBSERVATION_SUFFIX = "\n\nPlease answer the question concisely."


# ═══════════════════════════════════════════════════════════════
# ReportAgent main class
# ═══════════════════════════════════════════════════════════════


class ReportAgent:
    """
    Report Agent - Simulation report generation Agent

    Uses ReACT (Reasoning + Acting) pattern:
    1. Planning phase: Analyze simulation requirements, plan report outline structure
    2. Generation phase: Generate content section by section, each section can call tools multiple times
    3. Reflection phase: Check content completeness and accuracy
    """
    
    # Legacy defaults retained for compatibility/reference; runtime uses instance values.
    MAX_TOOL_CALLS_PER_SECTION = 5
    MAX_REFLECTION_ROUNDS = 3
    
    # Max tool calls per chat
    MAX_TOOL_CALLS_PER_CHAT = 2
    
    def __init__(
        self,
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None,
        language: Optional[str] = None,
        custom_persona: str = '',
        report_variables: dict = None,
        analysis_mode: str = ANALYSIS_MODE_GLOBAL,
    ):
        """
        Initialize Report Agent

        Args:
            graph_id: Graph ID
            simulation_id: Simulation ID
            simulation_requirement: Simulation requirement description
            llm_client: LLM client (optional)
            zep_tools: Zep tools service (optional)
            language: Locale code (e.g. 'en', 'ru') for LLM response language
            custom_persona: Custom analysis perspective for the report
            report_variables: Additional parameters to include in prompts
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement
        self.language = normalize_locale_code(language)
        self.language_instruction = get_llm_language_instruction(self.language)
        self.custom_persona = custom_persona or ''
        self.report_variables = report_variables or {}
        self.analysis_mode = normalize_analysis_mode(analysis_mode)

        self.llm = llm_client or LLMClient()
        self.zep_tools = zep_tools or ZepToolsService()
        self.live_evidence = LiveEvidenceService()
        self.perplexity = PerplexityProvider()
        self.usage = UsageAccumulator()
        self.source_manifest: Optional[SourceManifest] = None

        configured_tool_calls = max(1, int(getattr(Config, "REPORT_AGENT_MAX_TOOL_CALLS", self.MAX_TOOL_CALLS_PER_SECTION)))
        configured_reflection_rounds = max(1, int(getattr(Config, "REPORT_AGENT_MAX_REFLECTION_ROUNDS", self.MAX_REFLECTION_ROUNDS)))
        if self.analysis_mode == ANALYSIS_MODE_QUICK:
            self.max_tool_calls_per_section = min(configured_tool_calls, 2)
            self.max_reflection_rounds = min(configured_reflection_rounds, 2)
            self.min_tool_calls_per_section = 1
        else:
            self.max_tool_calls_per_section = configured_tool_calls
            self.max_reflection_rounds = configured_reflection_rounds
            self.min_tool_calls_per_section = min(3, self.max_tool_calls_per_section)

        # Tool definitions
        self.tools = self._define_tools()

        # Logger (initialized in generate_report)
        self.report_logger: Optional[ReportLogger] = None
        # Console logger (initialized in generate_report)
        self.console_logger: Optional[ReportConsoleLogger] = None
        
        logger.info(
            "ReportAgent initialized: graph_id=%s, simulation_id=%s, analysis_mode=%s, tool_limit=%s, reflection_limit=%s",
            graph_id,
            simulation_id,
            self.analysis_mode,
            self.max_tool_calls_per_section,
            self.max_reflection_rounds,
        )
    
    def _build_variables_context(self) -> str:
        """Format report_variables into a prompt section."""
        if not self.report_variables:
            return ''
        lines = ['\n[Report Parameters]']
        for key, value in self.report_variables.items():
            lines.append(f'- {key}: {value}')
        return '\n'.join(lines)

    def _build_persona_prefix(self) -> str:
        """Return the custom persona as a prompt prefix."""
        if not self.custom_persona:
            return ''
        return f'\n[Custom Analysis Perspective]\n{self.custom_persona}\n'

    def _outline_section_bounds(self) -> Tuple[int, int]:
        if self.analysis_mode == ANALYSIS_MODE_QUICK:
            return 2, 3
        return 2, 5

    def _allowed_legacy_aliases(self) -> set[str]:
        aliases = {"search_graph"}
        if self.analysis_mode == ANALYSIS_MODE_GLOBAL:
            aliases.update({
                "get_graph_statistics",
                "get_entity_summary",
                "get_entities_by_type",
                "get_simulation_context",
            })
        return aliases

    def _make_source_entry(
        self,
        *,
        provider: str,
        source_type: str,
        query: str = "",
        title: str = "",
        url: str = "",
        snippet: str = "",
        published_at: Optional[str] = None,
        last_updated: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> SourceEntry:
        return SourceEntry.create(
            provider=provider,
            source_type=source_type,
            query=query,
            title=title,
            url=url,
            snippet=snippet,
            published_at=published_at,
            last_updated=last_updated,
            language=self.language,
            extra=extra,
        )

    @staticmethod
    def _preview(value: Any, limit: int = 400) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."

    def _record_tool_result(self, result: ToolExecutionResult) -> None:
        if not self.source_manifest:
            return
        self.source_manifest.add_sources(result.sources)
        for warning in result.warnings:
            self.source_manifest.add_warning(warning)

    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define available tools"""
        tools = {
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "Search query for relevance ranking",
                    "include_expired": "Whether to include expired/historical content (default True)"
                }
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "Search query string",
                    "limit": "Number of results to return (optional, default 10)"
                }
            }
        }
        if self.analysis_mode == ANALYSIS_MODE_GLOBAL:
            tools["insight_forge"] = {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "The question or topic you want to deeply analyze",
                    "report_context": "Current report section context (optional, helps generate more precise sub-questions)"
                }
            }
            tools["interview_agents"] = {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "Interview topic or requirement description (e.g., 'understand students' views on the dormitory incident')",
                    "max_agents": "Maximum number of Agents to interview (optional, default 5, max 10)"
                }
            }
        if self.live_evidence.enabled:
            tools["live_news_brief"] = {
                "name": "live_news_brief",
                "description": TOOL_DESC_LIVE_NEWS_BRIEF,
                "parameters": {
                    "query": "Query string for recent live headlines",
                    "max_items": "Maximum number of live headlines to return (optional, default 5)"
                }
            }
            tools["live_market_snapshot"] = {
                "name": "live_market_snapshot",
                "description": TOOL_DESC_LIVE_MARKET_SNAPSHOT,
                "parameters": {
                    "query": "Query string containing the company/ticker/topic you want current market context for",
                    "context": "Additional context text to help detect ticker symbols (optional)",
                    "max_symbols": "Maximum number of ticker symbols to resolve (optional, default 5)"
                }
            }
        if self.analysis_mode == ANALYSIS_MODE_GLOBAL and self.perplexity.available:
            tools["web_search"] = {
                "name": "web_search",
                "description": TOOL_DESC_WEB_SEARCH,
                "parameters": {
                    "query": "Search query string",
                    "max_results": "Maximum number of web search results to return (optional, default 5)"
                }
            }
        return tools
    
    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], report_context: str = "") -> ToolExecutionResult:
        """
        Execute tool call
        
        Args:
            tool_name: Tool name
            parameters: Tool parameters
            report_context: Report context (for InsightForge)
            
        Returns:
            Structured tool execution result
        """
        logger.info(f"Executing tool: {tool_name}, parameters: {parameters}")
        
        try:
            if self.analysis_mode == ANALYSIS_MODE_QUICK and tool_name in {
                "get_graph_statistics",
                "get_entity_summary",
                "get_entities_by_type",
                "get_simulation_context",
            }:
                message = f"{tool_name} is unavailable in quick mode."
                return ToolExecutionResult(text=message, warnings=[message])

            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.zep_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx
                )
                sources = [
                    self._make_source_entry(
                        provider="zep_graph",
                        source_type="graph_fact",
                        query=query,
                        title=f"InsightForge fact {index}",
                        snippet=fact,
                        extra={"tool": tool_name, "report_context": self._preview(ctx, 200)},
                    )
                    for index, fact in enumerate((result.semantic_facts or [])[:8], start=1)
                ]
                if not sources:
                    sources.append(
                        self._make_source_entry(
                            provider="zep_graph",
                            source_type="graph_summary",
                            query=query,
                            title="InsightForge summary",
                            snippet=self._preview(result.to_text(), 500),
                            extra={
                                "tool": tool_name,
                                "total_facts": result.total_facts,
                                "total_entities": result.total_entities,
                                "total_relationships": result.total_relationships,
                            },
                        )
                    )
                return ToolExecutionResult(text=result.to_text(), sources=sources)
            
            elif tool_name == "panorama_search":
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ['true', '1', 'yes']
                result = self.zep_tools.panorama_search(
                    graph_id=self.graph_id,
                    query=query,
                    include_expired=include_expired
                )
                fact_entries: List[SourceEntry] = []
                for index, fact in enumerate((result.active_facts or [])[:6], start=1):
                    fact_entries.append(
                        self._make_source_entry(
                            provider="zep_graph",
                            source_type="graph_active_fact",
                            query=query,
                            title=f"Active graph fact {index}",
                            snippet=fact,
                            extra={"tool": tool_name, "include_expired": include_expired},
                        )
                    )
                for index, fact in enumerate((result.historical_facts or [])[:4], start=1):
                    fact_entries.append(
                        self._make_source_entry(
                            provider="zep_graph",
                            source_type="graph_historical_fact",
                            query=query,
                            title=f"Historical graph fact {index}",
                            snippet=fact,
                            extra={"tool": tool_name, "include_expired": include_expired},
                        )
                    )
                if not fact_entries:
                    fact_entries.append(
                        self._make_source_entry(
                            provider="zep_graph",
                            source_type="graph_summary",
                            query=query,
                            title="Panorama summary",
                            snippet=self._preview(result.to_text(), 500),
                            extra={
                                "tool": tool_name,
                                "total_nodes": result.total_nodes,
                                "total_edges": result.total_edges,
                                "active_count": result.active_count,
                                "historical_count": result.historical_count,
                            },
                        )
                    )
                return ToolExecutionResult(text=result.to_text(), sources=fact_entries)
            
            elif tool_name == "quick_search":
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.zep_tools.quick_search(
                    graph_id=self.graph_id,
                    query=query,
                    limit=limit
                )
                sources = [
                    self._make_source_entry(
                        provider="zep_graph",
                        source_type="graph_fact",
                        query=query,
                        title=f"Quick search fact {index}",
                        snippet=fact,
                        extra={"tool": tool_name, "limit": limit},
                    )
                    for index, fact in enumerate((result.facts or [])[:8], start=1)
                ]
                if not sources:
                    sources.append(
                        self._make_source_entry(
                            provider="zep_graph",
                            source_type="graph_summary",
                            query=query,
                            title="Quick search summary",
                            snippet=self._preview(result.to_text(), 500),
                            extra={"tool": tool_name, "total_count": result.total_count},
                        )
                    )
                return ToolExecutionResult(text=result.to_text(), sources=sources)
            
            elif tool_name == "interview_agents":
                interview_topic = parameters.get("interview_topic", parameters.get("query", ""))
                max_agents = parameters.get("max_agents", 5)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 10)
                result = self.zep_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents
                )
                sources = [
                    self._make_source_entry(
                        provider="simulation_agents",
                        source_type="agent_interview",
                        query=interview_topic,
                        title=interview.agent_name,
                        snippet=self._preview(interview.response or (interview.key_quotes[0] if interview.key_quotes else ""), 400),
                        extra={
                            "tool": tool_name,
                            "agent_role": interview.agent_role,
                            "question": interview.question,
                            "key_quotes": interview.key_quotes[:3],
                        },
                    )
                    for interview in (result.interviews or [])[:6]
                ]
                if not sources:
                    sources.append(
                        self._make_source_entry(
                            provider="simulation_agents",
                            source_type="agent_interview_summary",
                            query=interview_topic,
                            title="Interview summary",
                            snippet=self._preview(result.summary or result.selection_reasoning, 400),
                            extra={"tool": tool_name, "interviewed_count": result.interviewed_count},
                        )
                    )
                return ToolExecutionResult(text=result.to_text(), sources=sources)

            elif tool_name == "live_news_brief":
                query = parameters.get("query", "") or report_context or self.simulation_requirement
                max_items = parameters.get("max_items", Config.LIVE_NEWS_MAX_ITEMS)
                if isinstance(max_items, str):
                    max_items = int(max_items)
                result = self.live_evidence.live_news_brief(
                    query=query,
                    max_items=max_items,
                )
                sources = [
                    self._make_source_entry(
                        provider=result.provider,
                        source_type="live_news",
                        query=query,
                        title=item.title,
                        url=item.link,
                        snippet=item.title,
                        published_at=item.published_at,
                        extra={"tool": tool_name, "source": item.source},
                    )
                    for item in (result.items or [])
                ]
                return ToolExecutionResult(
                    text=result.to_text(),
                    sources=sources,
                    warnings=list(result.warnings or []),
                )

            elif tool_name == "live_market_snapshot":
                query = parameters.get("query", "") or report_context or self.simulation_requirement
                context = parameters.get("context", "") or report_context
                max_symbols = parameters.get("max_symbols", 5)
                if isinstance(max_symbols, str):
                    max_symbols = int(max_symbols)
                result = self.live_evidence.live_market_snapshot(
                    query=query,
                    context=context,
                    max_symbols=max_symbols,
                )
                sources = [
                    self._make_source_entry(
                        provider="twelve_data",
                        source_type="market_quote",
                        query=query,
                        title=f"{quote.get('name', quote.get('symbol', 'Unknown'))} ({quote.get('symbol', 'N/A')})",
                        snippet=self._preview(
                            f"Price {quote.get('price', 'N/A')} {quote.get('currency', 'USD')} on {quote.get('exchange', 'N/A')}; "
                            f"change {quote.get('change', 'N/A')} / {quote.get('percent_change', 'N/A')}%",
                            300,
                        ),
                        last_updated=result.fetched_at,
                        extra={"tool": tool_name, **quote},
                    )
                    for quote in (result.quotes or [])
                ]
                return ToolExecutionResult(
                    text=result.to_text(),
                    sources=sources,
                    warnings=list(result.warnings or []),
                )

            elif tool_name == "web_search":
                query = parameters.get("query", "") or report_context or self.simulation_requirement
                max_results = parameters.get("max_results", 5)
                if isinstance(max_results, str):
                    max_results = int(max_results)
                result = self.perplexity.search(query, max_results=max_results)
                sources = [
                    self._make_source_entry(
                        provider=result.provider,
                        source_type="web_search",
                        query=query,
                        title=entry.title or entry.url,
                        url=entry.url,
                        snippet=entry.snippet,
                        published_at=entry.published_at,
                        last_updated=entry.last_updated,
                        extra={"tool": tool_name},
                    )
                    for entry in (result.entries or [])
                ]
                return ToolExecutionResult(
                    text=result.to_text(),
                    sources=sources,
                    warnings=list(result.warnings or []),
                )
            
            # ========== Backward compatible old tools (internally redirected to new tools) ==========
            
            elif tool_name == "search_graph":
                logger.info("search_graph redirected to quick_search")
                return self._execute_tool("quick_search", parameters, report_context)
            
            elif tool_name == "get_graph_statistics":
                result = self.zep_tools.get_graph_statistics(self.graph_id)
                text = json.dumps(result, ensure_ascii=False, indent=2)
                return ToolExecutionResult(
                    text=text,
                    sources=[
                        self._make_source_entry(
                            provider="zep_graph",
                            source_type="graph_statistics",
                            title="Graph statistics",
                            snippet=self._preview(text, 500),
                            extra={"tool": tool_name, **(result or {})},
                        )
                    ],
                )
            
            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.zep_tools.get_entity_summary(
                    graph_id=self.graph_id,
                    entity_name=entity_name
                )
                text = json.dumps(result, ensure_ascii=False, indent=2)
                return ToolExecutionResult(
                    text=text,
                    sources=[
                        self._make_source_entry(
                            provider="zep_graph",
                            source_type="entity_summary",
                            query=entity_name,
                            title=entity_name or "Entity summary",
                            snippet=self._preview(text, 500),
                            extra={"tool": tool_name},
                        )
                    ],
                )
            
            elif tool_name == "get_simulation_context":
                if self.analysis_mode != ANALYSIS_MODE_GLOBAL:
                    message = "get_simulation_context is unavailable in quick mode."
                    return ToolExecutionResult(text=message, warnings=[message])
                logger.info("get_simulation_context redirected to insight_forge")
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool("insight_forge", {"query": query}, report_context)
            
            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.zep_tools.get_entities_by_type(
                    graph_id=self.graph_id,
                    entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                text = json.dumps(result, ensure_ascii=False, indent=2)
                return ToolExecutionResult(
                    text=text,
                    sources=[
                        self._make_source_entry(
                            provider="zep_graph",
                            source_type="entity_type_list",
                            query=entity_type,
                            title=f"Entities of type {entity_type or 'unknown'}",
                            snippet=self._preview(text, 500),
                            extra={"tool": tool_name, "count": len(result)},
                        )
                    ],
                )
            
            else:
                message = (
                    f"Unknown tool: {tool_name}. Please use one of: "
                    + ", ".join(sorted(self.tools.keys()))
                )
                return ToolExecutionResult(text=message, warnings=[message])
                
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, error: {str(e)}")
            return ToolExecutionResult(
                text=f"Tool execution failed: {str(e)}",
                warnings=[f"{tool_name} failed: {str(e)}"],
            )
    
    # Valid tool names set, used for bare JSON fallback parsing validation
    VALID_TOOL_NAMES = {
        "insight_forge",
        "panorama_search",
        "quick_search",
        "interview_agents",
        "live_news_brief",
        "live_market_snapshot",
        "web_search",
        "search_graph",
        "get_graph_statistics",
        "get_entity_summary",
        "get_simulation_context",
        "get_entities_by_type",
    }

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from LLM response

        Supported formats (by priority):
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. Bare JSON (response body or single line is a tool call JSON)
        """
        tool_calls = []

        # Format 1: XML style (standard format)
        xml_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        # Format 2: Fallback - LLM directly outputs bare JSON (no <tool_call> tags)
        # Only try when format 1 did not match, to avoid false matching JSON in body text
        stripped = response.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        # Response may contain thinking text + bare JSON, try to extract last JSON object
        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """Validate whether parsed JSON is a valid tool call"""
        # Support both {"name": ..., "parameters": ...} and {"tool": ..., "params": ...} key formats
        tool_name = data.get("name") or data.get("tool")
        legacy_aliases = self._allowed_legacy_aliases()
        if tool_name and (tool_name in self.tools or tool_name in legacy_aliases):
            # Normalize keys to name / parameters
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False
    
    def _get_tools_description(self) -> str:
        """Generate tool description text"""
        desc_parts = ["Available tools:"]
        for name, tool in self.tools.items():
            params_desc = ", ".join([f"{k}: {v}" for k, v in tool["parameters"].items()])
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  Parameters: {params_desc}")
        return "\n".join(desc_parts)

    def _generate_prediction_summary(self, report_content: str) -> Optional[Dict[str, Any]]:
        """Generate a structured scenario/probability summary from the report."""
        trimmed_report = (report_content or "").strip()
        if not trimmed_report:
            return None

        trimmed_report = trimmed_report[:18000]
        messages = [
            {
                "role": "system",
                "content": (
                    self._build_persona_prefix()
                    + PROBABILITY_SUMMARY_SYSTEM_PROMPT
                    + self._build_variables_context()
                    + self.language_instruction
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Simulation requirement:\n{self.simulation_requirement}\n\n"
                    f"Report content:\n{trimmed_report}"
                ),
            },
        ]

        try:
            response, usage = self.llm.chat_json_with_fallback(
                messages=messages,
                temperature=0.2,
                max_tokens=1600,
            )
            self.usage.add(usage)
            normalized = self._normalize_prediction_summary(response)
            if normalized is not None:
                normalized["language_used"] = self.language
            return normalized
        except Exception as exc:
            logger.warning("Structured prediction summary generation failed: %s", exc)
            return None

    @staticmethod
    def _normalize_prediction_summary(summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Coerce LLM output into a stable scenario summary contract."""
        scenarios = summary.get("scenarios")
        if not isinstance(scenarios, list) or not scenarios:
            return None

        name_map = {
            "bull case": "Bull case",
            "base case": "Base case",
            "bear case": "Bear case",
        }
        normalized_by_name: Dict[str, Dict[str, Any]] = {}
        ordered_labels = ["Bull case", "Base case", "Bear case"]
        for index, item in enumerate(scenarios):
            if not isinstance(item, dict):
                continue
            raw_name = str(item.get("name", "")).strip().lower()
            canonical_name = name_map.get(raw_name)
            if not canonical_name:
                if "bull" in raw_name:
                    canonical_name = "Bull case"
                elif "bear" in raw_name:
                    canonical_name = "Bear case"
                else:
                    canonical_name = ordered_labels[min(index, len(ordered_labels) - 1)]

            try:
                probability = int(round(float(item.get("probability", 0))))
            except Exception:
                probability = 0

            normalized_by_name[canonical_name] = {
                "name": canonical_name,
                "probability": max(0, min(100, probability)),
                "timeframe": str(item.get("timeframe") or summary.get("forecast_horizon") or "").strip(),
                "summary": str(item.get("summary") or "").strip(),
                "key_drivers": ReportAgent._normalize_string_list(item.get("key_drivers")),
                "key_risks": ReportAgent._normalize_string_list(item.get("key_risks")),
                "assumptions": ReportAgent._normalize_string_list(item.get("assumptions")),
            }

        ordered = []
        for label in ordered_labels:
            if label in normalized_by_name:
                ordered.append(normalized_by_name[label])
            else:
                ordered.append({
                    "name": label,
                    "probability": 0,
                    "timeframe": str(summary.get("forecast_horizon") or "").strip(),
                    "summary": "",
                    "key_drivers": [],
                    "key_risks": [],
                    "assumptions": [],
                })

        probabilities = ReportAgent._normalize_probability_values(
            [item["probability"] for item in ordered]
        )

        for item, probability in zip(ordered, probabilities):
            item["probability"] = max(0, min(100, int(probability)))

        return {
            "forecast_horizon": str(summary.get("forecast_horizon") or ordered[1]["timeframe"] or "").strip(),
            "confidence_note": str(summary.get("confidence_note") or "").strip(),
            "scenarios": ordered,
            "caveats": ReportAgent._normalize_string_list(summary.get("caveats")),
        }

    @staticmethod
    def _normalize_string_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @staticmethod
    def _normalize_probability_values(values: List[int]) -> List[int]:
        """Normalize a list of integer probabilities to a stable sum of 100."""
        normalized_values = [max(0, int(value)) for value in values]
        total = sum(normalized_values)
        if total <= 0:
            return [25, 50, 25]

        exact_values = [(value / total) * 100 for value in normalized_values]
        floored_values = [int(value) for value in exact_values]
        remainder = 100 - sum(floored_values)

        if remainder > 0:
            ranked_indexes = sorted(
                range(len(exact_values)),
                key=lambda index: (exact_values[index] - floored_values[index], -index),
                reverse=True,
            )
            for index in ranked_indexes[:remainder]:
                floored_values[index] += 1
        elif remainder < 0:
            ranked_indexes = sorted(
                range(len(exact_values)),
                key=lambda index: (floored_values[index] - exact_values[index], index),
                reverse=True,
            )
            for index in ranked_indexes[: abs(remainder)]:
                if floored_values[index] > 0:
                    floored_values[index] -= 1

        return floored_values

    def _build_explainability(self, report_content: str, manifest: Optional[SourceManifest]) -> Dict[str, Any]:
        explainability = {
            "why_this_conclusion": "",
            "basis_summary": [],
            "source_attribution": [],
        }
        trimmed_report = (report_content or "").strip()
        if not trimmed_report:
            return explainability

        source_shortlist = []
        source_map: Dict[str, SourceEntry] = {}
        for source in (manifest.sources if manifest else [])[:8]:
            source_map[source.source_id] = source
            source_shortlist.append({
                "source_id": source.source_id,
                "provider": source.provider,
                "title": source.title,
                "url": source.url,
                "snippet": self._preview(source.snippet, 240),
            })

        messages = [
            {
                "role": "system",
                "content": (
                    self._build_persona_prefix()
                    + EXPLAINABILITY_SYSTEM_PROMPT
                    + self._build_variables_context()
                    + self.language_instruction
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Simulation requirement:\n{self.simulation_requirement}\n\n"
                    f"Report content:\n{trimmed_report[:14000]}\n\n"
                    f"Source shortlist:\n{json.dumps(source_shortlist, ensure_ascii=False, indent=2)}"
                ),
            },
        ]

        try:
            response, usage = self.llm.chat_json(
                messages=messages,
                temperature=0.2,
                max_tokens=1200,
            )
            self.usage.add(usage)
            explainability["why_this_conclusion"] = str(response.get("why_this_conclusion") or "").strip()
            explainability["basis_summary"] = self._normalize_string_list(response.get("basis_summary"))[:5]

            source_ids = []
            for source_id in response.get("source_ids") or []:
                normalized = str(source_id or "").strip()
                if normalized and normalized in source_map and normalized not in source_ids:
                    source_ids.append(normalized)
            if not source_ids:
                source_ids = [source.source_id for source in (manifest.sources if manifest else [])[:3]]

            explainability["source_attribution"] = [
                {
                    "source_id": source_map[source_id].source_id,
                    "provider": source_map[source_id].provider,
                    "title": source_map[source_id].title,
                    "url": source_map[source_id].url,
                    "snippet": self._preview(source_map[source_id].snippet, 240),
                }
                for source_id in source_ids
                if source_id in source_map
            ]
        except Exception as exc:
            logger.warning("Explainability generation failed for simulation_id=%s: %s", self.simulation_id, exc)
            if manifest:
                manifest.add_warning(f"Explainability generation failed: {exc}")
        return explainability
    
    def plan_outline(
        self, 
        progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        Plan report outline
        
        Use LLM to analyze simulation requirements and plan report outline structure
        
        Args:
            progress_callback: Progress callback function
            
        Returns:
            ReportOutline: Report outline
        """
        logger.info("Starting report outline planning...")
        
        if progress_callback:
            progress_callback("planning", 0, "Analyzing simulation requirements...")
        
        # First get simulation context
        context = self.zep_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement
        )
        
        if progress_callback:
            progress_callback("planning", 30, "Generating report outline...")

        min_sections, max_sections = self._outline_section_bounds()
        mode_prompt = (
            "\n[Analysis Mode]\n"
            f"- Current analysis mode: {self.analysis_mode}\n"
            f"- Section count must stay between {min_sections} and {max_sections}\n"
            + ("- Favor fast synthesis and keep the outline compact.\n" if self.analysis_mode == ANALYSIS_MODE_QUICK else "- Use the full report structure when it materially improves coverage.\n")
        )
        system_prompt = self._build_persona_prefix() + PLAN_SYSTEM_PROMPT + mode_prompt + self._build_variables_context() + self.language_instruction
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
            total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
            entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
            total_entities=context.get('total_entities', 0),
            related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
        ) + (
            f"\n\n[Mode-specific constraint]\nKeep the outline between {min_sections} and {max_sections} sections."
        )

        try:
            response, _usage = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            self.usage.add(_usage)

            if progress_callback:
                progress_callback("planning", 80, "Parsing outline structure...")
            
            # Parse outline
            sections = []
            for section_data in response.get("sections", [])[:max_sections]:
                sections.append(ReportSection(
                    title=section_data.get("title", ""),
                    content=""
                ))
            if len(sections) < min_sections:
                fallback_sections = [
                    "Prediction Scenarios and Core Findings",
                    "Population Behavior Prediction Analysis",
                    "Trend Outlook and Risk Indicators",
                ]
                sections = [ReportSection(title=title, content="") for title in fallback_sections[:max_sections]]
            
            outline = ReportOutline(
                title=response.get("title", "Simulation Analysis Report"),
                summary=response.get("summary", ""),
                sections=sections
            )
            
            if progress_callback:
                progress_callback("planning", 100, "Outline planning complete")
            
            logger.info(f"Outline planning complete: {len(sections)} sections")
            return outline
            
        except Exception as e:
            logger.error(f"Outline planning failed: {str(e)}")
            # Return default outline (3 sections, as fallback)
            return ReportOutline(
                title="Future Prediction Report",
                summary="Future trend and risk analysis based on simulation predictions",
                sections=[
                    ReportSection(title="Prediction Scenarios and Core Findings"),
                    ReportSection(title="Population Behavior Prediction Analysis"),
                    ReportSection(title="Trend Outlook and Risk Indicators")
                ]
            )
    
    def _generate_section_react(
        self, 
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0
    ) -> str:
        """
        Generate single section content using ReACT pattern
        
        ReACT loop:
        1. Thought - Analyze what information is needed
        2. Action - Call tools to get information
        3. Observation - Analyze tool return results
        4. Repeat until information is sufficient or max iterations reached
        5. Final Answer - Generate section content
        
        Args:
            section: Section to generate
            outline: Complete outline
            previous_sections: Previous section content (for maintaining coherence)
            progress_callback: Progress callback
            section_index: Section index (for logging)
            
        Returns:
            Section content (Markdown format)
        """
        logger.info(f"ReACT generating section: {section.title}")
        
        # Log section start
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)
        
        formatted_template = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
            min_tool_calls=self.min_tool_calls_per_section,
            max_tool_calls=self.max_tool_calls_per_section,
        )
        system_prompt = self._build_persona_prefix() + formatted_template + self._build_variables_context() + self.language_instruction

        # Build user prompt - each completed section passes in max 4000 chars
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                # Max 4000 chars per section
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "(This is the first section)"
        
        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # ReACT loop
        tool_calls_count = 0
        max_iterations = self.max_reflection_rounds
        min_tool_calls = self.min_tool_calls_per_section
        conflict_retries = 0  # Consecutive conflicts where tool call and Final Answer appear simultaneously
        used_tools = set()  # Track called tool names
        all_tools = set(self.tools.keys())

        # Report context, for InsightForge sub-question generation
        report_context = f"Section title: {section.title}\nSimulation requirement: {self.simulation_requirement}"
        
        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating", 
                    int((iteration / max_iterations) * 100),
                    f"Deep retrieval and writing ({tool_calls_count}/{self.max_tool_calls_per_section})"
                )
            
            # Call LLM
            response, _usage = self.llm.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )
            self.usage.add(_usage)

            # Check if LLM returned None (API exception or empty content)
            if response is None:
                logger.warning(f"Section {section.title} iteration {iteration + 1}: LLM returned None")
                # If there are more iterations, add message and retry
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "(Response was empty)"})
                    messages.append({"role": "user", "content": "Please continue generating content."})
                    continue
                # Last iteration also returned None, break out to forced conclusion
                break

            logger.debug(f"LLM response: {response[:200]}...")

            # Parse once, reuse results
            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # -- Conflict handling: LLM output both tool call and Final Answer --
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    f"Section {section.title} round {iteration+1}: "
                    f"LLM output both tool call and Final Answer (conflict #{conflict_retries})"
                )

                if conflict_retries <= 2:
                    # First two times: discard this response, ask LLM to re-reply
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "[Format Error] You included both a tool call and Final Answer in one response, this is not allowed.\n"
                            "Each response can only do one of the following two things:\n"
                            "- Call a tool (output a <tool_call> block, do not write Final Answer)\n"
                            "- Output final content (starting with 'Final Answer:', do not include <tool_call>)\n"
                            "Please re-reply, doing only one of these."
                        ),
                    })
                    continue
                else:
                    # Third time: degrade, truncate to first tool call, force execute
                    logger.warning(
                        f"Section {section.title}: {conflict_retries} consecutive conflicts, "
                        "degrading to truncated execution of first tool call"
                    )
                    first_tool_end = response.find('</tool_call>')
                    if first_tool_end != -1:
                        response = response[:first_tool_end + len('</tool_call>')]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # Log LLM response
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer
                )

            # -- Case 1: LLM output Final Answer --
            if has_final_answer:
                # Tool call count insufficient, reject and request more tool calls
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = f"(These tools have not been used yet, try them: {', '.join(unused_tools)})" if unused_tools else ""
                    messages.append({
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                # Normal end
                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(f"Section {section.title} generation complete (tool calls: {tool_calls_count})")

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count
                    )
                return final_answer

            # -- Case 2: LLM attempted tool call --
            if has_tool_calls:
                # Tool quota exhausted -> explicitly notify, request Final Answer output
                if tool_calls_count >= self.max_tool_calls_per_section:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.max_tool_calls_per_section,
                        ),
                    })
                    continue

                # Only execute first tool call
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(f"LLM attempted {len(tool_calls)} tool calls, only executing first: {call['name']}")

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1
                    )

                tool_result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context
                )
                self._record_tool_result(tool_result)

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=tool_result.text,
                        iteration=iteration + 1
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])

                # Build unused tools hint
                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.max_tool_calls_per_section:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list=", ".join(unused_tools))

                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=tool_result.text,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.max_tool_calls_per_section,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # -- Case 3: Neither tool call nor Final Answer --
            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                # Tool call count insufficient, recommend unused tools
                unused_tools = all_tools - used_tools
                unused_hint = f"(These tools have not been used yet, try them: {', '.join(unused_tools)})" if unused_tools else ""

                messages.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # Tool calls sufficient, LLM output content without "Final Answer:" prefix
            # Use this content directly as the final answer, no more idle loops
            logger.info(f"Section {section.title} no 'Final Answer:' prefix detected, directly adopting LLM output as final content (tool calls: {tool_calls_count})")
            final_answer = response.strip()

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count
                )
            return final_answer
        
        # Max iterations reached, force generate content
        logger.warning(f"Section {section.title} reached max iterations, force generating")
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})
        
        response, _usage = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096
        )
        self.usage.add(_usage)

        # Check if LLM returned None during forced conclusion
        if response is None:
            logger.error(f"Section {section.title} LLM returned None during forced conclusion, using default error message")
            final_answer = f"(This section generation failed: LLM returned empty response, please try again later)"
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response
        
        # Log section content generation complete
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count
            )
        
        return final_answer
    
    def generate_report(
        self, 
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None
    ) -> Report:
        """
        Generate complete report (with per-section real-time output)
        
        Each section is saved to folder immediately after completion, no need to wait for entire report.
        File structure:
        reports/{report_id}/
            meta.json       - Report metadata
            outline.json    - Report outline
            progress.json   - Generation progress
            section_01.md   - Section 1
            section_02.md   - Section 2
            ...
            full_report.md  - Complete report
        
        Args:
            progress_callback: Progress callback function (stage, progress, message)
            report_id: Report ID (optional, auto-generated if not provided)
            
        Returns:
            Report: Complete report
        """
        import uuid
        
        # If no report_id provided, auto-generate one
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()
        
        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat(),
            language_used=self.language,
            analysis_mode=self.analysis_mode,
            source_manifest_summary={},
            explainability={},
        )
        
        # Completed section title list (for progress tracking)
        completed_section_titles = []
        
        try:
            # Initialization: Create report folder and save initial state
            ReportManager._ensure_report_folder(report_id)
            self.source_manifest = SourceManifest(
                report_id=report_id,
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                analysis_mode=self.analysis_mode,
                language=self.language,
            )
            
            # Initialize logger (structured log agent_log.jsonl)
            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement,
                analysis_mode=self.analysis_mode,
            )
            
            # Initialize console logger (console_log.txt)
            self.console_logger = ReportConsoleLogger(report_id)
            
            ReportManager.update_progress(
                report_id, "pending", 0, "Initializing report...",
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            # Phase 1: Plan outline
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, "Starting report outline planning...",
                completed_sections=[]
            )
            
            # Log planning start
            self.report_logger.log_planning_start()
            
            if progress_callback:
                progress_callback("planning", 0, "Starting report outline planning...")
            
            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg: 
                    progress_callback(stage, prog // 5, msg) if progress_callback else None
            )
            report.outline = outline
            
            # Log planning complete
            self.report_logger.log_planning_complete(outline.to_dict())
            
            # Save outline to file
            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id, "planning", 15, f"Outline planning complete, {len(outline.sections)} sections total",
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            logger.info(f"Outline saved to file: {report_id}/outline.json")
            
            # Phase 2: Generate section by section (save per section)
            report.status = ReportStatus.GENERATING
            ReportManager.save_report(report)
            
            total_sections = len(outline.sections)
            generated_sections = []  # Save content for context
            
            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)
                
                # Update progress
                ReportManager.update_progress(
                    report_id, "generating", base_progress,
                    f"Generating section: {section.title} ({section_num}/{total_sections})",
                    current_section=section.title,
                    completed_sections=completed_section_titles
                )
                
                if progress_callback:
                    progress_callback(
                        "generating", 
                        base_progress, 
                        f"Generating section: {section.title} ({section_num}/{total_sections})"
                    )
                
                # Generate main section content
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg:
                        progress_callback(
                            stage, 
                            base_progress + int(prog * 0.7 / total_sections),
                            msg
                        ) if progress_callback else None,
                    section_index=section_num
                )
                
                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                # Save section
                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                # Log section complete
                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip()
                    )

                logger.info(f"Section saved: {report_id}/section_{section_num:02d}.md")
                
                # Update progress
                ReportManager.update_progress(
                    report_id, "generating", 
                    base_progress + int(70 / total_sections),
                    f"Section {section.title} completed",
                    current_section=None,
                    completed_sections=completed_section_titles
                )
            
            # Phase 3: Assemble complete report
            if progress_callback:
                progress_callback("generating", 95, "Assembling complete report...")
            
            ReportManager.update_progress(
                report_id, "generating", 95, "Assembling complete report...",
                completed_sections=completed_section_titles
            )
            
            # Use ReportManager to assemble complete report
            report.markdown_content = ReportManager.assemble_full_report(
                report_id,
                outline,
                language_used=report.language_used,
            )
            ReportManager.update_progress(
                report_id, "generating", 97, "Generating structured scenario outlook...",
                completed_sections=completed_section_titles
            )
            if progress_callback:
                progress_callback("generating", 97, "Generating structured scenario outlook...")

            prediction_summary = self._generate_prediction_summary(report.markdown_content)
            if prediction_summary:
                report.prediction_summary = prediction_summary
                report.markdown_content = ReportManager.assemble_full_report(
                    report_id,
                    outline,
                    prediction_summary=prediction_summary,
                    language_used=report.language_used,
                )

            report.explainability = self._build_explainability(report.markdown_content, self.source_manifest)
            if self.source_manifest:
                try:
                    ReportManager.save_source_manifest(report.report_id, self.source_manifest)
                    report.source_manifest_summary = self.source_manifest.summary()
                except Exception as exc:
                    logger.warning("Failed to persist source manifest for report_id=%s: %s", report.report_id, exc)
                    report.source_manifest_summary = {
                        "artifact": "",
                        "source_count": 0,
                        "provider_counts": {},
                        "warnings": [f"Source manifest persistence failed: {exc}"],
                    }

            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()
            
            # Calculate total elapsed time
            total_time_seconds = (datetime.now() - start_time).total_seconds()
            
            # Log report complete
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections,
                    total_time_seconds=total_time_seconds
                )
            
            # Save final report
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id, "completed", 100, "Report generation complete",
                completed_sections=completed_section_titles
            )
            
            if progress_callback:
                progress_callback("completed", 100, "Report generation complete")
            
            logger.info(f"Report generation complete: {report_id}")
            logger.info(f"Total LLM usage: {self.usage.to_dict()}")

            # Store usage metadata on report
            report.usage = self.usage.to_dict()
            ReportManager.save_report(report)

            # Close console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report
            
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            report.status = ReportStatus.FAILED
            report.error = str(e)
            
            # Log error
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")
            
            # Save failed state
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id, "failed", -1, f"Report generation failed: {str(e)}",
                    completed_sections=completed_section_titles
                )
            except Exception:
                pass  # Ignore save failure errors
            
            # Close console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
    
    def chat(
        self, 
        message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Chat with Report Agent
        
        In conversation, Agent can autonomously call retrieval tools to answer questions
        
        Args:
            message: User message
            chat_history: Chat history
            
        Returns:
            {
                "response": "Agent response",
                "tool_calls": [list of called tools],
                "sources": [information sources]
            }
        """
        logger.info(f"Report Agent chat: {message[:50]}...")
        
        chat_history = chat_history or []
        
        # Get generated report content
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(
                self.simulation_id,
                language_used=self.language,
                analysis_mode=self.analysis_mode,
            )
            if report and report.markdown_content:
                # Limit report length to avoid context overflow
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [Report content truncated] ..."
        except Exception as e:
            logger.warning(f"Failed to get report content: {e}")
        
        formatted_template = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "(No report available yet)",
            tools_description=self._get_tools_description(),
        )
        system_prompt = self._build_persona_prefix() + formatted_template + self._build_variables_context() + self.language_instruction

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add chat history
        for h in chat_history[-10:]:  # Limit history length
            messages.append(h)
        
        # Add user message
        messages.append({
            "role": "user", 
            "content": message
        })
        
        # ReACT loop (simplified version)
        tool_calls_made = []
        max_iterations = 2  # Reduced iteration rounds
        
        for iteration in range(max_iterations):
            response, _usage = self.llm.chat(
                messages=messages,
                temperature=0.5
            )
            self.usage.add(_usage)

            # Parse tool call
            tool_calls = self._parse_tool_calls(response)
            
            if not tool_calls:
                # No tool call, return response directly
                clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', response, flags=re.DOTALL)
                clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
                
                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
                }
            
            # Execute tool calls (limited count)
            tool_results = []
            for call in tool_calls[:1]:  # Max 1 tool call per round
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append({
                    "tool": call["name"],
                    "result": result.text[:1500]  # Limit result length
                })
                tool_calls_made.append(call)
            
            # Add results to messages
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join([f"[{r['tool']} result]\n{r['result']}" for r in tool_results])
            messages.append({
                "role": "user",
                "content": observation + CHAT_OBSERVATION_SUFFIX
            })
        
        # Max iterations reached, get final response
        final_response, _usage = self.llm.chat(
            messages=messages,
            temperature=0.5
        )
        self.usage.add(_usage)

        # Clean response
        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', final_response, flags=re.DOTALL)
        clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
        
        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
        }


class ReportManager:
    """
    Report manager
    
    Responsible for report persistent storage and retrieval
    
    File structure (per-section output):
    reports/
      {report_id}/
        meta.json          - Report metadata and status
        outline.json       - Report outline
        progress.json      - Generation progress
        section_01.md      - Section 1
        section_02.md      - Section 2
        ...
        full_report.md     - Complete report
    """
    
    # Report storage directory
    REPORTS_DIR = Config.REPORTS_DIR

    @classmethod
    def _store(cls):
        return get_artifact_store()
    
    @classmethod
    def _ensure_reports_dir(cls):
        """Ensure report root directory exists"""
        cls._store().ensure_namespace(REPORT_NAMESPACE)
    
    @classmethod
    def _get_report_folder(cls, report_id: str, *, ensure: bool = False, sync: bool = False) -> str:
        """Get report folder path"""
        return cls._store().get_resource_dir(REPORT_NAMESPACE, report_id, ensure=ensure, sync=sync)
    
    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """Ensure report folder exists and return path"""
        return cls._get_report_folder(report_id, ensure=True)

    @classmethod
    def flush_report(cls, report_id: str) -> str:
        return cls._store().flush_resource(REPORT_NAMESPACE, report_id)
    
    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """Get report metadata file path"""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")
    
    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """Get complete report Markdown file path"""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")
    
    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """Get outline file path"""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")
    
    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """Get progress file path"""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")

    @classmethod
    def _get_prediction_summary_path(cls, report_id: str) -> str:
        """Get structured prediction summary path."""
        return os.path.join(cls._get_report_folder(report_id), "prediction_summary.json")

    @classmethod
    def _get_source_manifest_path(cls, report_id: str) -> str:
        return os.path.join(cls._get_report_folder(report_id), SourceManifest.ARTIFACT_NAME)
    
    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """Get section Markdown file path"""
        return os.path.join(cls._get_report_folder(report_id), f"section_{section_index:02d}.md")
    
    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """Get Agent log file path"""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")
    
    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """Get console log file path"""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")
    
    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Get console log content
        
        These are console output logs during report generation (INFO, WARNING, etc.),
        different from the structured logs in agent_log.jsonl.
        
        Args:
            report_id: Report ID
            from_line: Start reading from which line (for incremental retrieval, 0 means from beginning)
            
        Returns:
            {
                "logs": [log line list],
                "total_lines": total line count,
                "from_line": start line number,
                "has_more": whether there are more logs
            }
        """
        cls._get_report_folder(report_id, sync=True)
        log_path = cls._get_console_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    # Keep original log line, strip trailing newline
                    logs.append(line.rstrip('\n\r'))
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Read to end
        }
    
    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
        Get complete console log (all at once)
        
        Args:
            report_id: Report ID
            
        Returns:
            Log line list
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Get Agent log content
        
        Args:
            report_id: Report ID
            from_line: Start reading from which line (for incremental retrieval, 0 means from beginning)
            
        Returns:
            {
                "logs": [log entry list],
                "total_lines": total line count,
                "from_line": start line number,
                "has_more": whether there are more logs
            }
        """
        cls._get_report_folder(report_id, sync=True)
        log_path = cls._get_agent_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # Skip lines that fail to parse
                        continue
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Read to end
        }
    
    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Get complete Agent log (for getting all at once)
        
        Args:
            report_id: Report ID
            
        Returns:
            Log entry list
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        Save report outline
        
        Called immediately after planning phase completes
        """
        cls._ensure_report_folder(report_id)
        
        with open(cls._get_outline_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)
        cls.flush_report(report_id)
        
        logger.info(f"Outline saved: {report_id}")
    
    @classmethod
    def save_section(
        cls,
        report_id: str,
        section_index: int,
        section: ReportSection
    ) -> str:
        """
        Save a single section

        Called immediately after each section generation completes, enabling per-section output

        Args:
            report_id: Report ID
            section_index: Section index (starting from 1)
            section: Section object

        Returns:
            Saved file path
        """
        cls._ensure_report_folder(report_id)

        # Build section Markdown content - clean possible duplicate headings
        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        # Save file
        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        cls.flush_report(report_id)

        logger.info(f"Section saved: {report_id}/{file_suffix}")
        return file_path
    
    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        Clean section content
        
        1. Remove Markdown heading lines at content start that duplicate section title
        2. Convert all ### and below level headings to bold text
        
        Args:
            content: Original content
            section_title: Section title
            
        Returns:
            Cleaned content
        """
        import re
        
        if not content:
            return content
        
        content = content.strip()
        lines = content.split('\n')
        cleaned_lines = []
        skip_next_empty = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Check if this is a Markdown heading line
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()
                
                # Check if heading duplicates section title (skip duplicates within first 5 lines)
                if i < 5:
                    if title_text == section_title or title_text.replace(' ', '') == section_title.replace(' ', ''):
                        skip_next_empty = True
                        continue
                
                # Convert all heading levels (#, ##, ###, #### etc.) to bold
                # Because section title is added by system, content should not have any headings
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("")  # Add blank line
                continue
            
            # If previous line was a skipped heading and current line is empty, also skip
            if skip_next_empty and stripped == '':
                skip_next_empty = False
                continue
            
            skip_next_empty = False
            cleaned_lines.append(line)
        
        # Remove leading blank lines
        while cleaned_lines and cleaned_lines[0].strip() == '':
            cleaned_lines.pop(0)
        
        # Remove leading dividers
        while cleaned_lines and cleaned_lines[0].strip() in ['---', '***', '___']:
            cleaned_lines.pop(0)
            # Also remove blank lines after dividers
            while cleaned_lines and cleaned_lines[0].strip() == '':
                cleaned_lines.pop(0)
        
        return '\n'.join(cleaned_lines)
    
    @classmethod
    def update_progress(
        cls, 
        report_id: str, 
        status: str, 
        progress: int, 
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None
    ) -> None:
        """
        Update report generation progress
        
        Frontend can read progress.json for real-time progress
        """
        cls._ensure_report_folder(report_id)
        
        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": datetime.now().isoformat()
        }
        
        with open(cls._get_progress_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
        cls.flush_report(report_id)
    
    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report generation progress"""
        cls._get_report_folder(report_id, sync=True)
        path = cls._get_progress_path(report_id)
        
        if not os.path.exists(path):
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Get list of generated sections
        
        Return all saved section file info
        """
        folder = cls._get_report_folder(report_id, ensure=True, sync=True)
        
        if not os.path.exists(folder):
            return []
        
        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith('section_') and filename.endswith('.md'):
                file_path = os.path.join(folder, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse section index from filename
                parts = filename.replace('.md', '').split('_')
                section_index = int(parts[1])

                sections.append({
                    "filename": filename,
                    "section_index": section_index,
                    "content": content
                })

        return sections

    @classmethod
    def save_prediction_summary(cls, report_id: str, prediction_summary: Dict[str, Any]) -> None:
        """Persist structured prediction summary to a standalone JSON artifact."""
        cls._ensure_report_folder(report_id)
        with open(cls._get_prediction_summary_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(prediction_summary, f, ensure_ascii=False, indent=2)
        cls.flush_report(report_id)

    @classmethod
    def save_source_manifest(cls, report_id: str, manifest: SourceManifest) -> None:
        cls._ensure_report_folder(report_id)
        with open(cls._get_source_manifest_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(manifest.to_dict(), f, ensure_ascii=False, indent=2)
        cls.flush_report(report_id)

    @classmethod
    def get_source_manifest(cls, report_id: str) -> Optional[SourceManifest]:
        cls._get_report_folder(report_id, sync=True)
        path = cls._get_source_manifest_path(report_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return SourceManifest.from_dict(json.load(f))
        except Exception as exc:
            logger.warning("Failed to read source manifest for report_id=%s: %s", report_id, exc)
            return None

    @classmethod
    def _prediction_summary_terms(cls, language_used: str) -> Dict[str, str]:
        translations = {
            "en": {
                "scenario_outlook": "Scenario Outlook",
                "forecast_horizon": "Forecast horizon",
                "timeframe": "Timeframe",
                "summary": "Summary",
                "drivers": "Drivers",
                "risks": "Risks",
                "assumptions": "Assumptions",
                "confidence_note": "Confidence note",
                "caveats": "Caveats",
                "bull_case": "Bull case",
                "base_case": "Base case",
                "bear_case": "Bear case",
            },
            "ru": {
                "scenario_outlook": "Сценарный прогноз",
                "forecast_horizon": "Горизонт прогноза",
                "timeframe": "Период",
                "summary": "Краткий вывод",
                "drivers": "Драйверы",
                "risks": "Риски",
                "assumptions": "Допущения",
                "confidence_note": "Комментарий по уверенности",
                "caveats": "Ограничения",
                "bull_case": "Бычий сценарий",
                "base_case": "Базовый сценарий",
                "bear_case": "Медвежий сценарий",
            },
            "he": {
                "scenario_outlook": "תחזית תרחישים",
                "forecast_horizon": "אופק התחזית",
                "timeframe": "טווח זמן",
                "summary": "סיכום",
                "drivers": "מניעים",
                "risks": "סיכונים",
                "assumptions": "הנחות",
                "confidence_note": "הערת ביטחון",
                "caveats": "הסתייגויות",
                "bull_case": "תרחיש שורי",
                "base_case": "תרחיש בסיס",
                "bear_case": "תרחיש דובי",
            },
            "es": {
                "scenario_outlook": "Panorama de escenarios",
                "forecast_horizon": "Horizonte de pronóstico",
                "timeframe": "Plazo",
                "summary": "Resumen",
                "drivers": "Impulsores",
                "risks": "Riesgos",
                "assumptions": "Supuestos",
                "confidence_note": "Nota de confianza",
                "caveats": "Limitaciones",
                "bull_case": "Escenario alcista",
                "base_case": "Escenario base",
                "bear_case": "Escenario bajista",
            },
            "de": {
                "scenario_outlook": "Szenarioausblick",
                "forecast_horizon": "Prognosehorizont",
                "timeframe": "Zeitraum",
                "summary": "Zusammenfassung",
                "drivers": "Treiber",
                "risks": "Risiken",
                "assumptions": "Annahmen",
                "confidence_note": "Hinweis zur Sicherheit",
                "caveats": "Einschränkungen",
                "bull_case": "Bullishes Szenario",
                "base_case": "Basisszenario",
                "bear_case": "Bärisches Szenario",
            },
            "fr": {
                "scenario_outlook": "Perspective des scénarios",
                "forecast_horizon": "Horizon de prévision",
                "timeframe": "Horizon temporel",
                "summary": "Résumé",
                "drivers": "Facteurs moteurs",
                "risks": "Risques",
                "assumptions": "Hypothèses",
                "confidence_note": "Note de confiance",
                "caveats": "Limites",
                "bull_case": "Scénario haussier",
                "base_case": "Scénario central",
                "bear_case": "Scénario baissier",
            },
            "it": {
                "scenario_outlook": "Quadro degli scenari",
                "forecast_horizon": "Orizzonte di previsione",
                "timeframe": "Orizzonte temporale",
                "summary": "Sintesi",
                "drivers": "Driver",
                "risks": "Rischi",
                "assumptions": "Assunzioni",
                "confidence_note": "Nota di confidenza",
                "caveats": "Limiti",
                "bull_case": "Scenario rialzista",
                "base_case": "Scenario base",
                "bear_case": "Scenario ribassista",
            },
            "pt": {
                "scenario_outlook": "Panorama de cenários",
                "forecast_horizon": "Horizonte de previsão",
                "timeframe": "Horizonte",
                "summary": "Resumo",
                "drivers": "Vetores",
                "risks": "Riscos",
                "assumptions": "Premissas",
                "confidence_note": "Nota de confiança",
                "caveats": "Limitações",
                "bull_case": "Cenário de alta",
                "base_case": "Cenário base",
                "bear_case": "Cenário de baixa",
            },
            "pl": {
                "scenario_outlook": "Przegląd scenariuszy",
                "forecast_horizon": "Horyzont prognozy",
                "timeframe": "Horyzont czasowy",
                "summary": "Podsumowanie",
                "drivers": "Czynniki napędzające",
                "risks": "Ryzyka",
                "assumptions": "Założenia",
                "confidence_note": "Uwagi o pewności",
                "caveats": "Ograniczenia",
                "bull_case": "Scenariusz wzrostowy",
                "base_case": "Scenariusz bazowy",
                "bear_case": "Scenariusz spadkowy",
            },
            "nl": {
                "scenario_outlook": "Scenario-overzicht",
                "forecast_horizon": "Prognosehorizon",
                "timeframe": "Tijdshorizon",
                "summary": "Samenvatting",
                "drivers": "Drijvers",
                "risks": "Risico's",
                "assumptions": "Aannames",
                "confidence_note": "Betrouwbaarheidsnotitie",
                "caveats": "Beperkingen",
                "bull_case": "Bullish scenario",
                "base_case": "Basisscenario",
                "bear_case": "Bearish scenario",
            },
            "tr": {
                "scenario_outlook": "Senaryo görünümü",
                "forecast_horizon": "Tahmin ufku",
                "timeframe": "Zaman dilimi",
                "summary": "Özet",
                "drivers": "Sürücüler",
                "risks": "Riskler",
                "assumptions": "Varsayımlar",
                "confidence_note": "Güven notu",
                "caveats": "Sınırlamalar",
                "bull_case": "Yükseliş senaryosu",
                "base_case": "Temel senaryo",
                "bear_case": "Düşüş senaryosu",
            },
            "ar": {
                "scenario_outlook": "آفاق السيناريوهات",
                "forecast_horizon": "أفق التوقع",
                "timeframe": "الإطار الزمني",
                "summary": "الملخص",
                "drivers": "العوامل الدافعة",
                "risks": "المخاطر",
                "assumptions": "الافتراضات",
                "confidence_note": "ملاحظة الثقة",
                "caveats": "القيود",
                "bull_case": "السيناريو الصاعد",
                "base_case": "السيناريو الأساسي",
                "bear_case": "السيناريو الهابط",
            },
        }
        return translations.get(language_used or "en", translations["en"])

    @classmethod
    def _localize_scenario_name(cls, name: str, language_used: str) -> str:
        terms = cls._prediction_summary_terms(language_used)
        normalized = (name or "").strip().lower()
        if normalized == "bull case":
            return terms["bull_case"]
        if normalized == "base case":
            return terms["base_case"]
        if normalized == "bear case":
            return terms["bear_case"]
        return name or terms["base_case"]

    @classmethod
    def _format_prediction_summary_markdown(cls, prediction_summary: Dict[str, Any], language_used: str = "en") -> str:
        """Render structured probabilities as a human-readable markdown block."""
        scenarios = prediction_summary.get("scenarios") or []
        if not scenarios:
            return ""
        terms = cls._prediction_summary_terms(language_used)

        lines = [f"## {terms['scenario_outlook']}", ""]
        forecast_horizon = prediction_summary.get("forecast_horizon")
        if forecast_horizon:
            lines.append(f"**{terms['forecast_horizon']}:** {forecast_horizon}")
            lines.append("")

        for scenario in scenarios:
            name = cls._localize_scenario_name(scenario.get("name", "Scenario"), language_used)
            probability = scenario.get("probability", 0)
            timeframe = scenario.get("timeframe", "")
            summary = scenario.get("summary", "")
            lines.append(f"**{name} ({probability}%)**")
            if timeframe:
                lines.append(f"- {terms['timeframe']}: {timeframe}")
            if summary:
                lines.append(f"- {terms['summary']}: {summary}")
            drivers = scenario.get("key_drivers") or []
            if drivers:
                lines.append(f"- {terms['drivers']}:")
                lines.extend(f"  - {driver}" for driver in drivers)
            risks = scenario.get("key_risks") or []
            if risks:
                lines.append(f"- {terms['risks']}:")
                lines.extend(f"  - {risk}" for risk in risks)
            assumptions = scenario.get("assumptions") or []
            if assumptions:
                lines.append(f"- {terms['assumptions']}:")
                lines.extend(f"  - {assumption}" for assumption in assumptions)
            lines.append("")

        confidence_note = prediction_summary.get("confidence_note")
        if confidence_note:
            lines.append(f"**{terms['confidence_note']}:** {confidence_note}")
            lines.append("")

        caveats = prediction_summary.get("caveats") or []
        if caveats:
            lines.append(f"**{terms['caveats']}**")
            lines.extend(f"- {caveat}" for caveat in caveats)
            lines.append("")

        return "\n".join(lines).rstrip() + "\n\n"

    @classmethod
    def assemble_full_report(
        cls,
        report_id: str,
        outline: ReportOutline,
        prediction_summary: Optional[Dict[str, Any]] = None,
        language_used: str = "en",
    ) -> str:
        """
        Assemble complete report
        
        Assemble complete report from saved section files and clean headings
        """
        folder = cls._get_report_folder(report_id, ensure=True, sync=True)
        
        # Build report header
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        if prediction_summary:
            md_content += cls._format_prediction_summary_markdown(prediction_summary, language_used)
        md_content += f"---\n\n"
        
        # Read all section files in order
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]
        
        # Post-process: clean heading issues in entire report
        md_content = cls._post_process_report(md_content, outline, language_used=language_used)
        
        # Save complete report
        full_path = os.path.join(folder, "full_report.md")
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        cls.flush_report(report_id)
        
        logger.info(f"Complete report assembled: {report_id}")
        return md_content
    
    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline, language_used: str = "en") -> str:
        """
        Post-process report content
        
        1. Remove duplicate headings
        2. Keep report main title (#) and section titles (##), remove other heading levels (###, #### etc.)
        3. Clean excess blank lines and dividers
        
        Args:
            content: Original report content
            outline: Report outline
            
        Returns:
            Processed content
        """
        import re
        
        lines = content.split('\n')
        processed_lines = []
        prev_was_heading = False
        
        # Collect all section titles from outline
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)
        allowed_level_two_headings = {cls._prediction_summary_terms(language_used)["scenario_outlook"]}
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Check if this is a heading line
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # Check if heading is duplicate (same content heading within consecutive 5 lines)
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r'^(#{1,6})\s+(.+)$', prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    # Skip duplicate heading and following blank lines
                    i += 1
                    while i < len(lines) and lines[i].strip() == '':
                        i += 1
                    continue
                
                # Heading level handling:
                # - # (level=1) Keep only report main title
                # - ## (level=2) Keep section titles
                # - ### and below (level>=3) convert to bold text
                
                if level == 1:
                    if title == outline.title:
                        # Keep report main title
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        # Section title incorrectly used #, correct to ##
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        # Other level-1 headings to bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title or title in allowed_level_two_headings:
                        # Keep section title
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        # Non-section level-2 headings to bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    # ### and below level headings to bold text
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False
                
                i += 1
                continue
            
            elif stripped == '---' and prev_was_heading:
                # Skip dividers immediately after headings
                i += 1
                continue
            
            elif stripped == '' and prev_was_heading:
                # Keep only one blank line after heading
                if processed_lines and processed_lines[-1].strip() != '':
                    processed_lines.append(line)
                prev_was_heading = False
            
            else:
                processed_lines.append(line)
                prev_was_heading = False
            
            i += 1
        
        # Clean consecutive multiple blank lines (keep max 2)
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    @classmethod
    def save_report(cls, report: Report) -> None:
        """Save report metadata and complete report"""
        cls._ensure_report_folder(report.report_id)
        
        # Save metadata JSON
        with open(cls._get_report_path(report.report_id), 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        # Save outline
        if report.outline:
            cls.save_outline(report.report_id, report.outline)

        if report.prediction_summary:
            cls.save_prediction_summary(report.report_id, report.prediction_summary)
            try:
                PredictionLedgerManager.sync_report_prediction_summary(
                    report_id=report.report_id,
                    simulation_id=report.simulation_id,
                    graph_id=report.graph_id,
                    prediction_summary=report.prediction_summary,
                    created_at=report.created_at,
                    completed_at=report.completed_at,
                )
            except Exception as exc:
                logger.warning(
                    "Prediction ledger sync failed for report_id=%s: %s",
                    report.report_id,
                    exc,
                )
        
        # Save complete Markdown report
        if report.markdown_content:
            with open(cls._get_report_markdown_path(report.report_id), 'w', encoding='utf-8') as f:
                f.write(report.markdown_content)
        cls.flush_report(report.report_id)
        
        logger.info(f"Report saved: {report.report_id}")
    
    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """Get report"""
        cls._get_report_folder(report_id, sync=True)
        path = cls._get_report_path(report_id)
        
        if not os.path.exists(path):
            # Backward compatible: check files stored directly in reports directory
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Rebuild Report object
        outline = None
        if data.get('outline'):
            outline_data = data['outline']
            sections = []
            for s in outline_data.get('sections', []):
                sections.append(ReportSection(
                    title=s['title'],
                    content=s.get('content', '')
                ))
            outline = ReportOutline(
                title=outline_data['title'],
                summary=outline_data['summary'],
                sections=sections
            )
        
        # If markdown_content is empty, try reading from full_report.md
        markdown_content = data.get('markdown_content', '')
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()

        prediction_summary = data.get('prediction_summary')
        if not prediction_summary:
            prediction_summary_path = cls._get_prediction_summary_path(report_id)
            if os.path.exists(prediction_summary_path):
                with open(prediction_summary_path, 'r', encoding='utf-8') as f:
                    prediction_summary = json.load(f)
        if not prediction_summary:
            prediction_summary = PredictionLedgerManager.get_prediction_summary(report_id)
        
        source_manifest = cls.get_source_manifest(report_id)

        return Report(
            report_id=data['report_id'],
            simulation_id=data['simulation_id'],
            graph_id=data['graph_id'],
            simulation_requirement=data['simulation_requirement'],
            status=ReportStatus(data['status']),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at', ''),
            error=data.get('error')
            ,
            usage=data.get('usage'),
            prediction_summary=prediction_summary,
            language_used=data.get('language_used', 'en'),
            analysis_mode=normalize_analysis_mode(data.get('analysis_mode')),
            source_manifest_summary=data.get('source_manifest_summary') or (source_manifest.summary() if source_manifest else {}),
            explainability=data.get('explainability') or {},
        )
    
    @classmethod
    def get_report_by_simulation(
        cls,
        simulation_id: str,
        *,
        language_used: Optional[str] = None,
        analysis_mode: Optional[str] = None,
        statuses: Optional[List[ReportStatus]] = None,
    ) -> Optional[Report]:
        """Get report by simulation ID"""
        requested_mode = normalize_analysis_mode(analysis_mode) if analysis_mode is not None else None
        allowed_statuses = {status.value if isinstance(status, ReportStatus) else str(status) for status in (statuses or [])}
        for report in cls.list_reports(simulation_id=simulation_id, limit=200):
            if language_used is not None and getattr(report, "language_used", "en") != language_used:
                continue
            if requested_mode is not None and normalize_analysis_mode(getattr(report, "analysis_mode", ANALYSIS_MODE_GLOBAL)) != requested_mode:
                continue
            if allowed_statuses and report.status.value not in allowed_statuses:
                continue
            return report
        return None
    
    @classmethod
    def list_reports(cls, simulation_id: Optional[str] = None, limit: int = 50) -> List[Report]:
        """List reports"""
        cls._ensure_reports_dir()
        
        reports = []
        for report_id in cls._store().list_resource_ids(REPORT_NAMESPACE):
            report = cls.get_report(report_id)
            if report and (simulation_id is None or report.simulation_id == simulation_id):
                reports.append(report)
        
        # Sort by creation time descending
        reports.sort(key=lambda r: r.created_at, reverse=True)
        
        return reports[:limit]
    
    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """Delete report (entire folder)"""
        deleted = cls._store().delete_resource(REPORT_NAMESPACE, report_id)
        if deleted:
            logger.info(f"Report folder deleted: {report_id}")
        return deleted
