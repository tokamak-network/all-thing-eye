"""
TOON (Token-Oriented Object Notation) Encoder

A Python implementation of TOON format for efficient LLM data serialization.
Based on the TOON specification: https://github.com/toon-format/toon

TOON is optimized for:
- Token efficiency (20-40% fewer tokens than JSON)
- LLM readability (explicit structure with array lengths and field headers)
- Human readability (indented, self-documenting format)
"""

from typing import Any, Dict, List, Union
from datetime import datetime, date
import json


class TOONEncoder:
    """Encoder for TOON (Token-Oriented Object Notation) format"""
    
    def __init__(self, indent: int = 2, delimiter: str = ','):
        """
        Initialize TOON encoder
        
        Args:
            indent: Number of spaces per indentation level (default: 2)
            delimiter: Delimiter for array values (',' | '\t' | '|')
        """
        self.indent = indent
        self.delimiter = delimiter
    
    def encode(self, data: Any, level: int = 0) -> str:
        """
        Encode Python data to TOON format
        
        Args:
            data: Python data structure to encode
            level: Current indentation level
            
        Returns:
            TOON-formatted string
        """
        if data is None:
            return self._encode_primitive(data, level)
        elif isinstance(data, (str, int, float, bool)):
            return self._encode_primitive(data, level)
        elif isinstance(data, dict):
            return self._encode_object(data, level)
        elif isinstance(data, list):
            return self._encode_array(data, level)
        elif isinstance(data, (datetime, date)):
            return self._encode_primitive(data.isoformat(), level)
        else:
            # Fallback to JSON serialization
            return self._encode_primitive(str(data), level)
    
    def _encode_primitive(self, value: Any, level: int) -> str:
        """Encode primitive values"""
        indent_str = ' ' * (self.indent * level)
        
        if value is None:
            return f"{indent_str}null"
        elif isinstance(value, bool):
            return f"{indent_str}{str(value).lower()}"
        elif isinstance(value, (int, float)):
            return f"{indent_str}{value}"
        elif isinstance(value, str):
            # Quote if contains delimiter, newline, or starts with special chars
            needs_quotes = (
                self.delimiter in value or
                '\n' in value or
                value.startswith(('-', '[', '{')) or
                value in ('true', 'false', 'null') or
                value == ''
            )
            if needs_quotes:
                # Escape quotes and backslashes
                escaped = value.replace('\\', '\\\\').replace('"', '\\"')
                return f'{indent_str}"{escaped}"'
            return f"{indent_str}{value}"
        else:
            return f"{indent_str}{value}"
    
    def _encode_object(self, obj: Dict[str, Any], level: int) -> str:
        """Encode dictionary/object"""
        if not obj:
            return ""
        
        indent_str = ' ' * (self.indent * level)
        lines = []
        
        for key, value in obj.items():
            if isinstance(value, dict):
                # Nested object
                lines.append(f"{indent_str}{key}:")
                nested = self._encode_object(value, level + 1)
                if nested:
                    lines.append(nested)
            elif isinstance(value, list):
                # Array
                array_str = self._encode_array_with_key(key, value, level)
                lines.append(array_str)
            else:
                # Primitive value
                value_str = self._format_value(value)
                lines.append(f"{indent_str}{key}: {value_str}")
        
        return '\n'.join(lines)
    
    def _encode_array_with_key(self, key: str, arr: List[Any], level: int) -> str:
        """Encode array with key (for object properties)"""
        indent_str = ' ' * (self.indent * level)
        
        if not arr:
            return f"{indent_str}{key}[0]:"
        
        # Check if it's a tabular array (list of uniform objects)
        if self._is_tabular_array(arr):
            return self._encode_tabular_array(key, arr, level)
        
        # Check if it's a primitive array
        if all(isinstance(item, (str, int, float, bool, type(None))) for item in arr):
            return self._encode_primitive_array(key, arr, level)
        
        # Mixed/complex array - use list format
        return self._encode_list_array(key, arr, level)
    
    def _encode_array(self, arr: List[Any], level: int) -> str:
        """Encode root-level array"""
        if not arr:
            return f"[0]:"
        
        # For root arrays, use similar logic
        if self._is_tabular_array(arr):
            fields = list(arr[0].keys())
            delimiter_display = self.delimiter if self.delimiter != '\t' else '\\t'
            header = f"[{len(arr)}{delimiter_display}]{{{self.delimiter.join(fields)}}}:"
            
            indent_str = ' ' * (self.indent * level)
            lines = [header]
            
            for item in arr:
                values = [self._format_value(item.get(f)) for f in fields]
                lines.append(f"{indent_str}  {self.delimiter.join(values)}")
            
            return '\n'.join(lines)
        
        # Primitive array
        if all(isinstance(item, (str, int, float, bool, type(None))) for item in arr):
            values = [self._format_value(item) for item in arr]
            return f"[{len(arr)}]: {self.delimiter.join(values)}"
        
        # Mixed array
        return self._encode_list_array_root(arr, level)
    
    def _is_tabular_array(self, arr: List[Any]) -> bool:
        """Check if array is tabular (uniform objects)"""
        if not arr or not isinstance(arr[0], dict):
            return False
        
        # All items must be dicts with the same keys
        first_keys = set(arr[0].keys())
        return all(isinstance(item, dict) and set(item.keys()) == first_keys for item in arr)
    
    def _encode_tabular_array(self, key: str, arr: List[Dict], level: int) -> str:
        """Encode tabular array (uniform objects)"""
        indent_str = ' ' * (self.indent * level)
        fields = list(arr[0].keys())
        
        # Build header with length, delimiter, and fields
        delimiter_display = self.delimiter if self.delimiter != '\t' else '\\t'
        header = f"{indent_str}{key}[{len(arr)}{delimiter_display}]{{{self.delimiter.join(fields)}}}:"
        
        lines = [header]
        
        # Build data rows
        for item in arr:
            values = [self._format_value(item.get(f)) for f in fields]
            row = f"{indent_str}  {self.delimiter.join(values)}"
            lines.append(row)
        
        return '\n'.join(lines)
    
    def _encode_primitive_array(self, key: str, arr: List[Any], level: int) -> str:
        """Encode primitive array (inline)"""
        indent_str = ' ' * (self.indent * level)
        values = [self._format_value(item) for item in arr]
        return f"{indent_str}{key}[{len(arr)}]: {self.delimiter.join(values)}"
    
    def _encode_list_array(self, key: str, arr: List[Any], level: int) -> str:
        """Encode mixed/complex array (list format)"""
        indent_str = ' ' * (self.indent * level)
        lines = [f"{indent_str}{key}[{len(arr)}]:"]
        
        for item in arr:
            if isinstance(item, (str, int, float, bool, type(None))):
                value_str = self._format_value(item)
                lines.append(f"{indent_str}  - {value_str}")
            elif isinstance(item, dict):
                lines.append(f"{indent_str}  -")
                nested = self._encode_object(item, level + 2)
                if nested:
                    lines.append(nested)
            elif isinstance(item, list):
                nested_arr = self._encode_array(item, level + 2)
                lines.append(f"{indent_str}  - {nested_arr}")
        
        return '\n'.join(lines)
    
    def _encode_list_array_root(self, arr: List[Any], level: int) -> str:
        """Encode root-level mixed array"""
        lines = [f"[{len(arr)}]:"]
        indent_str = ' ' * (self.indent * level)
        
        for item in arr:
            if isinstance(item, (str, int, float, bool, type(None))):
                value_str = self._format_value(item)
                lines.append(f"{indent_str}  - {value_str}")
            elif isinstance(item, dict):
                lines.append(f"{indent_str}  -")
                nested = self._encode_object(item, level + 2)
                if nested:
                    lines.append(nested)
        
        return '\n'.join(lines)
    
    def _format_value(self, value: Any) -> str:
        """Format a single value for output"""
        if value is None:
            return 'null'
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, str):
            # Quote if necessary
            needs_quotes = (
                self.delimiter in value or
                '\n' in value or
                value.startswith(('-', '[', '{')) or
                value in ('true', 'false', 'null') or
                value == ''
            )
            if needs_quotes:
                escaped = value.replace('\\', '\\\\').replace('"', '\\"')
                return f'"{escaped}"'
            return value
        else:
            return str(value)


