"""
------------------------------------------------------------------------
File : results.py
Description: Result - the JSON envelope of the /api/v3 routes of
             soup/api: {http_status_code, response_data, message}, the
             shape the frontend's ApiService reads.
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "http_status_code": self.http_status_code,
            "response_data": self.response_data,
            "message": self.message,
        }
