import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from motor.motor_asyncio import AsyncIOMotorClient
from src.utils.logger import get_logger
from backend.api.v1.mcp_agent import run_mcp_agent, AgentRequest
import httpx

logger = get_logger(__name__)
KST = ZoneInfo("Asia/Seoul")


class SlackScheduler:
    def __init__(self, mongo_manager):
        self.mongo_manager = mongo_manager
        self.scheduler = AsyncIOScheduler(timezone=KST)
        self.db = mongo_manager.async_db
        self.collection = self.db["slack_schedules"]
        self.bot_token = os.getenv("SLACK_CHATBOT_TOKEN")
        self.post_message_url = "https://slack.com/api/chat.postMessage"

    async def start(self):
        """Start the scheduler and load existing jobs."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("⏰ Slack Scheduler started.")
            if not self.bot_token:
                logger.warning("⚠️ SLACK_CHATBOT_TOKEN not configured! Scheduled messages will fail.")
            else:
                logger.info(f"🔑 Slack bot token loaded: {self.bot_token[:10]}...{self.bot_token[-4:]}")
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
        schedule_name = schedule.get("name", "Unnamed")

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        schedule_tz = schedule.get("timezone", "Asia/Seoul")
        tz = ZoneInfo(schedule_tz)

        job = self.scheduler.add_job(
            self.execute_scheduled_task,
            CronTrigger.from_crontab(schedule["cron_expression"], timezone=tz),
            args=[schedule],
            id=job_id,
            replace_existing=True,
        )

        next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z") if job.next_run_time else "N/A"
        logger.info(f"📅 Job added: '{schedule_name}' (cron: {schedule['cron_expression']}, tz: {schedule_tz}, next: {next_run})")

    async def execute_scheduled_task(self, schedule):
        """Execute the scheduled task (fetch data/AI answer and send to Slack)."""
        logger.info(
            f"🚀 Executing scheduled task: {schedule.get('name', 'Unnamed')} ({schedule['_id']})"
        )

        channel_id = schedule["channel_id"]
        content_type = schedule.get("content_type", "custom_prompt")
        prompt = schedule.get("prompt", "Summarize today's activities.")

        try:
            if content_type == "daily_analysis":
                # Fetch stored daily analysis from gemini.recordings_daily
                answer = await self._fetch_stored_daily_analysis()
            else:
                # Custom prompt: Call AI Agent
                agent_req = AgentRequest(
                    messages=[{"role": "user", "content": prompt}],
                    model=schedule.get("model", "qwen3-235b"),
                )

                result = await run_mcp_agent(agent_req)
                answer = result.get("answer", "Error generating response.")

            # Send to Slack
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json",
                }
                resp = await client.post(
                    self.post_message_url,
                    json={
                        "channel": channel_id,
                        "text": f"📅 *[Scheduled Report]*\n\n{answer}",
                        "mrkdwn": True,
                    },
                    headers=headers,
                )

                if resp.status_code != 200 or not resp.json().get("ok"):
                    logger.error(
                        f"Failed to send scheduled message to Slack: {resp.text}"
                    )
                else:
                    logger.info(f"✅ Scheduled message sent to {channel_id}")

        except Exception as e:
            logger.error(f"Error executing scheduled task {schedule['_id']}: {e}")

    async def _fetch_stored_daily_analysis(self) -> str:
        """Fetch the most recent stored daily analysis from gemini.recordings_daily."""
        from pymongo import MongoClient

        # Get gemini database connection
        gemini_uri = os.getenv('GEMINI_MONGODB_URI')
        if not gemini_uri:
            gemini_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')

        client = MongoClient(gemini_uri)
        gemini_db = client["gemini"]

        try:
            # Get the most recent daily analysis (yesterday or today)
            now = datetime.now(KST)
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            today = now.strftime("%Y-%m-%d")

            # Try to get yesterday's analysis first, then today's
            doc = gemini_db["recordings_daily"].find_one(
                {"target_date": {"$in": [yesterday, today]}},
                sort=[("target_date", -1)]
            )

            if not doc:
                return "📊 *Daily Analysis*\n\n데이터가 없습니다. 해당 날짜의 분석 데이터가 아직 생성되지 않았습니다."

            # Format the analysis for Slack
            analysis = doc.get("analysis", {})
            target_date = doc.get("target_date", "")
            meeting_count = doc.get("meeting_count", 0)
            meeting_titles = doc.get("meeting_titles", [])
            total_meeting_time = doc.get("total_meeting_time", "")

            # Build the formatted message
            formatted = f"📊 *Daily Analysis - {target_date}*\n\n"
            formatted += f"*📅 미팅 수:* {meeting_count}개\n"
            if total_meeting_time:
                formatted += f"*⏱️ 총 미팅 시간:* {total_meeting_time}\n"

            if meeting_titles:
                formatted += f"\n*📝 미팅 목록:*\n"
                for title in meeting_titles[:10]:  # Limit to 10 meetings
                    formatted += f"• {title}\n"
                if len(meeting_titles) > 10:
                    formatted += f"_...외 {len(meeting_titles) - 10}개_\n"

            # Add the full analysis text
            full_analysis = analysis.get("full_analysis_text", "")
            if full_analysis:
                formatted += f"\n{full_analysis}"
            else:
                # Fallback to summary if no full analysis
                summary = analysis.get("summary", "")
                if summary:
                    formatted += f"\n*요약:*\n{summary}"

            return formatted

        except Exception as e:
            logger.error(f"Error fetching stored daily analysis: {e}")
            return f"📊 *Daily Analysis*\n\n분석 데이터를 가져오는 중 오류가 발생했습니다: {str(e)}"
        finally:
            client.close()

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
            {"$set": {**update_data, "updated_at": datetime.utcnow()}},
        )

        updated_schedule = await self.collection.find_one(
            {"_id": ObjectId(schedule_id)}
        )
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
