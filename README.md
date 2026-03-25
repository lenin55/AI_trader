# 📈 AI Trader

## 📌 What is this application for?
This is a **conservative, fully automated AI trading bot** designed for the Indian Stock Market (NSE). 
It actively prioritizes **capital preservation**. Instead of relying purely on technical indicators, it reads the latest Indian financial news every morning, uses an AI (Google Gemini) to determine if there is an *overwhelmingly positive* macroeconomic or sector-specific catalyst, and if so, places a safe CNC (cash-and-carry) delivery order for a highly liquid blue-chip stock within an allowed "Liquid Universe."

If the news is mixed, uncertain, or the AI detects global economic fears, it triggers a `NO_TRADE` safety net.

## 🔑 Required APIs

1. **Google Gemini API (Execution Logic & Parsing)**  
   * **Cost**: Free Tier via Google AI Studio (Using the `gemini-2.5-flash` model).
   * **Purpose**: This is the brain of the bot. It reads the raw news data, evaluates the sentiment, strictly adheres to the conservative prompt, and outputs a JSON decision (`BUY` or `NO_TRADE` + reasoning). 

2. **NewsData.io API (Information Source)**
   * **Cost**: Free Tier (200 requests/day).
   * **Purpose**: Fetches the 10-15 latest business/economic news articles specific to the Indian market for the AI to analyze.

3. **Zerodha Kite Connect (Live Order Execution)**
   * **Cost**: ₹2000 / month (Paid to Zerodha).
   * **Purpose**: Used *only* if `LIVE_MODE=True` in your `.env` file. It places the actual trades on your Zerodha account. If this key is missing or you are in paper-trading mode, the bot gracefully relies on fake ₹1,000 asset prices and simulates the outcomes instead.

---

## 🚀 How to Run the Application

The application actually consists of two parts running simultaneously in separate terminal windows:
1. **The Scheduler (`main.py`)**: The brain that waits for 9:00 AM every weekday to execute the trading logic.
2. **The Dashboard (`dashboard.py`)**: The web UI to monitor the bot's logs.

### 🍎 Mac / Linux Commands

1. **Activate the Virtual Environment**:
   ```bash
   source venv/bin/activate
   ```
2. **Start the Web Dashboard**:
   ```bash
   streamlit run dashboard.py
   ```
3. **Start the Trading Bot Scheduler** (Open a new terminal tab and activate the `venv` first!):
   ```bash
   python main.py
   ```
   *(To force it to run immediately for testing instead of waiting for 9:00 AM, add the `--now` flag: `python main.py --now`)*

### 🪟 Windows Commands

1. **Activate the Virtual Environment**:
   ```cmd
   venv\Scripts\activate
   ```
2. **Start the Web Dashboard**:
   ```cmd
   streamlit run dashboard.py
   ```
3. **Start the Trading Bot Scheduler** (Open a new terminal tab and activate the `venv` first!):
   ```cmd
   python main.py
   ```
   *(To test immediately: `python main.py --now`)*

---

## 🌍 Deployment & Hosting (Zerodha rules)

When you are ready to move from Paper Trading to betting real money, you cannot reliably run this from your home laptop. This is because **Zerodha's Kite Connect strictly requires your server's IP address to be whitelisted** in their developer portal to prevent unauthorized access. Home networks use "Dynamic IPs" that change constantly, which will break the bot.

**Here is the standard deployment process:**
1. **Rent a VPS (Virtual Private Server)**: Rent a cheap, reliable Linux server with a **Static IP address** from providers like DigitalOcean, AWS (EC2), or Linode. *Choose a data center in Mumbai (India) for the lowest latency execution times to the NSE exchange.*
2. **Whitelist the IP**: Copy the public IPv4 address of your new VPS. Go to your Zerodha Kite Connect dashboard and paste it into the "Whitelist IP" section of your active API app.
3. **Upload & Run 24/7**: 
   - SSH into the server and upload this project code.
   - Install dependencies (`pip install -r requirements.txt`).
   - Fill out the `.env` file with your real Keys (and set `LIVE_MODE=True`).
   - Run the bot in the background infinitely. Instead of just running `python main.py` (which will crash if you close your laptop), you'll want to use a tool like `tmux`, `screen`, or `PM2` to keep the process alive forever on the server.

---

## 📈 Dynamic Sizing & Expected Yields

This bot is designed to be **fully dynamic** based on your invested capital. By default, it simulates with a base capital of ₹50,000, but you can scale this entirely by adding/changing a single line in your `.env` file:
```env
TOTAL_CAPITAL=100000  # Sets capital to ₹1 Lakh
```

### How Sizing Scales Automatically
- **Risk Management**: The bot is hardcoded to never risk more than **0.5% of your total capital** on a single trade. If you increase capital to ₹1 Lakh, your max risk per trade automatically scales from ₹250 to ₹500.
- **Stock Selection**: Because risk scales proportionally, you don't need to change any logic when adding money. The bot calculates how many shares it is legally allowed to buy while honoring that 0.5% cap at an assumed 5% stop-loss distance.

### Estimated Realistic Yields (Selling Point)
*Note: The stock market is never guaranteed, and macroeconomic environments naturally fluctuate.*
- **Strategy Type**: Highly conservative, long-bias news breakout strategy. It does not trade every day (only acts when overwhelming catalysts appear, hence "Capital Preservation").
- **Target Win/Loss Ratio**: By taking strictly validated, blue-chip delivery trades with a tight 5% assumed protective logic, the underlying goal is to catch 10-15% multi-week momentum swings. 
- **Conservative Annual Returns**: An automated, unleveraged delivery strategy like this realistically aims for **12-18% Annually**, outperforming fixed deposits passively, while drastically mitigating the catastrophic drawdown risks associated with aggressive Intraday/Options bots.
- **Scaling Estimates**:
  - **₹50,000 Capital**: Expect ~₹6,000 - ₹9,000 annual profit.
  - **₹5,00,000 Capital (5 Lakhs)**: Expect ~₹60,000 - ₹90,000 annual profit.
