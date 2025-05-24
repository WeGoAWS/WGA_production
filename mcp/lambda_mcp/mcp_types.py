"""Type definitions for MCP protocol and diagram utilities"""
from typing import Optional, Any, Dict, List
from dataclasses import dataclass
from enum import Enum

@dataclass
class JSONRPCError:
    code: int
    message: str
    data: Optional[Any] = None

    def model_dump_json(self) -> str:
        import json
        return json.dumps({
            "code": self.code,
            "message": self.message,
            **({"data": self.data} if self.data is not None else {})
        })

@dataclass
class JSONRPCResponse:
    jsonrpc: str
    id: Optional[str]
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None
    errorContent: Optional[List[Dict]] = None

    def model_dump_json(self) -> str:
        import json
        data = {
            "jsonrpc": self.jsonrpc,
            "id": self.id
        }
        if self.result is not None:
            data["result"] = self.result
        if self.error is not None:
            data["error"] = json.loads(self.error.model_dump_json())
        if self.errorContent is not None:
            data["errorContent"] = self.errorContent
        return json.dumps(data)

@dataclass
class ServerInfo:
    name: str
    version: str

    def model_dump(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version
        }

@dataclass
class Capabilities:
    tools: Dict[str, bool]

    def model_dump(self) -> Dict:
        return {
            "tools": self.tools
        }

@dataclass
class InitializeResult:
    protocolVersion: str
    serverInfo: ServerInfo
    capabilities: Capabilities

    def model_dump(self) -> Dict:
        return {
            "protocolVersion": self.protocolVersion,
            "serverInfo": self.serverInfo.model_dump(),
            "capabilities": self.capabilities.model_dump()
        }

    def model_dump_json(self) -> str:
        import json
        return json.dumps(self.model_dump())

@dataclass
class JSONRPCRequest:
    jsonrpc: str
    id: Optional[str]
    method: str
    params: Optional[Dict] = None

    @classmethod
    def model_validate(cls, data: Dict) -> 'JSONRPCRequest':
        return cls(
            jsonrpc=data["jsonrpc"],
            id=data.get("id"),
            method=data["method"],
            params=data.get("params")
        )

@dataclass
class TextContent:
    text: str
    type: str = "text"

    def model_dump(self) -> Dict:
        return {
            "type": self.type,
            "text": self.text
        }

    def model_dump_json(self) -> str:
        import json
        return json.dumps(self.model_dump())

@dataclass
class ErrorContent:
    text: str
    type: str = "error"

    def model_dump(self) -> Dict:
        return {
            "type": self.type,
            "text": self.text
        }

    def model_dump_json(self) -> str:
        import json
        return json.dumps(self.model_dump())

@dataclass
class ImageContent:
    data: str
    mimeType: str
    type: str = "image"

    def model_dump(self) -> Dict:
        return {
            "type": self.type,
            "data": self.data,
            "mimeType": self.mimeType
        }

    def model_dump_json(self) -> str:
        import json
        return json.dumps(self.model_dump())

@dataclass
class SearchResult:
    """Search result from AWS documentation search."""
    rank_order: int
    url: str
    title: str
    context: Optional[str] = None

    def model_dump(self) -> Dict:
        return {
            "rank_order": self.rank_order,
            "url": self.url,
            "title": self.title,
            "context": self.context
        }

@dataclass
class RecommendationResult:
    """Recommendation result from AWS documentation."""
    url: str
    title: str
    context: Optional[str] = None

    def model_dump(self) -> Dict:
        return {
            "url": self.url,
            "title": self.title,
            "context": self.context
        }

class DiagramType(str, Enum):
    """Enum for supported diagram types."""
    AWS = 'aws'
    SEQUENCE = 'sequence'
    FLOW = 'flow'
    CLASS = 'class'
    K8S = 'k8s'
    ONPREM = 'onprem'
    CUSTOM = 'custom'
    ALL = 'all'

@dataclass
class SecurityIssue:
    """Model for security issues found in code."""
    severity: str
    confidence: str
    line: int
    issue_text: str
    issue_type: str

@dataclass
class CodeMetrics:
    """Model for code metrics."""
    total_lines: int
    code_lines: int
    comment_lines: int
    blank_lines: int
    comment_ratio: float

@dataclass
class CodeScanResult:
    """Model for code scan result."""
    has_errors: bool
    syntax_valid: bool
    security_issues: List[SecurityIssue]
    error_message: Optional[str] = None
    metrics: Optional[CodeMetrics] = None

    def __init__(self, has_errors: bool, syntax_valid: bool, security_issues: List[SecurityIssue] = None, error_message: str = None, metrics: CodeMetrics = None):
        self.has_errors = has_errors
        self.syntax_valid = syntax_valid
        self.security_issues = security_issues or []
        self.error_message = error_message
        self.metrics = metrics

@dataclass
class DiagramGenerateResponse:
    """Response model for diagram generation."""
    status: str  # 'success' or 'error'
    url: Optional[str] = None
    s3_key: Optional[str] = None
    message: str = ""

@dataclass
class DiagramExampleResponse:
    """Response model for diagram examples."""
    examples: Dict[str, str]

@dataclass
class DiagramIconsResponse:
    """Response model for listing available diagram icons."""
    providers: Dict[str, Dict[str, List[str]]]
    filtered: bool = False
    filter_info: Optional[Dict[str, str]] = None