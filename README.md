# FoodJoint Voice Agent

A voice-powered food ordering assistant built with Google's Gemini Live audio API. Uses Cache-Augmented Generation (CAG) architecture for instant menu responses.

## Features

- **Voice Ordering** - Natural conversation with real-time speech recognition
- **CAG Architecture** - Full menu embedded in context for zero-latency menu queries
- **Modern UI** - Clean, responsive web interface with green/blue theme
- **Order Management** - Complete cart operations (add, remove, update, confirm)
- **Analytics Dashboard** - Streamlit-based order tracking and insights

## Quick Start

### 1. Install Dependencies

```bash
cd FoodJointAgent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.sample .env
```

Edit `.env` and add your Gemini API key:

```env
GEMINI_API_KEY=your_api_key_here
```

### 3. Run the Voice Agent

```bash
uvicorn foodjoint_agent.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

### 4. View Orders

The orders dashboard is built into the app. After placing an order via voice, click **"View Orders"** in the UI or go to:

```
http://localhost:8000/orders
```

### 5. Run Streamlit Dashboard (Optional)

For more detailed analytics, you can also run the Streamlit dashboard:

```bash
streamlit run dashboard.py
```

## Project Structure

```
FoodJointAgent/
├── .env.sample              # Environment variables template
├── dashboard.py             # Streamlit order management dashboard
├── requirements.txt         # Python dependencies
├── README.md                # This file
│
├── database/
│   ├── food_menu.json       # Menu items (55 items)
│   └── orders.db            # SQLite database (auto-created)
│
└── foodjoint_agent/
    ├── __init__.py
    ├── main.py              # FastAPI server & WebSocket handler
    ├── prompts.py           # System prompts with embedded menu
    ├── cag_menu_builder.py  # Menu formatting for context
    ├── agent_tools.py       # Cart/order tool implementations
    ├── order_manager.py     # Shopping cart state management
    ├── menu_utils.py        # Menu validation
    ├── db_utils.py          # SQLite persistence
    │
    └── website/
        ├── templates/
        │   └── chat.html    # Voice ordering web UI
        └── static/
            └── main.js      # Audio capture & WebSocket client
```

## Menu Categories

| Category | Items | Price Range |
|----------|-------|-------------|
| Mains | Burgers, Sandwiches, Hot Dogs | $4.99 - $9.99 |
| Sides | Fries, Nuggets, Tenders, Rings | $2.49 - $7.99 |
| Drinks | Sodas, Shakes, Coffee, Tea | $1.79 - $4.49 |
| Desserts | Cookies, Pies, Ice Cream | $1.49 - $3.99 |
| Extras | Sauces, Toppings | $0.00 - $1.49 |
| Kids | Kids Meals | $4.99 - $5.99 |

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (required) | Your Google Gemini API key |
| `GEMINI_LIVE_MODEL` | `gemini-2.5-flash-native-audio-preview-09-2025` | Gemini model |
| `GEMINI_LIVE_VOICE` | `Kore` | Voice preset |
| `GEMINI_LIVE_USE_CLIENT_VAD` | `false` | Use client-side voice detection |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Voice ordering web interface |
| `/orders` | GET | Orders dashboard page |
| `/api/orders` | GET | Get all orders with stats (JSON) |
| `/api/orders/{id}` | GET | Get specific order details (JSON) |
| `/session` | WebSocket | Real-time audio/transcript stream |
| `/health` | GET | Health check |

## How It Works

1. **User speaks** → Audio captured at 16kHz PCM
2. **WebSocket** → Audio streamed to server
3. **Gemini Live** → Real-time speech-to-text + response generation
4. **CAG** → Menu queries answered instantly from embedded context
5. **Tools** → Cart operations executed via function calls
6. **Response** → Audio played back at 24kHz

## Agent Tools

| Tool | Description |
|------|-------------|
| `add_to_order` | Add items to cart |
| `remove_from_order` | Remove items from cart |
| `update_order_quantity` | Change item quantity |
| `update_order_item` | Modify item addons |
| `view_current_order` | Get cart summary |
| `confirm_and_save_order` | Finalize and save order |
| `clear_current_order` | Empty the cart |

## Dashboard Features

- **Overview** - Key metrics and recent orders
- **Search** - Find orders by ID or customer name
- **All Orders** - Table view with filtering
- **Analytics** - Sales trends and top items
- **Menu** - Browse and filter menu items

## Tech Stack

- **Backend**: FastAPI, Uvicorn, SQLite
- **AI**: Google Gemini Live (native audio)
- **Frontend**: HTML5, CSS3, JavaScript (vanilla)
- **Dashboard**: Streamlit, Pandas
- **Audio**: Web Audio API, PCM 16-bit

## License

MIT
