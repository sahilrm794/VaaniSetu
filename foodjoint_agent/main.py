"""
CAG-Based E-commerce Voice Agent

This is a Cache-Augmented Generation (CAG) implementation that embeds
company policies directly in the system prompt, eliminating policy query
tool calls and significantly reducing latency.

Key features:
- Policies pre-loaded into context at session start
- 13 customer support tools for products, orders, and FAQs
- No tool calls needed for policy questions
- Faster responses for policy-related questions
"""
import asyncio
import json
import logging
import math
import os
import random
from logging import getLogger
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google import genai
from google.genai import types

from . import agent_tools
from .managers.session_manager import SessionManager
from .prompts import SYSTEM_PROMPT, WELCOME_MESSAGE

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

# Use September 2025 version - the "latest" (December 2025) has function calling bugs
# See: https://discuss.ai.google.dev/t/114644
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash-native-audio-preview-09-2025"
GEMINI_DEFAULT_VOICE = "Kore"
INPUT_AUDIO_MIME = "audio/pcm;rate=16000"
FILLER_SAMPLE_RATE = 24000
FILLER_GAP_MIN_S = 0.5
FILLER_GAP_MAX_S = 1.2
FILLER_AUDIO_GUARD_S = 0.25
FILLER_MAX_PER_TURN = 3


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


app = FastAPI(title="E-commerce Voice Agent (CAG)")

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
website_files_path = Path(__file__).parent / "website"
app.mount("/static", StaticFiles(directory=website_files_path / "static"), name="static")
templates = Jinja2Templates(directory=website_files_path / "templates")


def _build_tool_declarations() -> list[dict[str, Any]]:
    """
    CAG TOOL DECLARATIONS - E-commerce customer support tools.

    Policy queries are REMOVED because policies are embedded in the system prompt.

    13 tools for product search, order tracking, FAQs, cancellations, and returns.

    IMPORTANT: Tool descriptions emphasize MANDATORY usage to help
    Gemini understand these must be called for data lookups.
    """
    return [
        # Product search tools
        {
            "name": "search_products_by_name",
            "description": "MANDATORY: Search for products by name using fuzzy matching. Call this when customer searches for a product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Product name or search term"},
                    "limit": {"type": "integer", "description": "Maximum number of results (default 5)", "default": 5},
                },
                "required": ["query"],
            },
        },
        {
            "name": "search_products_by_category",
            "description": "MANDATORY: Search products by category with optional price filtering. Use exact category names: Electronics, Clothing, Home & Kitchen, Beauty & Personal Care, Sports & Fitness.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Product category"},
                    "price_min": {"type": "number", "description": "Minimum price (optional)"},
                    "price_max": {"type": "number", "description": "Maximum price (optional)"},
                    "query": {"type": "string", "description": "Optional search term within category"},
                    "limit": {"type": "integer", "description": "Maximum results (default 10)", "default": 10},
                },
                "required": ["category"],
            },
        },
        {
            "name": "get_product_details",
            "description": "MANDATORY: Get detailed information about a specific product. Call this when customer asks about a product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Product ID (e.g., P1001)"},
                },
                "required": ["product_id"],
            },
        },
        {
            "name": "check_product_availability",
            "description": "MANDATORY: Check if a product is in stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Product ID"},
                },
                "required": ["product_id"],
            },
        },
        {
            "name": "get_product_faqs",
            "description": "MANDATORY: Get frequently asked questions for a specific product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Product ID"},
                },
                "required": ["product_id"],
            },
        },
        # Order tracking tools
        {
            "name": "track_order",
            "description": "MANDATORY: Track an order by Order ID. Call this when customer asks about order status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID (e.g., O0001)"},
                },
                "required": ["order_id"],
            },
        },
        {
            "name": "get_customer_orders",
            "description": "MANDATORY: Get recent orders for a customer by Customer ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer ID (e.g., C0001)"},
                    "limit": {"type": "integer", "description": "Number of recent orders (default 5)", "default": 5},
                },
                "required": ["customer_id"],
            },
        },
        {
            "name": "get_order_details",
            "description": "MANDATORY: Get detailed information about an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID"},
                },
                "required": ["order_id"],
            },
        },
        # Order management tools
        {
            "name": "cancel_order",
            "description": "MANDATORY: Cancel an order (policy-aware). The tool checks if cancellation is allowed based on order status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID to cancel"},
                    "reason": {"type": "string", "description": "Reason for cancellation"},
                },
                "required": ["order_id", "reason"],
            },
        },
        {
            "name": "initiate_return",
            "description": "MANDATORY: Initiate return for a product (policy-aware). The tool checks return eligibility and window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID"},
                    "product_id": {"type": "string", "description": "Product ID to return"},
                    "reason": {"type": "string", "description": "Reason for return"},
                },
                "required": ["order_id", "product_id", "reason"],
            },
        },
        # FAQ search tool
        {
            "name": "search_faqs",
            "description": "MANDATORY: Search across all product FAQs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Maximum results (default 5)", "default": 5},
                },
                "required": ["query"],
            },
        },
        # Utility tool
        {
            "name": "get_all_categories",
            "description": "Get list of all available product categories.",
            "parameters": {"type": "object", "properties": {}},
        },
    ]


