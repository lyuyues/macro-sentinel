"""Generate a professional Options Trading Guide PDF with embedded charts."""
import os
from fpdf import FPDF

CHARTS_DIR = "output/options_guide_charts"
OUTPUT_PATH = "output/Options_Trading_Guide.pdf"


class OptionsPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 5, "Options Trading Guide", align="L")
            self.cell(0, 5, f"Page {self.page_no()}", align="R")
            self.ln(8)

    def chapter_title(self, title):
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(20, 60, 120)
        self.cell(0, 12, title, ln=True)
        self.set_draw_color(20, 60, 120)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def section_title(self, title):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(40, 40, 40)
        self.cell(0, 10, title, ln=True)
        self.ln(2)

    def sub_section(self, title):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(60, 60, 60)
        self.cell(0, 8, title, ln=True)
        self.ln(1)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bold_text(self, text):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.cell(0, 5.5, "  -  " + text)
        self.ln(5.5)

    def code_block(self, text):
        self.set_font("Courier", "", 9)
        self.set_fill_color(240, 240, 240)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        self.set_x(x + 5)
        for line in text.split("\n"):
            self.cell(180, 5, "  " + line, ln=True, fill=True)
        self.ln(3)

    def table(self, headers, rows, col_widths=None):
        if col_widths is None:
            col_widths = [190 / len(headers)] * len(headers)
        # Header
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(20, 60, 120)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
        self.ln()
        # Rows
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        fill = False
        for row in rows:
            if fill:
                self.set_fill_color(245, 245, 250)
            else:
                self.set_fill_color(255, 255, 255)
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 6, str(cell), border=1, fill=True, align="C")
            self.ln()
            fill = not fill
        self.ln(3)

    def add_chart(self, image_path, w=180):
        if os.path.exists(image_path):
            self.image(image_path, x=15, w=w)
            self.ln(5)

    def tip_box(self, text):
        self.set_fill_color(230, 245, 230)
        self.set_draw_color(60, 160, 60)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(30, 100, 30)
        y = self.get_y()
        self.rect(10, y, 190, 12, style="DF")
        self.set_xy(14, y + 1)
        self.multi_cell(182, 5, "TIP: " + text)
        self.ln(5)

    def warning_box(self, text):
        self.set_fill_color(255, 240, 240)
        self.set_draw_color(200, 60, 60)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(180, 30, 30)
        y = self.get_y()
        self.rect(10, y, 190, 12, style="DF")
        self.set_xy(14, y + 1)
        self.multi_cell(182, 5, "WARNING: " + text)
        self.ln(5)


