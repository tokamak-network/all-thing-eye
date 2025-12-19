#!/usr/bin/env python3
"""
Extract ActivitiesView component from activities/page.tsx to components/ActivitiesView.tsx
"""

import os

# Paths
activities_page = "frontend/src/app/activities/page.tsx"
activities_view = "frontend/src/components/ActivitiesView.tsx"

# Read the activities page
with open(activities_page, "r", encoding="utf-8") as f:
    content = f.read()

# Find the ActivitiesView function start (after interface)
interface_start = content.find("interface ActivitiesViewProps")
if interface_start == -1:
    print("Error: Could not find ActivitiesViewProps interface")
    exit(1)

# Find the ActivitiesView function
view_start = content.find("export function ActivitiesView({", interface_start)
if view_start == -1:
    # Try without export
    view_start = content.find("function ActivitiesView({", interface_start)
    if view_start == -1:
        print("Error: Could not find ActivitiesView function")
        exit(1)

# Find the end of ActivitiesView function (before export default ActivitiesPage)
page_export = content.find("export default function ActivitiesPage()", view_start)
if page_export == -1:
    print("Error: Could not find ActivitiesPage export")
    exit(1)

# Extract ActivitiesView (include interface and function, but change export)
activities_view_content = content[:view_start].rstrip() + "\n\n"

# Add interface
interface_end = content.find("}", interface_start) + 1
activities_view_content += content[interface_start:interface_end] + "\n\n"

# Add ActivitiesView function (change export function to export default function)
view_function = content[view_start:page_export].rstrip()
# Replace "export function" with "export default function"
view_function = view_function.replace("export function ActivitiesView", "export default function ActivitiesView", 1)
activities_view_content += view_function + "\n"

# Write to new file
os.makedirs(os.path.dirname(activities_view), exist_ok=True)
with open(activities_view, "w", encoding="utf-8") as f:
    f.write(activities_view_content)

print(f"✅ Created {activities_view}")
print(f"   Extracted {len(activities_view_content)} characters")