def _synthesize_filler_clip(duration_ms: int, frequency: float, amplitude: float = 0.12) -> bytes:
    """Generate a short voiced hum for filler audio."""
    sample_rate = FILLER_SAMPLE_RATE
    total_samples = max(1, int(sample_rate * duration_ms / 1000))
    taper_samples = min(total_samples // 2, max(1, int(sample_rate * 0.03)))
    buf = bytearray()
    for i in range(total_samples):
        env = 1.0
        if i < taper_samples:
            env *= i / taper_samples
        if i > total_samples - taper_samples:
            env *= (total_samples - i) / taper_samples
        sample = math.sin(2 * math.pi * frequency * i / sample_rate)
        value = int(sample * amplitude * env * 32767)
        value = max(-32767, min(32767, value))
        buf.extend(value.to_bytes(2, "little", signed=True))
    return bytes(buf)


def _build_filler_clips() -> list[bytes]:
    """Precompute filler audio clips."""
    return [
        _synthesize_filler_clip(320, 190.0, 0.12),
        _synthesize_filler_clip(420, 150.0, 0.1),
        _synthesize_filler_clip(260, 230.0, 0.09),
    ]


FILLER_CLIPS = _build_filler_clips()


def _build_live_config(voice_name: Optional[str], use_client_vad: bool) -> dict[str, Any]:
    """Build Gemini Live configuration with CAG system prompt."""
    system_instruction = (
        SYSTEM_PROMPT
        + "\n\nStart every new session with this welcome line: "
        + WELCOME_MESSAGE
    )

    realtime_input_config: dict[str, Any] = {}
    if use_client_vad:
        realtime_input_config["automatic_activity_detection"] = {"disabled": True}
    else:
        realtime_input_config["automatic_activity_detection"] = {
            "disabled": False,
            "silence_duration_ms": 200,
        }

    tool_declarations = _build_tool_declarations()

    config: dict[str, Any] = {
        "response_modalities": ["AUDIO"],
        "system_instruction": system_instruction,
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "realtime_input_config": realtime_input_config,
        "tools": [{"function_declarations": tool_declarations}],
        # Thoughts made the model narrate adds without actually calling tools on multi-item requests.
        # Disable them to keep the model on the cart/order tool path.
        "thinking_config": {"include_thoughts": False},
    }
    if voice_name:
        config["speech_config"] = {
            "voice_config": {"prebuilt_voice_config": {"voice_name": voice_name}}
        }
    return config


def _coerce_args(raw_args: Any) -> dict[str, Any]:
    """Convert tool arguments to dict."""
    if raw_args is None:
        return {}
    if isinstance(raw_args, dict):
        return raw_args
    if hasattr(raw_args, "to_dict"):
        return raw_args.to_dict()
    if isinstance(raw_args, str):
        try:
            return json.loads(raw_args)
        except json.JSONDecodeError:
            return {}
    return {}


# =============================================================================
# CONCURRENT TOOL EXECUTION
# =============================================================================

# Tools that modify order state - require lock for safety
STATE_MODIFYING_TOOLS = {
    "cancel_order",
    "initiate_return",
}

# Read-only tools - can run concurrently without lock
READ_ONLY_TOOLS = {
    "search_products_by_name",
    "search_products_by_category",
    "get_product_details",
    "check_product_availability",
    "get_product_faqs",
    "track_order",
    "get_customer_orders",
    "get_order_details",
    "search_faqs",
    "get_all_categories",
}


async def _execute_single_tool(
    call_id: str,
    call_name: str,
    args: dict[str, Any],
    handler: Any,
    logger: logging.Logger,
) -> tuple[str, str, str]:
    """
    Execute a single tool call.

    For ecommerce tools, database handles concurrency through SQLite's built-in locking,
    so we don't need application-level locks for state-modifying operations.

    Returns: (call_id, call_name, result_string)
    """
    try:
        # Run sync handler in thread pool to not block event loop
        result = await asyncio.to_thread(handler, **args)

        logger.info(f"[CONCURRENT] Tool {call_name} completed: {str(result)[:100]}...")
        return (call_id, call_name, result)

    except Exception as exc:
        logger.exception(f"[CONCURRENT] Tool {call_name} failed")
        return (call_id, call_name, f"Tool {call_name} failed: {exc}")


async def _execute_tools_concurrently(
    function_calls: list,
    tool_handlers: dict[str, Any],
    logger: logging.Logger,
) -> list[types.FunctionResponse]:
    """
    Execute multiple tool calls concurrently using asyncio.gather.

    Strategy:
    - All tools run in parallel in thread pool
    - Database handles concurrency through SQLite's built-in locking

    Returns: List of FunctionResponse objects ready to send back to Gemini
    """
    if not function_calls:
        return []

    tasks = []
    unknown_responses = []

    for call in function_calls:
        args = _coerce_args(call.args)
        handler = tool_handlers.get(call.name)

        if handler is None:
            logger.warning(f"[CONCURRENT] Unknown tool call: {call.name}")
            unknown_responses.append(
                types.FunctionResponse(
                    id=call.id,
                    name=call.name,
                    response={"result": f"Unknown tool: {call.name}"},
                )
            )
            continue

        logger.info(f"[CONCURRENT] Queuing tool: {call.name} with args: {args}")

        task = _execute_single_tool(
            call_id=call.id,
            call_name=call.name,
            args=args,
            handler=handler,
            logger=logger,
        )
        tasks.append(task)

    # Execute all valid tool calls concurrently
    if tasks:
        logger.info(f"[CONCURRENT] Executing {len(tasks)} tool(s) concurrently...")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        function_responses = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"[CONCURRENT] Task raised exception: {result}")
                continue

            call_id, call_name, result_str = result
            function_responses.append(
                types.FunctionResponse(
                    id=call_id,
                    name=call_name,
                    response={"result": result_str},
                )
            )

        logger.info(f"[CONCURRENT] All {len(function_responses)} tool(s) completed")
        return unknown_responses + function_responses

    return unknown_responses