def build_pdf():
    pdf = OptionsPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ═══════════════════════════════════════
    # COVER PAGE
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.ln(60)
    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(20, 60, 120)
    pdf.cell(0, 20, "Options Trading Guide", align="C", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, "A Practical Guide for Stock Investors", align="C", ln=True)
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Fidelity Options Tier 1  |  Cash-Secured Puts  |  Covered Calls  |  Wheel Strategy", align="C", ln=True)
    pdf.ln(30)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 8, "Generated: 2026-02-10", align="C", ln=True)

    # ═══════════════════════════════════════
    # TABLE OF CONTENTS
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("Table of Contents")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)
    toc = [
        ("Chapter 1", "The Nature of Options (Qi Quan De Ben Zhi)"),
        ("Chapter 2", "The Greeks (Xi La Zi Mu)"),
        ("Chapter 3", "Strategies You Can Use (Tier 1)"),
        ("Chapter 4", "Options Pricing Intuition"),
        ("Chapter 5", "Practical Execution Guide"),
        ("Chapter 6", "Risk Management"),
        ("Chapter 7", "Tax Implications (US)"),
        ("Chapter 8", "Pre-Trade Checklists"),
        ("Appendix A", "Payoff Diagrams"),
        ("Appendix B", "Common Abbreviations"),
    ]
    for ch, title in toc:
        pdf.cell(30, 8, ch)
        pdf.cell(0, 8, title, ln=True)
    pdf.ln(5)

    # ═══════════════════════════════════════
    # CHAPTER 1: NATURE OF OPTIONS
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("Chapter 1: The Nature of Options")

    pdf.section_title("1.1 Options in One Sentence")
    pdf.body_text(
        "An option is like insurance. You pay a fee (premium) to get the RIGHT to buy or sell "
        "a stock at an agreed price by a certain date."
    )

    pdf.section_title("1.2 The Four Basic Roles")
    pdf.table(
        ["", "Call (Bullish)", "Put (Bearish)"],
        [
            ["Buyer (Long)", "Pay premium, RIGHT to BUY", "Pay premium, RIGHT to SELL"],
            ["Seller (Short)", "Collect premium, OBLIGATION to SELL", "Collect premium, OBLIGATION to BUY"],
        ],
        [30, 80, 80],
    )
    pdf.bold_text("Key: Buyers have rights. Sellers have obligations.")

    pdf.section_title("1.3 Key Terms")
    pdf.table(
        ["Term", "Meaning", "Example"],
        [
            ["Strike Price", "Agreed buy/sell price", "AVGO $300 Put -> strike = $300"],
            ["Expiration", "Date option expires", "2026-03-21"],
            ["Premium", "Price of the option", "$5.00/share = $500/contract"],
            ["Contract", "1 contract = 100 shares", "Buy 1 call = control 100 shares"],
            ["ITM (In The Money)", "Option has intrinsic value", "$340 stock, $300 call = ITM"],
            ["ATM (At The Money)", "Strike ~ current price", "$340 stock, $340 strike"],
            ["OTM (Out of Money)", "No intrinsic value", "$340 stock, $380 call = OTM"],
        ],
        [35, 60, 95],
    )

    pdf.section_title("1.4 Option Price = Intrinsic Value + Time Value")
    pdf.body_text(
        "Intrinsic Value: How much profit if exercised NOW.\n"
        "  - Call: max(Stock Price - Strike, 0)\n"
        "  - Put: max(Strike - Stock Price, 0)\n\n"
        "Time Value: Premium for the POSSIBILITY of future movement. Decays over time."
    )
    pdf.body_text(
        "Example: AVGO at $340\n"
        "  $300 Call: Intrinsic = $40. If premium = $45, time value = $5\n"
        "  $300 Put: Intrinsic = $0 (OTM). If premium = $3, ALL time value"
    )

    # ═══════════════════════════════════════
    # CHAPTER 2: THE GREEKS
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("Chapter 2: The Greeks")
    pdf.body_text("Greeks measure how sensitive an option's price is to various factors. "
                  "You don't need to memorize formulas - just understand the intuition.")

    pdf.section_title("2.1 Delta - Direction Sensitivity")
    pdf.body_text("How much does the option price change when the stock moves $1?")
    pdf.table(
        ["Delta Value", "Meaning"],
        [
            ["Call: +0.50", "Stock up $1 -> option up $0.50"],
            ["Put: -0.30", "Stock up $1 -> option down $0.30"],
            ["Deep ITM: ~1.0", "Option moves nearly 1:1 with stock"],
            ["Deep OTM: ~0", "Stock movement barely affects option"],
        ],
        [50, 140],
    )
    pdf.tip_box("Delta ~ probability of expiring ITM. A put with delta -0.30 has ~30% chance of being assigned.")

    pdf.section_title("2.2 Theta - Time Decay")
    pdf.body_text(
        "How much value does the option lose each day?\n\n"
        "- Buyer's enemy, seller's friend\n"
        "- ATM options have the highest theta\n"
        "- Accelerates in the last 30 days\n"
        "- Example: Theta = -$0.15 -> option loses $0.15/day (all else equal)"
    )

    pdf.section_title("2.3 Vega - Volatility Sensitivity")
    pdf.body_text(
        "How much does the option price change when IV moves 1%?\n\n"
        "- High IV = expensive options (panic markets)\n"
        "- Low IV = cheap options\n"
        "- Sellers want high IV (collect more premium)\n"
        "- Buyers want low IV (pay less)"
    )
    pdf.warning_box("IV Crush: IV spikes before earnings, then collapses after. Don't buy options before earnings!")

    pdf.section_title("2.4 Gamma - Rate of Delta Change")
    pdf.body_text(
        "How fast does Delta change when the stock moves $1?\n"
        "ATM + near expiration = highest Gamma = most explosive price changes.\n"
        "Sellers fear high Gamma (sudden large moves)."
    )

    pdf.section_title("2.5 Greeks Quick Reference")
    pdf.code_block(
        "Want to profit from direction  -> look at Delta\n"
        "Want to profit from time       -> look at Theta (seller strategies)\n"
        "Want to profit from volatility -> look at Vega\n"
        "Control risk                   -> look at Gamma"
    )

    # ═══════════════════════════════════════
    # CHAPTER 3: STRATEGIES (TIER 1)
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("Chapter 3: Strategies You Can Use (Tier 1)")

    pdf.table(
        ["Strategy", "Type", "Risk Level"],
        [
            ["Buy Calls / Puts", "Buyer", "Medium (max loss = premium)"],
            ["Sell Covered Calls", "Seller", "Low"],
            ["Sell Cash-Secured Puts", "Seller", "Medium"],
            ["Long Straddle / Strangle", "Buyer", "Medium"],
        ],
        [60, 40, 90],
    )

    pdf.section_title("3.1 Sell Cash-Secured Put (CSP)")
    pdf.bold_text("Your AVGO scenario: Want to buy at $300, current price $340")
    pdf.body_text(
        "Action: Sell 1 AVGO $300 Put, 30-45 DTE\n"
        "You collect premium immediately (e.g. $3/share = $300)\n\n"
        "Two outcomes:\n"
        "  AVGO > $300 at expiry -> option expires worthless, you keep $300 premium\n"
        "  AVGO <= $300 at expiry -> assigned, buy 100 shares at $300 (effective cost ~$297)"
    )
    pdf.body_text(
        "How to choose contracts:\n"
        "  Expiration: 30-45 DTE (optimal theta decay)\n"
        "  Strike: Price you genuinely want to own the stock at\n"
        "  Delta: -0.15 to -0.30 (15-30% chance of assignment)\n"
        "  Collateral: Strike x 100 = $30,000 (cash or margin)"
    )
    pdf.warning_box("Only sell puts on stocks you truly want to own. If AVGO drops to $200, you still buy at $300.")

    pdf.section_title("3.2 Covered Call (CC)")
    pdf.body_text(
        "Prerequisite: Own 100+ shares of the stock\n\n"
        "Action: Own 100 shares of XYZ -> Sell 1 OTM Call\n\n"
        "Two outcomes:\n"
        "  Stock < strike at expiry -> keep shares + keep premium\n"
        "  Stock >= strike at expiry -> shares sold at strike + keep premium\n\n"
        "Risk: Miss out on upside if stock rockets past your strike.\n"
        "Best for: Stocks you think will stay flat or rise slowly."
    )

    pdf.section_title("3.3 Buy Call / Buy Put")
    pdf.body_text(
        "Buy Call: Pay premium for the right to buy. Max loss = premium. Unlimited upside.\n"
        "Buy Put: Pay premium for the right to sell. Max loss = premium. Profit when stock drops.\n\n"
        "Key risks:\n"
        "  - Theta eats your premium every day\n"
        "  - Even if you're right on direction, you can lose if the move is too slow\n"
        "  - Low win rate, high reward potential"
    )

    pdf.section_title("3.4 The Wheel Strategy")
    pdf.body_text(
        "The most suitable strategy for your investing style (long-term holder):\n\n"
        "Step 1: Sell OTM Put at your target buy price\n"
        "  -> Not assigned? Repeat, keep collecting premium\n"
        "  -> Assigned? You now own 100 shares at your target price\n\n"
        "Step 2: Sell OTM Covered Call on your shares\n"
        "  -> Not called away? Repeat, keep collecting premium\n"
        "  -> Called away? Shares sold at profit, go back to Step 1\n\n"
        "You earn premium at EVERY stage of the cycle."
    )

    # ═══════════════════════════════════════
    # CHAPTER 4: PRICING INTUITION
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("Chapter 4: Options Pricing Intuition")

    pdf.section_title("4.1 What Makes Options More Expensive?")
    pdf.table(
        ["Factor", "Call Price", "Put Price"],
        [
            ["Stock price UP", "Higher", "Lower"],
            ["Stock price DOWN", "Lower", "Higher"],
            ["Volatility UP (IV)", "Higher", "Higher"],
            ["More time to expiry", "Higher", "Higher"],
            ["Interest rates UP", "Slightly higher", "Slightly lower"],
        ],
        [60, 65, 65],
    )

    pdf.section_title("4.2 IV Rank and IV Percentile")
    pdf.body_text(
        "IV Rank: Where current IV sits in its 1-year range (0-100)\n\n"
        "  IV Rank > 50 -> IV is elevated -> good time to SELL options\n"
        "  IV Rank < 30 -> IV is low -> good time to BUY options\n"
    )

    pdf.section_title("4.3 Implied vs Historical Volatility")
    pdf.code_block(
        "Implied Volatility (IV):    Market's EXPECTATION of future volatility\n"
        "Historical Volatility (HV): Actual past volatility\n"
        "\n"
        "IV > HV -> Options are 'expensive' -> Seller advantage\n"
        "IV < HV -> Options are 'cheap'     -> Buyer advantage"
    )

    # Theta decay chart
    pdf.section_title("4.4 Theta Decay Curve")
    pdf.body_text("Time value erodes following a square-root curve - slowly at first, then rapidly in the last 30 days:")
    pdf.add_chart(os.path.join(CHARTS_DIR, "4_theta_decay.png"), w=170)
    pdf.tip_box("Sell options at 45 DTE to capture the steepest part of the decay curve.")

    # ═══════════════════════════════════════
    # CHAPTER 5: PRACTICAL EXECUTION
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("Chapter 5: Practical Execution Guide")

    pdf.section_title("5.1 Placing an Order on Fidelity")
    pdf.body_text(
        "1. Go to Trade -> Options\n"
        "2. Enter ticker (e.g. AVGO)\n"
        "3. Select Expiration Date (30-45 days out)\n"
        "4. Select Strike Price\n"
        "5. Select Action:\n"
        "     Buy to Open (BTO) = open a new long position\n"
        "     Sell to Open (STO) = open a new short position\n"
        "     Buy to Close (BTC) = close an existing short position\n"
        "     Sell to Close (STC) = close an existing long position\n"
        "6. Order Type: Limit (recommended)\n"
        "7. Price: midpoint between Bid and Ask\n"
        "8. Preview -> Submit"
    )

    pdf.section_title("5.2 Reading the Option Chain")
    pdf.code_block(
        "         CALLS                              PUTS\n"
        " Last  Bid   Ask   Vol    OI  | Strike | Last  Bid   Ask   Vol    OI\n"
        " 45.2  44.8  45.6  120  3400  |  $300  | 3.10  2.90  3.30   85  5200\n"
        " 35.0  34.5  35.5   80  2100  |  $310  | 5.40  5.10  5.70   60  3800"
    )
    pdf.body_text(
        "Bid: Price you get when selling\n"
        "Ask: Price you pay when buying\n"
        "Volume: Today's trades (higher = better)\n"
        "Open Interest (OI): Total open contracts (higher = more liquid)\n\n"
        "Rule: Choose contracts with OI > 500 and tight bid-ask spread (<10%)."
    )

    pdf.section_title("5.3 Your AVGO Put: Step by Step")
    pdf.code_block(
        "1. Trade -> Options -> AVGO\n"
        "2. Expiration: ~30-45 days (e.g. 2026-03-20)\n"
        "3. Strike: $300\n"
        "4. Action: Sell to Open\n"
        "5. Quantity: 1\n"
        "6. Order Type: Limit\n"
        "7. Price: Look at $300 put Bid (e.g. $3.00)\n"
        "8. Preview -> Confirm margin requirement -> Submit\n"
        "\n"
        "Result: Collect $300 ($3.00 x 100), then wait."
    )

    pdf.section_title("5.4 Close Early vs Hold to Expiration")
    pdf.table(
        ["Scenario", "Action", "Why"],
        [
            ["Premium dropped 50%+", "Buy to Close", "Lock in profit, reduce risk"],
            ["Stock crashing toward strike", "Buy to Close", "Cut loss, avoid assignment"],
            ["Near expiry, don't want shares", "Buy to Close", "Avoid being assigned"],
            ["Happy to own at strike", "Hold to expiry", "Get assigned, start step 2"],
        ],
        [55, 40, 95],
    )
    pdf.tip_box("Close at 50% profit. Don't risk the remaining premium for marginal gain.")

    # ═══════════════════════════════════════
    # CHAPTER 6: RISK MANAGEMENT
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("Chapter 6: Risk Management")

    pdf.section_title("6.1 Never Do These")
    pdf.body_text(
        "1. Sell Naked Calls - unlimited loss potential (you don't have Tier permission anyway)\n"
        "2. Go all-in on options - they can go to zero, only risk what you can lose entirely\n"
        "3. Buy options before earnings - IV Crush will destroy your position\n"
        "4. Trade illiquid options - OI < 100 means terrible fills and wide spreads\n"
        "5. Sell puts on stocks you don't want - never sell puts just for premium"
    )

    pdf.section_title("6.2 Position Sizing")
    pdf.code_block(
        "Rule: Single option trade risk <= 2-5% of account\n"
        "\n"
        "Your Y Account ~$63,000:\n"
        "  Max risk per trade: $1,260 - $3,150\n"
        "  Selling 1 AVGO $300 put: max risk ~$30,000 (extreme case)\n"
        "    -> 47% of account (high, but acceptable if you want to own AVGO)"
    )

    pdf.section_title("6.3 Managing Assignments")
    pdf.body_text(
        "When your put gets assigned:\n"
        "  - You now own 100 shares at the strike price\n"
        "  - Your cost basis = strike - premium collected\n"
        "  - Immediately sell a covered call to continue generating income\n"
        "  - Set a mental stop loss (e.g. sell if stock drops 20% below your cost)"
    )

    # ═══════════════════════════════════════
    # CHAPTER 7: TAX
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("Chapter 7: Tax Implications (US)")

    pdf.section_title("7.1 Capital Gains Tax Rates")
    pdf.table(
        ["Holding Period", "Tax Rate"],
        [
            ["< 1 year (Short-term)", "Ordinary income rate (22-37%)"],
            ["> 1 year (Long-term)", "Preferential rate (0/15/20%)"],
        ],
        [80, 110],
    )

    pdf.section_title("7.2 How Options Are Taxed")
    pdf.table(
        ["Scenario", "Tax Treatment"],
        [
            ["Buy option -> expires worthless", "Capital loss (deductible)"],
            ["Buy option -> sell to close", "Short-term capital gain/loss"],
            ["Sell put -> expires", "Premium = short-term gain"],
            ["Sell put -> assigned", "Premium reduces cost basis"],
            ["Sell covered call -> expires", "Premium = short-term gain"],
            ["Sell covered call -> called away", "Premium added to sale proceeds"],
        ],
        [80, 110],
    )
    pdf.warning_box("Most options income is short-term = taxed at your highest rate.")

    pdf.section_title("7.3 Wash Sale Rule")
    pdf.body_text(
        "If you sell a stock at a loss and buy back substantially identical securities within "
        "30 days, the loss is disallowed. Being assigned on a put can trigger this rule "
        "if you recently sold the same stock at a loss."
    )

    # ═══════════════════════════════════════
    # CHAPTER 8: CHECKLISTS
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("Chapter 8: Pre-Trade Checklists")

    pdf.section_title("8.1 General Options Checklist")
    for item in [
        "Direction: What is my thesis on this stock? (Bullish / Bearish / Neutral)",
        "Strategy Match: Does this strategy align with my thesis?",
        "Max Loss: If completely wrong, how much do I lose? Can I handle it?",
        "Liquidity: OI > 500? Bid-ask spread < 10%?",
        "IV Level: IV Rank high or low? Am I buying or selling at the right time?",
        "Expiration: 30-45 DTE? Avoiding earnings dates?",
        "Position Size: Risk < 5% of account?",
        "Exit Plan: When do I take profit? When do I cut losses?",
    ]:
        pdf.bullet(item)
    pdf.ln(3)

    pdf.section_title("8.2 Sell Put Specific Checklist")
    for item in [
        "Do I genuinely want to own this stock at this strike price?",
        "Can I afford 100 shares if assigned? (Cash or margin capacity)",
        "If the stock drops 30%, would I still want to hold?",
        "Is there an earnings report before expiration? (Avoid if yes)",
        "Is IV elevated? (IV Rank > 30 is preferred for selling)",
    ]:
        pdf.bullet(item)
    pdf.ln(3)

    # ═══════════════════════════════════════
    # APPENDIX A: PAYOFF DIAGRAMS
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("Appendix A: Payoff Diagrams")

    pdf.section_title("A.1 The Four Basic Options Payoffs")
    pdf.add_chart(os.path.join(CHARTS_DIR, "1_four_basic_payoffs.png"), w=185)

    pdf.add_page()
    pdf.section_title("A.2 Covered Call vs Stock Only")
    pdf.body_text("Green line = covered call, blue dashed = stock only. "
                  "The premium provides a small cushion on the downside, but caps your upside.")
    pdf.add_chart(os.path.join(CHARTS_DIR, "2_covered_call.png"), w=175)

    pdf.section_title("A.3 Wheel Strategy")
    pdf.body_text("Red = Step 1 (Sell Put). Green = Step 2 (Covered Call after assignment).")
    pdf.add_chart(os.path.join(CHARTS_DIR, "3_wheel_strategy.png"), w=175)

    pdf.add_page()
    pdf.section_title("A.4 Vertical Spreads")
    pdf.body_text("Bull Call Spread (bullish, limited risk/reward) and Bear Put Spread (bearish, limited risk/reward).")
    pdf.add_chart(os.path.join(CHARTS_DIR, "5_vertical_spreads.png"), w=185)

    pdf.section_title("A.5 Straddle and Strangle")
    pdf.body_text("Both profit from large moves in either direction. Straddle is more expensive but needs less movement.")
    pdf.add_chart(os.path.join(CHARTS_DIR, "6_straddle_strangle.png"), w=185)

    # ═══════════════════════════════════════
    # APPENDIX B: ABBREVIATIONS
    # ═══════════════════════════════════════
    pdf.add_page()
    pdf.chapter_title("Appendix B: Common Abbreviations")
    pdf.table(
        ["Abbrev.", "Full Name", "Meaning"],
        [
            ["BTO", "Buy to Open", "Open a new long position"],
            ["STO", "Sell to Open", "Open a new short position"],
            ["BTC", "Buy to Close", "Close an existing short"],
            ["STC", "Sell to Close", "Close an existing long"],
            ["CSP", "Cash-Secured Put", "Sell put backed by cash"],
            ["CC", "Covered Call", "Sell call backed by shares"],
            ["IV", "Implied Volatility", "Market-expected volatility"],
            ["HV", "Historical Volatility", "Actual past volatility"],
            ["OI", "Open Interest", "Total open contracts"],
            ["DTE", "Days to Expiration", "Days until expiry"],
            ["ATM", "At The Money", "Strike = stock price"],
            ["ITM", "In The Money", "Option has intrinsic value"],
            ["OTM", "Out of The Money", "No intrinsic value"],
        ],
        [25, 65, 100],
    )

    pdf.ln(10)
    pdf.section_title("Recommended Learning Path")
    pdf.code_block(
        "Week 1:  Read Chapters 1-2. Browse option chains on Fidelity (don't trade yet)\n"
        "Week 2:  Paper trade using thinkorswim or options profit calculator websites\n"
        "Week 3:  First real trade: Sell 1 CSP on a stock you want to own\n"
        "Week 4+: Review results. Learn Chapters 4-6. Add covered calls."
    )

    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 8, "This guide is for educational purposes only. Not financial advice.", align="C")

    # Save
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    pdf.output(OUTPUT_PATH)
    print(f"PDF saved to: {OUTPUT_PATH}")
    print(f"Pages: {pdf.page_no()}")


if __name__ == "__main__":
    build_pdf()
