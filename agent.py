import logging

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
    get_job_context,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents import llm, stt, tts, inference 
from livekit.agents import AgentStateChangedEvent, MetricsCollectedEvent, metrics
from livekit.agents import RunContext, function_tool, ToolError
import aiohttp
from livekit.agents.beta.workflow import TaskGroup
from livekit.agents import mcp
from livekit.agents import AgentTask

logger = logging.getLogger(__name__)    

load_dotenv()

class CollectConsent(AgentTask[bool]):
    def __init__(self, chat_ctx=None):
        super().__init__(
            instructions="""
            Ask for recording consent and get a clear yes or no answer.
            Be polite and professional.
            """,
            chat_ctx=chat_ctx,
        )
    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions="""
            Briefly introduce yourself, then ask for permission to record the call for quality assurance and training purposes.
            Make it clear that they can decline.
            """
        )
    @function_tool
    async def consent_given(self) -> None:
        """Use this when the user gives consent to record."""
        self.complete(True)

    @function_tool
    async def consent_denied(self) -> None:
        """Use this when the user denies consent to record."""
        self.complete(False)


class Manager(Agent):
    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You are a manager for a team of helpful voice AI assistants. "
                "Handle escalations professionally."
            ),
            tts="inworld/inworld-tts-1",

            # Use session TTS (FallbackAdapter). Per-model voice IDs must exist on Inference;
            # e.g. `inworld/inworld-tts-1:ashley` caused NOT_FOUND for voice "ashley".
            chat_ctx=chat_ctx,
        )

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=("""you are a friendly customer service representative. Help customers with general inquiries. If they ask for manager or you cant reolve their issue, use the escalate_to_manager tool.""")
        )
    
    @function_tool()
    async def escalate_to_manager(self, context: RunContext):
        """Escalate the call to a manager on user request."""
        return Manager(chat_ctx=self.chat_ctx), "Escalating you to my manager now."


    async def on_enter(self) -> None:
        if await CollectConsent(chat_ctx=self.chat_ctx):
            await self.session.generate_reply(instructions="Offer your assistance to the user.")
        else:
            await self.session.generate_reply(instructions="Inform the user that you are unable to proceed and will end the call.")
            get_job_context().shutdown(reason="user denied recording consent")
    


async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=stt.FallbackAdapter([
            inference.STT.from_model_string("assemblyai/universal-streaming:en"),
            inference.STT.from_model_string("deepgram/nova-3"),
        ]),
        llm=llm.FallbackAdapter([
            inference.LLM.from_model_string("openai/gpt-4.1-mini"),
            inference.LLM.from_model_string("google/gemini-2.5-flash"),
        ]),
        tts=tts.FallbackAdapter([
            inference.TTS.from_model_string("cartesia/sonic-2:a167e0f3-df7e-4d52-a9c3-f949145efdab"),
            inference.TTS.from_model_string("inworld/inworld-tts-1"),
        ]),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
        preemptive_generation=True,
        mcp_servers=[
            # LiveKit Docs MCP: https://docs.livekit.io/reference/developer-tools/docs-mcp.md
            # URL path /mcp implies streamable HTTP; explicit + longer timeouts avoid flaky init.
            mcp.MCPServerHTTP(
                url="https://docs.livekit.io/mcp",
                transport_type="streamable_http",
                timeout=30.0,
                client_session_timeout_seconds=60.0,
            ),
        ],
    )

    await ctx.connect()
    
    #This captures per-turn statistics and logs a summary when the worker shuts down.
    usage_collector = metrics.UsageCollector()
    last_eou_metrics: metrics.EOUMetrics | None = None

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        nonlocal last_eou_metrics
        if ev.metrics.type == "eou_metrics":
            last_eou_metrics = ev.metrics
            metrics.log_metrics(ev.metrics)
            usage_collector.collect(ev.metrics)

    #Tracking time to first audio
    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent):
        if (
            ev.new_state == "speaking"
            and last_eou_metrics
            and session.current_speech
            and last_eou_metrics.speech_id == session.current_speech.id
        ):
            # EOUMetrics.timestamp is when EOU metrics were recorded (SDK removed last_speaking_time).
            delta_s = ev.created_at - last_eou_metrics.timestamp
            logger.info("Time to first audio frame: %.2fs", delta_s)

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
       # record=False, # Disable recording to save on storage costs
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))