async def _send_json(websocket: WebSocket, payload: dict[str, Any]) -> None:
    """Send JSON payload to websocket."""
    await websocket.send_text(json.dumps(payload))


def _new_diag_state() -> dict[str, Any]:
    """Initialize diagnostic state for session."""
    now = asyncio.get_event_loop().time()
    return {
        "start_time": now,
        "last_client_audio": None,
        "last_gemini_response": None,
        "last_gemini_audio": None,
        "tool_inflight": False,
        "filler_task": None,
        "last_filler_sent": None,
        "filler_count": 0,
    }


def _maybe_start_filler_task(
    websocket: WebSocket, state: dict[str, Any], logger: logging.Logger
) -> None:
    """Start filler audio task if not already running."""
    existing = state.get("filler_task")
    if existing and not existing.done():
        return
    state["filler_task"] = asyncio.create_task(_filler_loop(websocket, state, logger))


async def _filler_loop(
    websocket: WebSocket, state: dict[str, Any], logger: logging.Logger
) -> None:
    """Send short hums while tools are running."""
    try:
        while state.get("tool_inflight"):
            now = asyncio.get_event_loop().time()
            last_audio = state.get("last_gemini_audio")
            if last_audio is not None and now - last_audio < FILLER_AUDIO_GUARD_S:
                await asyncio.sleep(0.1)
                continue
            last_sent = state.get("last_filler_sent")
            first_clip = state.get("filler_count", 0) == 0
            if not first_clip and last_sent is not None and now - last_sent < FILLER_GAP_MIN_S:
                await asyncio.sleep(0.05)
                continue
            if state.get("filler_count", 0) >= FILLER_MAX_PER_TURN:
                await asyncio.sleep(0.1)
                continue
            clip = random.choice(FILLER_CLIPS)
            try:
                await websocket.send_bytes(clip)
                state["last_filler_sent"] = now
                state["filler_count"] = state.get("filler_count", 0) + 1
            except Exception as exc:
                logger.error(f"[FILLER] Failed to send filler audio: {exc}")
                break
            await asyncio.sleep(random.uniform(FILLER_GAP_MIN_S, FILLER_GAP_MAX_S))
    finally:
        state["filler_task"] = None
        state["tool_inflight"] = False
        state["filler_count"] = 0


