"""
GraphQL Extensions

Custom extensions for performance monitoring, logging, and optimization.
"""

import time
from typing import Any, Dict
from strawberry.extensions import SchemaExtension

from src.utils.logger import get_logger

logger = get_logger(__name__)


class PerformanceMonitoringExtension(SchemaExtension):
    """
    Extension to monitor GraphQL query performance.
    
    Logs execution time, operation name, and complexity metrics.
    """
    
    def on_operation(self) -> None:
        """Called when operation starts"""
        self.start_time = time.time()
        
        # Get operation details
        operation = self.execution_context.operation_name
        query = self.execution_context.query
        
        # Log query start
        if operation:
            logger.info(f"🔍 GraphQL query started: {operation}")
        else:
            # Log first 100 chars of query if no operation name
            query_preview = query[:100] + "..." if len(query) > 100 else query
            logger.debug(f"🔍 GraphQL query: {query_preview}")
    
    def on_execute(self) -> None:
        """Called during query execution"""
        pass
    
    def get_results(self) -> Dict[str, Any]:
        """Called after query execution"""
        # Calculate execution time
        execution_time = time.time() - self.start_time
        
        operation = self.execution_context.operation_name
        
        # Log performance metrics
        if execution_time > 1.0:
            # Slow query warning (> 1 second)
            logger.warning(
                f"⚠️  Slow GraphQL query: {operation or 'anonymous'} "
                f"took {execution_time:.2f}s"
            )
        else:
            logger.info(
                f"✅ GraphQL query completed: {operation or 'anonymous'} "
                f"in {execution_time*1000:.0f}ms"
            )
        
        # Return timing information (optional, can be included in response)
        return {
            "executionTime": execution_time,
            "operationName": operation,
        }


class QueryComplexityExtension(SchemaExtension):
    """
    Extension to analyze and log query complexity.
    
    Helps identify expensive queries that might need optimization.
    """
    
    def on_operation(self) -> None:
        """Analyze query complexity"""
        query = self.execution_context.query
        
        # Simple complexity metrics
        field_count = query.count('{')
        alias_count = query.count(':')
        
        complexity_score = field_count + (alias_count * 2)
        
        # Log if query is complex
        if complexity_score > 50:
            logger.warning(
                f"⚠️  Complex GraphQL query detected: "
                f"score={complexity_score}, fields≈{field_count}"
            )
        elif complexity_score > 20:
            logger.info(
                f"📊 Moderate GraphQL query: "
                f"score={complexity_score}, fields≈{field_count}"
            )
    
    def get_results(self) -> Dict[str, Any]:
        """Return complexity information"""
        return {}


class ErrorLoggingExtension(SchemaExtension):
    """
    Extension to log GraphQL errors with context.
    """
    
    def on_operation(self) -> None:
        """Store operation context for error logging"""
        self.operation = self.execution_context.operation_name
        self.query = self.execution_context.query
    
    def get_results(self) -> Dict[str, Any]:
        """Check for errors and log them"""
        result = self.execution_context.result
        
        if result and hasattr(result, 'errors') and result.errors:
            for error in result.errors:
                logger.error(
                    f"❌ GraphQL error in {self.operation or 'anonymous'}: "
                    f"{error.message}"
                )
                
                # Log error path if available
                if hasattr(error, 'path') and error.path:
                    logger.error(f"   Path: {' → '.join(str(p) for p in error.path)}")
                
                # Log error location if available
                if hasattr(error, 'locations') and error.locations:
                    for loc in error.locations:
                        logger.error(f"   Location: line {loc.line}, column {loc.column}")
        
        return {}

