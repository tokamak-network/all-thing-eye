"""
GraphQL API Module

Strawberry GraphQL implementation for All-Thing-Eye platform.
Provides flexible querying capabilities for multi-source activity data.
"""

from .schema import schema

__all__ = ["schema"]