@app.get("/", response_class=HTMLResponse)
async def start_page(request: Request) -> HTMLResponse:
    port = request.url.port or (443 if request.url.scheme == "https" else 80)
    return templates.TemplateResponse("chat.html", {"request": request, "port": port})


@app.get("/start-chat/", response_class=HTMLResponse)
async def start_chat(request: Request) -> HTMLResponse:
    return await start_page(request)


@app.get("/health", response_class=JSONResponse)
async def healthcheck() -> JSONResponse:
    return JSONResponse({"status": "ok", "architecture": "CAG"})


@app.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request) -> HTMLResponse:
    """Orders dashboard page."""
    return templates.TemplateResponse("orders.html", {"request": request})


@app.get("/api/orders", response_class=JSONResponse)
async def api_get_orders() -> JSONResponse:
    """Get all orders with stats."""
    orders = get_all_orders(limit=100)
    total_orders = len(orders)
    total_revenue = sum(o.get("total_amount", 0) for o in orders)
    avg_order = total_revenue / total_orders if total_orders > 0 else 0

    return JSONResponse({
        "orders": orders,
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "avg_order": round(avg_order, 2),
    })


@app.get("/api/orders/{order_id}", response_class=JSONResponse)
async def api_get_order(order_id: str) -> JSONResponse:
    """Get a specific order by ID."""
    order = get_order(order_id)
    if not order:
        return JSONResponse({"error": "Order not found"}, status_code=404)
    return JSONResponse(order)


def _build_tool_handlers(session: SessionManager) -> dict[str, Any]:
    """
    Build tool handlers - CAG version with e-commerce customer support tools.

    Note: Policy tools are removed since policies are embedded in prompt.
    """
    return {
        # Product search tools
        "search_products_by_name": lambda query, limit=5: agent_tools.search_products_by_name(
            query, int(limit), session
        ),
        "search_products_by_category": lambda category, price_min=None, price_max=None, query=None, limit=10: agent_tools.search_products_by_category(
            category, price_min, price_max, query, int(limit), session
        ),
        "get_product_details": lambda product_id: agent_tools.get_product_details(
            product_id, session
        ),
        "check_product_availability": lambda product_id: agent_tools.check_product_availability(
            product_id
        ),
        "get_product_faqs": lambda product_id: agent_tools.get_product_faqs(
            product_id
        ),
        # Order tracking tools
        "track_order": lambda order_id: agent_tools.track_order(
            order_id, session
        ),
        "get_customer_orders": lambda customer_id, limit=5: agent_tools.get_customer_orders(
            customer_id, int(limit), session
        ),
        "get_order_details": lambda order_id: agent_tools.get_order_details(
            order_id, session
        ),
        # Order management tools
        "cancel_order": lambda order_id, reason: agent_tools.cancel_order(
            order_id, reason, session
        ),
        "initiate_return": lambda order_id, product_id, reason: agent_tools.initiate_return(
            order_id, product_id, reason, session
        ),
        # FAQ search tool
        "search_faqs": lambda query, limit=5: agent_tools.search_faqs(
            query, int(limit)
        ),
        # Utility tool
        "get_all_categories": lambda: agent_tools.get_all_categories(),
    }


