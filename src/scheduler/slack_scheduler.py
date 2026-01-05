import os
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from motor.motor_asyncio import AsyncIOMotorClient
from src.utils.logger import get_logger
from backend.api.v1.mcp_agent import run_mcp_agent, AgentRequest
import httpx

logger = get_logger(__name__)

class SlackScheduler:
    def __init__(self, mongo_manager):
        self.mongo_manager = mongo_manager
        self.scheduler = AsyncIOScheduler()
        self.db = mongo_manager.async_db
        self.collection = self.db["slack_schedules"]
        self.bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.post_message_url = "https://slack.com/api/chat.postMessage"

    async def start(self):
        """Start the scheduler and load existing jobs."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("⏰ Slack Scheduler started.")
            await self.load_all_jobs()

    async def load_all_jobs(self):
        """Load all active schedules from MongoDB and add them to the scheduler."""
        cursor = self.collection.find({"is_active": True})
        schedules = await cursor.to_list(length=1000)
        
        for schedule in schedules:
            self.add_job_to_scheduler(schedule)
        
        logger.info(f"✅ Loaded {len(schedules)} active schedules.")

    def add_job_to_scheduler(self, schedule):
        """Add a single job to APScheduler."""
        job_id = str(schedule["_id"])
        
        # Check if job already exists
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            self.execute_scheduled_task,
            CronTrigger.from_crontab(schedule["cron_expression"]),
            args=[schedule],
            id=job_id,
            replace_existing=True
        )

    async def execute_scheduled_task(self, schedule):
        """Execute the scheduled task (fetch data/AI answer and send to Slack)."""
        logger.info(f"🚀 Executing scheduled task: {schedule.get('name', 'Unnamed')} ({schedule['_id']})")
        
        channel_id = schedule["channel_id"]
        content_type = schedule.get("content_type", "custom_prompt")
        prompt = schedule.get("prompt", "Summarize today's activities.")
        
        if content_type == "daily_analysis":
            # Predefined prompt for daily analysis
            prompt = "Provide a comprehensive daily analysis of team activities across GitHub and Slack for the last 24 hours."

        try:
            # 1. Call AI Agent
            agent_req = AgentRequest(
                messages=[{"role": "user", "content": prompt}],
                model=schedule.get("model", "gpt-oss:120b")
            )
            
            result = await run_mcp_agent(agent_req)
            answer = result.get("answer", "Error generating response.")

            # 2. Send to Slack
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json"
                }
                resp = await client.post(
                    self.post_message_url,
                    json={
                        "channel": channel_id,
                        "text": f"📅 *[Scheduled Report]*\n\n{answer}",
                        "mrkdwn": True
                    },
                    headers=headers
                )
                
                if resp.status_code != 200 or not resp.json().get("ok"):
                    logger.error(f"Failed to send scheduled message to Slack: {resp.text}")
                else:
                    logger.info(f"✅ Scheduled message sent to {channel_id}")

        except Exception as e:
            logger.error(f"Error executing scheduled task {schedule['_id']}: {e}")

    async def add_schedule(self, schedule_data):
        """Add a new schedule to DB and scheduler."""
        schedule_data["is_active"] = True
        schedule_data["created_at"] = datetime.utcnow()
        
        result = await self.collection.insert_one(schedule_data)
        schedule_data["_id"] = result.inserted_id
        
        self.add_job_to_scheduler(schedule_data)
        return str(result.inserted_id)

    async def update_schedule(self, schedule_id, update_data):
        """Update an existing schedule."""
        from bson import ObjectId
        await self.collection.update_one(
            {"_id": ObjectId(schedule_id)},
            {"$set": {**update_data, "updated_at": datetime.utcnow()}}
        )
        
        updated_schedule = await self.collection.find_one({"_id": ObjectId(schedule_id)})
        if updated_schedule["is_active"]:
            self.add_job_to_scheduler(updated_schedule)
        else:
            if self.scheduler.get_job(schedule_id):
                self.scheduler.remove_job(schedule_id)
        
        return True

    async def delete_schedule(self, schedule_id):
        """Delete a schedule."""
        from bson import ObjectId
        await self.collection.delete_one({"_id": ObjectId(schedule_id)})
        if self.scheduler.get_job(schedule_id):
            self.scheduler.remove_job(schedule_id)
        return True

    async def get_user_schedules(self, user_id):
        """Get all schedules for a specific user."""
        cursor = self.collection.find({"member_id": user_id})
        return await cursor.to_list(length=100)

