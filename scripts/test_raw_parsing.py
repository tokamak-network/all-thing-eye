#!/usr/bin/env python3
"""
Test script to parse _raw field from recordings_daily collection.
Tests different parsing strategies until we get valid JSON.
"""

import json
import re
from typing import Optional, Dict, Any


def extract_json_from_raw(raw_content: str) -> Optional[str]:
    """Extract JSON from _raw field, handling markdown code blocks."""
    # First, try to extract JSON from markdown code blocks
    code_block_start = raw_content.find("```json")
    if code_block_start != -1:
        after_start = raw_content[code_block_start + 7:]  # Skip "```json"
        code_block_end = after_start.find("```")
        if code_block_end != -1:
            extracted = after_start[:code_block_end].strip()
            return extracted
        else:
            # No closing ```, use everything after ```json
            extracted = after_start.strip()
            return extracted
    
    # If no code block, try to find JSON object directly
    json_start = raw_content.find("{")
    if json_start != -1:
        return raw_content[json_start:].strip()
    
    return None


def find_complete_json_object(content: str) -> Optional[tuple[int, int]]:
    """Find the start and end indices of a complete JSON object."""
    start_index = content.find("{")
    if start_index == -1:
        return None
    
    brace_count = 0
    in_string = False
    escape_next = False
    end_index = start_index
    
    for i in range(start_index, len(content)):
        char = content[i]
        
        if escape_next:
            escape_next = False
            continue
        
        if char == "\\":
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if not in_string:
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_index = i
                    return (start_index, end_index)
    
    return None


def fix_incomplete_json(json_str: str) -> str:
    """Attempt to fix incomplete JSON by removing incomplete fields."""
    # Check if we're in a string at the end
    in_string = False
    escape_next = False
    last_quote_index = -1
    
    for i in range(len(json_str)):
        char = json_str[i]
        
        if escape_next:
            escape_next = False
            continue
        
        if char == "\\":
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            if in_string:
                last_quote_index = i
    
    # If we're in a string at the end, find the last complete string
    if in_string and last_quote_index != -1:
        # Find the last complete field/array item
        # Look backwards for the last complete string value
        # Try to find pattern: "value", or "value"]
        
        # Find the last complete array item or object field
        # Look backwards from the end for patterns
        lines = json_str.split('\n')
        
        # Find the last line that looks complete
        # Look for the last complete array item (ending with ",)
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            # If line ends with ", it's a complete string value
            if line.endswith('",'):
                # Keep up to this line, but remove the comma since we'll add closing brackets
                fixed_lines = lines[:i+1]
                last_line = fixed_lines[-1]
                # Remove trailing comma - this is the last complete item
                # Use rstrip to preserve indentation but remove trailing comma and whitespace
                last_line_cleaned = last_line.rstrip()
                if last_line_cleaned.endswith(','):
                    # Remove comma but preserve indentation
                    indent = len(last_line) - len(last_line.lstrip())
                    fixed_lines[-1] = ' ' * indent + last_line_cleaned[:-1]
                fixed = '\n'.join(fixed_lines)
                # Also remove any trailing comma at the end of the entire string
                fixed = fixed.rstrip()
                fixed = re.sub(r',\s*$', '', fixed)
                return fixed
            # If line ends with ], or }, it might be complete
            elif line.endswith('],') or line.endswith('},'):
                # Keep up to this line
                fixed = '\n'.join(lines[:i+1])
                # Remove trailing comma if it's the last item
                fixed = re.sub(r',\s*$', '', fixed)
                return fixed
        
        # If we can't find a complete line, try to find the last complete string
        # Look for the pattern: "text", (with comma or closing bracket)
        # Find last occurrence of ", or "]
        last_comma_quote = json_str.rfind('",')
        last_bracket_quote = json_str.rfind('"]')
        
        if last_comma_quote > last_bracket_quote:
            # Cut at the quote (before the comma)
            # This removes the incomplete next item
            fixed = json_str[:last_comma_quote + 1]  # Keep the quote, remove comma and everything after
            return fixed
        elif last_bracket_quote != -1:
            # Cut at the bracket after the quote
            fixed = json_str[:last_bracket_quote + 2]
            return fixed
        else:
            # Just cut at the last quote
            return json_str[:last_quote_index + 1]
    
    # If not in string, just remove trailing incomplete parts
    # Remove trailing commas, colons, etc.
    fixed = json_str.rstrip()
    fixed = re.sub(r',\s*$', '', fixed)
    fixed = re.sub(r':\s*$', '', fixed)
    
    return fixed