async def _forward_client_audio(
    websocket: WebSocket,
    session: Any,
    logger: logging.Logger,
    use_client_vad: bool,
    state: dict[str, Any],
) -> None:
    """Forward audio from client to Gemini."""
    last_activity_time = asyncio.get_event_loop().time()

    while True:
        try:
            message = await asyncio.wait_for(websocket.receive(), timeout=10.0)
        except asyncio.TimeoutError:
            current_time = asyncio.get_event_loop().time()
            if current_time - last_activity_time > 30.0:
                try:
                    silence = bytes(1600)
                    await session.send_realtime_input(
                        audio=types.Blob(data=silence, mime_type=INPUT_AUDIO_MIME)
                    )
                    last_activity_time = current_time
                except Exception as exc:
                    logger.error(f"Keepalive failed: {exc}")
            continue

        if message.get("type") == "websocket.disconnect":
            raise WebSocketDisconnect

        audio_bytes = message.get("bytes")
        if audio_bytes:
            current_time = asyncio.get_event_loop().time()
            state["last_client_audio"] = current_time
            last_activity_time = current_time

            try:
                await session.send_realtime_input(
                    audio=types.Blob(data=audio_bytes, mime_type=INPUT_AUDIO_MIME)
                )
            except Exception as exc:
                logger.error(f"[GEMINI] Failed to send audio input: {exc}")
                break
            continue

        text_data = message.get("text")
        if not text_data:
            continue

        last_activity_time = asyncio.get_event_loop().time()

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            continue

        if payload.get("type") == "text":
            text = payload.get("text", "")
            if text:
                logger.info(f"Received text input: {text}")
                await session.send_client_content(
                    turns={"role": "user", "parts": [{"text": text}]},
                    turn_complete=True,
                )


async def _forward_gemini_responses(
    websocket: WebSocket,
    session: Any,
    tool_handlers: dict[str, Any],
    logger: logging.Logger,
    state: dict[str, Any],
) -> None:
    """
    Forward responses from Gemini to client.

    CONCURRENT TOOL EXECUTION: When Gemini sends multiple tool calls,
    they are executed concurrently using asyncio.gather for better performance.
    """
    last_event_debug: dict[str, Any] | None = None
    while True:
        try:
            async for response in session.receive():
                now = asyncio.get_event_loop().time()
                state["last_gemini_response"] = now

                last_event_debug = {
                    "has_data": response.data is not None,
                    "has_tool_call": bool(response.tool_call),
                    "has_server_content": bool(response.server_content),
                }

                if response.data is not None:
                    state["last_gemini_audio"] = now
                    await websocket.send_bytes(response.data)

                if response.server_content:
                    input_tx = response.server_content.input_transcription
                    if input_tx and input_tx.text:
                        logger.info(f"User said: {input_tx.text}")
                        await _send_json(
                            websocket,
                            {
                                "type": "transcript",
                                "role": "user",
                                "text": input_tx.text,
                                "final": True,
                            },
                        )

                    output_tx = response.server_content.output_transcription
                    if output_tx and output_tx.text:
                        logger.info(f"Assistant said: {output_tx.text}")
                        await _send_json(
                            websocket,
                            {
                                "type": "transcript",
                                "role": "assistant",
                                "text": output_tx.text,
                                "final": True,
                            },
                        )

                if response.tool_call:
                    num_calls = len(response.tool_call.function_calls)
                    logger.info(
                        "[Gemini] Tool calls incoming (%d call%s - CONCURRENT): %s",
                        num_calls,
                        "s" if num_calls > 1 else "",
                        [
                            {"id": call.id, "name": call.name, "args": _coerce_args(call.args)}
                            for call in response.tool_call.function_calls
                        ],
                    )
                    state["tool_inflight"] = True
                    state["filler_count"] = 0
                    state["last_filler_sent"] = None
                    _maybe_start_filler_task(websocket, state, logger)

                    # CONCURRENT EXECUTION: Execute all tool calls in parallel
                    function_responses = await _execute_tools_concurrently(
                        function_calls=response.tool_call.function_calls,
                        tool_handlers=tool_handlers,
                        logger=logger,
                    )

                    if function_responses:
                        try:
                            logger.info(
                                "[CONCURRENT] Sending %s function response(s): %s",
                                len(function_responses),
                                [
                                    {
                                        "id": fr.id,
                                        "name": fr.name,
                                        "result_preview": str(fr.response)[:200],
                                    }
                                    for fr in function_responses
                                ],
                            )
                            await session.send_tool_response(function_responses=function_responses)
                            logger.info("[CONCURRENT] Function responses delivered successfully")
                        except Exception as exc:
                            logger.exception(
                                "[CONCURRENT] Failed to send function responses to Gemini (model=%s): %s",
                                session._model if hasattr(session, "_model") else "unknown",
                                exc,
                            )
                        finally:
                            state["tool_inflight"] = False
                    else:
                        state["tool_inflight"] = False

        except Exception as exc:
            logger.error(
                "[GEMINI] Error in receive loop: %s | last_event=%s",
                exc,
                last_event_debug,
            )
            break


