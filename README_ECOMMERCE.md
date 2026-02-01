# E-commerce Voice Agent (Converted from FoodJoint)

A voice-powered e-commerce customer support assistant built with Google's Gemini Live audio API. Uses Cache-Augmented Generation (CAG) architecture for instant policy responses.

## Features

- **Voice Customer Support** - Natural conversation with real-time speech recognition
- **CAG Architecture** - Company policies embedded in context for zero-latency policy queries
- **Modern UI** - Clean, responsive web interface (inherited from FoodJoint)
- **Product Search** - Search by name or category with fuzzy matching
- **Order Management** - Track orders, cancel orders (policy-aware), initiate returns
- **FAQ Support** - Search across 750+ product FAQs
- **13 Specialized Tools** - Product search, order tracking, cancellations, returns

## Dataset

- **125 Products** across 5 categories (Electronics, Clothing, Home & Kitchen, Beauty & Personal Care, Sports & Fitness)
- **100 Orders** with various statuses
- **750+ FAQs** (6 per product)
- **Company Policies** (return, refund, cancellation - embedded in CAG)

## Quick Start

### 1. Install Dependencies

```bash
cd FoodJoint
pip install -r requirements.txt
```

### 2. Configure Environment

The `.env` file should already be configured with your Gemini API key from the FoodJoint setup.

If not, edit `.env`:

```env
GEMINI_API_KEY=your_api_key_here
```

### 3. Run the Voice Agent

```bash
uvicorn foodjoint_agent.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

## How It Works

1. **User speaks** → Audio captured at 16kHz PCM
2. **WebSocket** → Audio streamed to server (same as FoodJoint)
3. **Gemini Live** → Real-time speech-to-text + response generation (same as FoodJoint)
4. **CAG** → Policy queries answered instantly from embedded context
5. **Tools** → Product/order operations executed via function calls
6. **Response** → Audio played back at 24kHz (same as FoodJoint)

## Customer Support Tools

| Tool | Description |
|------|-------------|
| `search_products_by_name` | Fuzzy search products by name |
| `search_products_by_category` | Search by category with price filters |
| `get_product_details` | Get detailed product information |
| `check_product_availability` | Check stock availability |
| `get_product_faqs` | Get product-specific FAQs |
| `track_order` | Track order by Order ID |
| `get_customer_orders` | Get customer's recent orders |
| `get_order_details` | Get detailed order information |
| `cancel_order` | Cancel order (policy-aware) |
| `initiate_return` | Initiate product return (policy-aware) |
| `search_faqs` | Search across all FAQs |
| `get_all_categories` | List product categories |

## Example Queries

### Product Search
- "Show me laptops under $500"
- "I'm looking for running shoes"
- "Do you have any smartphones?"

### Product Information
- "Tell me about product P1001"
- "What's the price of the Dell laptop?"
- "Is this product in stock?"

### Order Tracking
- "Where is my order O0001?"
- "Track order O0050"
- "Show me my recent orders for customer C0001"

### Order Management
- "I want to cancel order O0001"
- "Can I return product P1001 from my order?"
- "What's your return policy?"

## Tech Stack

- **Backend**: FastAPI, Uvicorn, SQLite (same as FoodJoint)
- **AI**: Google Gemini Live (native audio) (same as FoodJoint)
- **Frontend**: HTML5, CSS3, JavaScript (inherited from FoodJoint)
- **Audio**: Web Audio API, PCM 16-bit (same as FoodJoint)
- **Search**: Rapidfuzz for fuzzy matching
- **Database**: SQLite with indexed queries

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (required) | Your Google Gemini API key |
| `GEMINI_LIVE_MODEL` | `gemini-2.5-flash-native-audio-preview-09-2025` | Gemini model |
| `GEMINI_LIVE_VOICE` | `Kore` | Voice preset |
| `GEMINI_LIVE_USE_CLIENT_VAD` | `false` | Use client-side voice detection |

## Architecture Highlights

**What Changed from FoodJoint:**
- ✅ Replaced menu management with product catalog (125 products)
- ✅ Replaced cart operations with customer support tools
- ✅ Replaced menu CAG with policy CAG (return/refund policies)
- ✅ Added fuzzy search for products
- ✅ Added order tracking and management
- ✅ Added FAQ search functionality

**What Stayed the Same (Working Components):**
- ✅ WebSocket infrastructure
- ✅ Gemini Live API integration
- ✅ Audio streaming (16kHz input, 24kHz output)
- ✅ Filler audio generation
- ✅ Concurrent tool execution
- ✅ Session management structure
- ✅ Web UI and frontend

## License

MIT (inherited from FoodJoint)