def parse_raw_analysis(raw_content: str) -> Optional[Dict[str, Any]]:
    """Parse _raw field and return parsed JSON object."""
    print(f"Raw content length: {len(raw_content)}")
    print(f"First 200 chars: {raw_content[:200]}")
    print(f"Last 200 chars: {raw_content[-200:]}")
    
    # Extract JSON from markdown code block
    extracted = extract_json_from_raw(raw_content)
    if not extracted:
        print("Could not extract JSON from code block")
        return None
    
    print(f"\nExtracted length: {len(extracted)}")
    print(f"Extracted first 200 chars: {extracted[:200]}")
    print(f"Extracted last 200 chars: {extracted[-200:]}")
    
    # Try to find complete JSON object
    json_range = find_complete_json_object(extracted)
    
    if json_range:
        start, end = json_range
        json_content = extracted[start:end+1]
        print(f"\n✅ Found complete JSON: {start} to {end}, length: {len(json_content)}")
    else:
        print("\n⚠️  JSON appears incomplete, attempting to fix...")
        # Find start of JSON
        start_index = extracted.find("{")
        if start_index == -1:
            print("❌ No opening brace found")
            return None
        
        json_content = extracted[start_index:]
        print(f"Before fix, last 100 chars: {json_content[-100:]}")
        
        json_content = fix_incomplete_json(json_content)
        print(f"After fix, last 100 chars: {json_content[-100:]}")
        
        # Remove any trailing comma - this is critical
        # Only remove comma at the very end (not multiline)
        json_content = json_content.rstrip()
        # Remove trailing comma if present
        json_content = re.sub(r',\s*$', '', json_content)
        
        # Count unclosed braces and brackets
        # We need to track them separately to close in correct order
        brace_count = 0
        bracket_count = 0
        in_string = False
        escape_next = False
        
        for char in json_content:
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                elif char == "[":
                    bracket_count += 1
                elif char == "]":
                    bracket_count -= 1
        
        print(f"Unclosed: {bracket_count} brackets, {brace_count} braces")
        
        # Before adding closing brackets/braces, remove any comma that's right before them
        json_content = re.sub(r'",(\s*)([\]}]+)', r'"\1\2', json_content)
        
        # Close in correct order: we need to close in reverse order of opening
        # If we have nested structures like: { participants: [ { action_items: [...] } ] }
        # We need to close: ] (action_items) -> } (participant) -> ] (participants) -> } (root)
        # But since we're counting globally, we need to close brackets and braces alternately
        # Actually, let's close them in the order: first one bracket (innermost array), 
        # then one brace (object), then remaining brackets, then remaining braces
        
        # Simple approach: close brackets first, then braces
        # But this might be wrong if structure is: { arr: [ { } ] }
        # Let's try: close one bracket, one brace, repeat
        closing_chars = ""
        remaining_brackets = bracket_count
        remaining_braces = brace_count
        
        # Alternate closing: bracket, brace, bracket, brace...
        while remaining_brackets > 0 or remaining_braces > 0:
            if remaining_brackets > 0:
                closing_chars += "]"
                remaining_brackets -= 1
            if remaining_braces > 0:
                closing_chars += "}"
                remaining_braces -= 1
        
        json_content += closing_chars
        print(f"Added closing sequence: {repr(closing_chars)}")
        
        # Final cleanup: remove any trailing comma before closing brackets/braces
        json_content = re.sub(r'",(\s*)([\]}]+)', r'"\1\2', json_content)
    
    # Try to parse
    print(f"\nFinal JSON last 200 chars: {json_content[-200:]}")
    
    # Debug: check for any remaining commas before closing brackets
    comma_before_bracket = json_content.rfind('",')
    if comma_before_bracket != -1:
        after_comma = json_content[comma_before_bracket+2:].strip()
        if after_comma.startswith(']') or after_comma.startswith('}'):
            print(f"⚠️  Found comma before closing bracket at position {comma_before_bracket}")
            print(f"   Context: {repr(json_content[comma_before_bracket-20:comma_before_bracket+30])}")
            # Force remove it
            json_content = json_content[:comma_before_bracket+1] + json_content[comma_before_bracket+2:]
            print(f"   Removed comma, retrying...")
    
    try:
        parsed = json.loads(json_content)
        print(f"\n✅ Successfully parsed JSON!")
        print(f"Keys: {list(parsed.keys())}")
        if 'summary' in parsed:
            print(f"Has summary.overview: {'overview' in parsed.get('summary', {})}")
            if 'overview' in parsed.get('summary', {}):
                print(f"Overview keys: {list(parsed['summary']['overview'].keys())}")
        if 'participants' in parsed:
            print(f"Participants count: {len(parsed.get('participants', []))}")
        return parsed
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON parse error: {e}")
        print(f"Error at position: {e.pos}")
        if e.pos < len(json_content):
            start = max(0, e.pos - 100)
            end = min(len(json_content), e.pos + 100)
            print(f"Context around error:\n{json_content[start:end]}")
            # Show the exact character at error position
            if e.pos < len(json_content):
                print(f"Character at error: {repr(json_content[e.pos])}")
                print(f"Characters before: {repr(json_content[max(0, e.pos-5):e.pos])}")
                print(f"Characters after: {repr(json_content[e.pos:min(len(json_content), e.pos+5)])}")
        return None


