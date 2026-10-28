from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

class AuditRequest(BaseModel):
    url: str
    demo: bool = False

class SuggestedFix(BaseModel):
    language: Literal["css", "html", "js", "python", "other"] = "css"
    code: str
    explanation: str

class Issue(BaseModel):
    title: str
    category: Literal["layout", "visual", "ux", "accessibility", "functional", "responsive"]
    severity: Literal["critical", "high", "medium", "low"]
    viewport: Literal["desktop", "mobile", "both"] = "desktop"
    description: str
    location: str
    suggested_fix: SuggestedFix
    test_scenario: str

class DOMSignals(BaseModel):
    console_errors: List[str] = Field(default_factory=list)
    failed_requests: List[Dict[str, Any]] = Field(default_factory=list)
    broken_images: List[Dict[str, Any]] = Field(default_factory=list)
    horizontal_overflow: bool = False
    overflow_details: Optional[Dict[str, Any]] = None
    clipped_elements: List[Dict[str, Any]] = Field(default_factory=list)
    small_touch_targets: List[Dict[str, Any]] = Field(default_factory=list)
    missing_alt_images: List[Dict[str, Any]] = Field(default_factory=list)
    missing_form_labels: List[Dict[str, Any]] = Field(default_factory=list)

class AuditScreenshots(BaseModel):
    desktop: str
    mobile: str

class AuditReport(BaseModel):
    url: str
    timestamp: str
    is_live: bool = True
    screenshots: AuditScreenshots
    signals: Dict[str, DOMSignals]
    issues: List[Issue]
    summary: str
    score: int = Field(ge=0, le=100)
    duration_seconds: float
