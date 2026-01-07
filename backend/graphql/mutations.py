"""
GraphQL Mutations

Defines Strawberry GraphQL mutations for the All-Thing-Eye platform.
"""

import strawberry
from typing import Optional
from datetime import datetime
from bson import ObjectId

from .types import Member


@strawberry.type
class MemberUpdateResult:
    """Result of a member update operation"""
    success: bool
    message: str
    member: Optional[Member] = None


@strawberry.type
class Mutation:
    """Root Mutation type for GraphQL API"""
    
    @strawberry.mutation
    async def deactivate_member(
        self,
        info,
        member_id: str,
        resignation_reason: Optional[str] = None,
        resigned_at: Optional[datetime] = None
    ) -> MemberUpdateResult:
        """
        Mark a member as inactive (resigned).
        
        The member will be hidden from the default member list but their
        historical activity data will be preserved for reporting.
        
        Args:
            member_id: MongoDB ObjectId of the member
            resignation_reason: Optional reason for leaving
            resigned_at: Resignation date (defaults to current date)
            
        Returns:
            MemberUpdateResult with success status and updated member
        """
        db = info.context['db']
        
        try:
            object_id = ObjectId(member_id)
        except Exception:
            return MemberUpdateResult(
                success=False,
                message=f"Invalid member ID: {member_id}"
            )
        
        # Find the member
        doc = await db['members'].find_one({'_id': object_id})
        if not doc:
            return MemberUpdateResult(
                success=False,
                message=f"Member not found: {member_id}"
            )
        
        # Update member status
        update_data = {
            'is_active': False,
            'resigned_at': resigned_at or datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        if resignation_reason:
            update_data['resignation_reason'] = resignation_reason
        
        await db['members'].update_one(
            {'_id': object_id},
            {'$set': update_data}
        )
        
        # Fetch updated member
        updated_doc = await db['members'].find_one({'_id': object_id})
        
        member = Member(
            id=str(updated_doc['_id']),
            name=updated_doc.get('name', 'Unknown'),
            email=updated_doc.get('email', ''),
            role=updated_doc.get('role'),
            team=updated_doc.get('team'),
            github_username=updated_doc.get('github_username'),
            slack_id=updated_doc.get('slack_id'),
            notion_id=updated_doc.get('notion_id'),
            eoa_address=updated_doc.get('eoa_address'),
            recording_name=updated_doc.get('recording_name'),
            projects=updated_doc.get('projects', []),
            is_active=updated_doc.get('is_active', True),
            resigned_at=updated_doc.get('resigned_at'),
            resignation_reason=updated_doc.get('resignation_reason')
        )
        
        return MemberUpdateResult(
            success=True,
            message=f"Member '{doc['name']}' has been marked as inactive",
            member=member
        )
    
    @strawberry.mutation
    async def reactivate_member(
        self,
        info,
        member_id: str
    ) -> MemberUpdateResult:
        """
        Reactivate an inactive member.
        
        Args:
            member_id: MongoDB ObjectId of the member
            
        Returns:
            MemberUpdateResult with success status and updated member
        """
        db = info.context['db']
        
        try:
            object_id = ObjectId(member_id)
        except Exception:
            return MemberUpdateResult(
                success=False,
                message=f"Invalid member ID: {member_id}"
            )
        
        # Find the member
        doc = await db['members'].find_one({'_id': object_id})
        if not doc:
            return MemberUpdateResult(
                success=False,
                message=f"Member not found: {member_id}"
            )
        
        # Update member status
        await db['members'].update_one(
            {'_id': object_id},
            {
                '$set': {
                    'is_active': True,
                    'updated_at': datetime.utcnow()
                },
                '$unset': {
                    'resigned_at': '',
                    'resignation_reason': ''
                }
            }
        )
        
        # Fetch updated member
        updated_doc = await db['members'].find_one({'_id': object_id})
        
        member = Member(
            id=str(updated_doc['_id']),
            name=updated_doc.get('name', 'Unknown'),
            email=updated_doc.get('email', ''),
            role=updated_doc.get('role'),
            team=updated_doc.get('team'),
            github_username=updated_doc.get('github_username'),
            slack_id=updated_doc.get('slack_id'),
            notion_id=updated_doc.get('notion_id'),
            eoa_address=updated_doc.get('eoa_address'),
            recording_name=updated_doc.get('recording_name'),
            projects=updated_doc.get('projects', []),
            is_active=True,
            resigned_at=None,
            resignation_reason=None
        )
        
        return MemberUpdateResult(
            success=True,
            message=f"Member '{doc['name']}' has been reactivated",
            member=member
        )

