"""
GraphQL Schema

Creates the Strawberry GraphQL schema for the All-Thing-Eye platform.
"""

import strawberry
from .queries import Query


# Create GraphQL schema
schema = strawberry.Schema(
    query=Query,
    # Future: Add mutations and subscriptions here
    # mutation=Mutation,
    # subscription=Subscription,
)