if __name__ == "__main__":
    # Test with actual _raw content from user
    # The data ends with incomplete string: "action_items": [..., "\n\n"
    raw_content = """```json
{
  "summary": {
    "overview": {
      "meeting_count": 10,
      "total_time": "5 hours 50 minutes",
      "main_topics": [
        "Project TRH hiring and development team management",
        "Reward and bug bounty program design",
        "DAO contract and Layer 2 candidate management",
        "Website updates and user guide review",
        "L2 chain and circuit input verification",
        "2026 roadmap planning"
      ]
    },
    "topics": [
      {
        "topic": "Project TRH Development Team Management & Hiring",
        "related_meetings": [
          "Project TRH_ShortCall_Praveen,Ale"
        ],
        "key_discussions": [
          "Discussed the suitability of a new full-stack developer candidate and the team's current capacity.",
          "Addressed concerns about the negative impact of frequent hiring and firing on team morale."
        ],
        "key_decisions": [
          "Praveen to discuss the new hire's potential role with Theo and assess team workload.",
          "Praveen to share final decision with Aaron after discussion with Theo."
        ],
        "progress": [
          "Shilendra volunteered to take ownership of the platform side, with Sahil assisting."
        ],
        "issues": [
          "The candidate's asking salary (70k) is considered high based on location.",
          "Concern that a new hire might not have enough work, given the existing team's willingness to contribute."
        ]
      }
    ],
    "key_decisions": [],
    "major_achievements": [],
    "common_issues": []
  },
  "participants": [
    {
      "name": "YEONGJU BAK",
      "speaking_time": "00:23:31",
      "speaking_percentage": 19.0,
      "key_activities": [
        "Provided clarification and insight into the DAO contract and Layer 2 candidate management.",
        "Explained the reasoning behind the レジスター レイヤー 2 캔디デート バイオ너 function.",
        "Described L2 code and processes",
        "Contributed with expertise and insight. "
      ],
      "progress": [
        "Made some specification for LRM to developing the SK staking B3."
      ],
      "issues": [
        "Recognized the older code doesn't meshing with newer L2 and DAO concepts and the difficulty of maintenance."
      ],
      "action_items": [
        "로 로드맵을 조금에 좀 구체적이고 조금 약간 발전적이고 제가 생각했을 땐 내년 가을이나 겨울 전에 뭔가 하나는 어 꼭지 잡고 발표할 수 있을 수 있는 거를 목표.",
        "

"""
    
    result = parse_raw_analysis(raw_content)
    
    if result:
        print("\n" + "="*60)
        print("✅ PARSING SUCCESSFUL!")
        print("="*60)
        print(f"Summary keys: {list(result.get('summary', {}).keys())}")
        if 'summary' in result and 'overview' in result['summary']:
            print(f"Overview keys: {list(result['summary']['overview'].keys())}")
            print(f"Main topics: {result['summary']['overview'].get('main_topics', [])}")
        if 'participants' in result:
            print(f"Participants: {len(result['participants'])}")
            if result['participants']:
                print(f"First participant: {result['participants'][0].get('name')}")
    else:
        print("\n" + "="*60)
        print("❌ PARSING FAILED")
        print("="*60)