@app.websocket("/session")
async def handle_session(websocket: WebSocket) -> None:
    """Handle WebSocket session with CAG architecture."""
    await websocket.accept()

    logger = getLogger("ecommerce.cag.agent")
    logger.info("New CAG session started")

    # Initialize session manager
    import uuid
    session_id = str(uuid.uuid4())
    session = SessionManager(session_id=session_id)
    tool_handlers = _build_tool_handlers(session)

    model = os.getenv("GEMINI_LIVE_MODEL", GEMINI_DEFAULT_MODEL)
    voice = os.getenv("GEMINI_LIVE_VOICE", GEMINI_DEFAULT_VOICE)
    use_client_vad = _env_flag("GEMINI_LIVE_USE_CLIENT_VAD", default=False)

    logger.info(
        "CAG Architecture - Tools: %s (policies embedded in prompt) | model=%s voice=%s client_vad=%s",
        len(tool_handlers),
        model,
        voice,
        use_client_vad,
    )

    state = _new_diag_state()

    # Get API key from environment
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set in environment")
        await _send_json(websocket, {"type": "error", "message": "Server configuration error: API key not set"})
        return

    client = genai.Client(api_key=api_key)
    config = _build_live_config(voice, use_client_vad)

    try:
        async with client.aio.live.connect(model=model, config=config) as live_session:
            await _send_json(websocket, {"type": "status", "state": "ready"})

            # Trigger initial greeting
            await live_session.send_client_content(
                turns={"role": "user", "parts": [{"text": "hello"}]},
                turn_complete=True,
            )

            # Start bidirectional audio forwarding
            send_task = asyncio.create_task(
                _forward_client_audio(websocket, live_session, logger, use_client_vad, state)
            )
            receive_task = asyncio.create_task(
                _forward_gemini_responses(
                    websocket, live_session, tool_handlers, logger, state
                )
            )

            done, pending = await asyncio.wait(
                {send_task, receive_task},
                return_when=asyncio.FIRST_EXCEPTION,
            )

            for task in pending:
                task.cancel()

            filler_task = state.get("filler_task")
            if filler_task and not filler_task.done():
                filler_task.cancel()
                try:
                    await filler_task
                except asyncio.CancelledError:
                    pass

            for task in done:
                try:
                    task.result()
                except Exception as task_exc:
                    logger.exception(f"Task error: {task_exc}")

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception(f"Session error: {exc}")
        try:
            await _send_json(
                websocket,
                {"type": "error", "message": f"Session error: {str(exc)}. Please reconnect."},
            )
        except Exception:
            pass
    finally:
        logger.info("CAG session ended")
