"""Web/API interface stubs — reserved for future development.

These modules define the HTTP/WebSocket/API contracts for:
- Uploading PDF scores
- Starting reconstruction jobs
- Querying job status
- Downloading results
- Enterprise licensing and usage tracking

They are NOT implemented in this phase. They exist only to reserve the
API surface and prevent future breaking changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobStatus:
    """Status of a reconstruction job."""
    job_id: str = ""
    status: str = "pending"  # pending | running | completed | failed
    progress: float = 0.0
    result_url: str = ""
    error: str = ""


@dataclass
class UploadResponse:
    """Response to a PDF upload."""
    job_id: str = ""
    file_name: str = ""
    file_size: int = 0


class ScoreService:
    """Stub service for future Web API."""

    def upload_pdf(self, file_data: bytes, file_name: str) -> UploadResponse:
        """STUB: accept PDF upload."""
        raise NotImplementedError("Web API not implemented in this phase")

    def get_job_status(self, job_id: str) -> JobStatus:
        """STUB: query job status."""
        raise NotImplementedError("Web API not implemented in this phase")

    def download_result(self, job_id: str) -> bytes:
        """STUB: download result."""
        raise NotImplementedError("Web API not implemented in this phase")
