"""
------------------------------------------------------------------------
File : results.py
Description: Result - what an InputHandler.handle() (and every other
             core use case) returns. Its to_dict() shape mirrors
             Models/api_response_model.py's ApiResponse.to_dict() exactly
             (http_status_code/response_data/message), so soup/api can
             turn a Result straight into the same JSON envelope the
             legacy ApiResponse produced - no frontend-visible change.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Result:
    http_status_code: int
    message: str
    response_data: Any = None

    def to_dict(self) -> dict:
        return {
            "http_status_code": self.http_status_code,
            "response_data": self.response_data,
            "message": self.message,
        }
