"""
GraphQL Schema

Creates the Strawberry GraphQL schema for the All-Thing-Eye platform.
"""

import strawberry
from strawberry.extensions import QueryDepthLimiter, MaxTokensLimiter
from .queries import Query
from .extensions import (
    PerformanceMonitoringExtension,
    QueryComplexityExtension,
    ErrorLoggingExtension,
)


# Create GraphQL schema with security and monitoring extensions
schema = strawberry.Schema(
    query=Query,
    # Future: Add mutations and subscriptions here
    # mutation=Mutation,
    # subscription=Subscription,
    extensions=[
        # Security: Limit query depth to prevent deeply nested queries
        QueryDepthLimiter(max_depth=10),
        
        # Security: Limit query complexity (number of tokens/fields)
        MaxTokensLimiter(max_token_count=1000),
        
        # Monitoring: Track query performance
        PerformanceMonitoringExtension,
        
        # Monitoring: Analyze query complexity
        QueryComplexityExtension,
        
        # Logging: Log errors with context
        ErrorLoggingExtension,
    ]
)