def encode_toon(data: Any, indent: int = 2, delimiter: str = ',') -> str:
    """
    Convenience function to encode data to TOON format
    
    Args:
        data: Python data structure to encode
        indent: Number of spaces per indentation level (default: 2)
        delimiter: Delimiter for array values (',' | '\t' | '|')
    
    Returns:
        TOON-formatted string
    
    Example:
        >>> data = {
        ...     'items': [
        ...         {'sku': 'A1', 'qty': 2, 'price': 9.99},
        ...         {'sku': 'B2', 'qty': 1, 'price': 14.5}
        ...     ]
        ... }
        >>> print(encode_toon(data))
        items[2,]{sku,qty,price}:
          A1,2,9.99
          B2,1,14.5
    """
    encoder = TOONEncoder(indent=indent, delimiter=delimiter)
    return encoder.encode(data)


# Example usage
if __name__ == '__main__':
    # Test with sample data
    data = {
        'project': 'All-Thing-Eye',
        'members': [
            {'id': 1, 'name': 'Alice', 'role': 'admin'},
            {'id': 2, 'name': 'Bob', 'role': 'user'},
            {'id': 3, 'name': 'Charlie', 'role': 'user'}
        ],
        'tags': ['python', 'mongodb', 'fastapi'],
        'metadata': {
            'version': '1.0.0',
            'updated': '2025-01-17'
        }
    }
    
    print("=" * 60)
    print("TOON Format Example")
    print("=" * 60)
    print(encode_toon(data))
    print("=" * 60)

