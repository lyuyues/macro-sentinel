"""Generate Semiconductor Industry Report PDF with Chinese font support."""
import os
from fpdf import FPDF

OUTPUT_PATH = "output/Semiconductor_Industry_Report.pdf"
# Arial Unicode MS supports CJK characters
FONT_PATH = "/Library/Fonts/Arial Unicode.ttf"


class SemiPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("CJK", "", FONT_PATH, uni=True)
        self.add_font("CJK", "B", FONT_PATH, uni=True)
        self.add_font("CJK", "I", FONT_PATH, uni=True)

    def header(self):
        if self.page_no() > 1:
            self.set_font("CJK", "I", 7)
            self.set_text_color(150, 150, 150)
            self.cell(95, 5, "Semiconductor Industry Report", align="L")
            self.cell(95, 5, f"Page {self.page_no()}", align="R")
            self.ln(8)

    def chapter_title(self, title):
        self.set_font("CJK", "B", 16)
        self.set_text_color(20, 50, 100)
        self.multi_cell(0, 10, title)
        y = self.get_y()
        self.set_draw_color(20, 50, 100)
        self.set_line_width(0.8)
        self.line(10, y, 200, y)
        self.set_line_width(0.2)
        self.ln(5)

    def section_title(self, title):
        self.set_font("CJK", "B", 13)
        self.set_text_color(30, 70, 130)
        self.multi_cell(0, 8, title)
        self.ln(2)

    def sub_section(self, title):
        self.set_font("CJK", "B", 11)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 7, title)
        self.ln(1)

    def body(self, text):
        self.set_font("CJK", "", 9.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def bold_body(self, text):
        self.set_font("CJK", "B", 9.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def bullet(self, text):
        self.set_font("CJK", "", 9.5)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        self.set_x(x + 4)
        self.multi_cell(0, 5, "- " + text)
        self.ln(0.5)

    def code_block(self, text):
        self.set_font("Courier", "", 8)
        self.set_fill_color(242, 242, 242)
        self.set_text_color(40, 40, 40)
        for line in text.split("\n"):
            safe = line.encode("latin-1", errors="replace").decode("latin-1")
            self.cell(190, 4.5, "  " + safe, fill=True)
            self.ln(4.5)
        self.ln(2)

    def table(self, headers, rows, col_widths=None):
        if col_widths is None:
            col_widths = [190 / len(headers)] * len(headers)
        # check page space
        needed = 8 + len(rows) * 6 + 5
        if self.get_y() + needed > 270:
            self.add_page()
        # header row
        self.set_font("CJK", "B", 8)
        self.set_fill_color(20, 50, 100)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
        self.ln()
        # data rows
        self.set_font("CJK", "", 8)
        self.set_text_color(30, 30, 30)
        alt = False
        for row in rows:
            # check if row fits on page
            if self.get_y() + 6 > 275:
                self.add_page()
                # reprint header
                self.set_font("CJK", "B", 8)
                self.set_fill_color(20, 50, 100)
                self.set_text_color(255, 255, 255)
                for i, h in enumerate(headers):
                    self.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
                self.ln()
                self.set_font("CJK", "", 8)
                self.set_text_color(30, 30, 30)
                alt = False
            if alt:
                self.set_fill_color(240, 243, 250)
            else:
                self.set_fill_color(255, 255, 255)
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 6, str(cell), border=1, fill=True, align="C")
            self.ln()
            alt = not alt
        self.ln(3)

    def insight_box(self, label, text, color_rgb=(30, 100, 60)):
        r, g, b = color_rgb
        self.set_fill_color(min(r + 210, 255), min(g + 180, 255), min(b + 210, 255))
        self.set_draw_color(r, g, b)
        self.set_line_width(0.5)
        y = self.get_y()
        # estimate height
        self.set_font("CJK", "B", 9)
        lines = len(text) / 45 + 2
        h = max(lines * 5 + 4, 14)
        self.rect(10, y, 190, h, style="DF")
        self.set_xy(14, y + 2)
        self.set_text_color(r, g, b)
        self.set_font("CJK", "B", 9)
        self.cell(30, 5, label)
        self.set_font("CJK", "", 9)
        self.multi_cell(146, 5, text)
        self.set_y(y + h + 3)
        self.set_line_width(0.2)

    def page_break_check(self, needed=40):
        if self.get_y() + needed > 270:
            self.add_page()


def build_pdf():
    pdf = SemiPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(10, 10, 10)

    # ============ COVER PAGE ============
    pdf.add_page()
    pdf.ln(35)
    pdf.set_font("CJK", "B", 28)
    pdf.set_text_color(20, 50, 100)
    pdf.multi_cell(0, 14, "Semiconductor Industry\nValue Chain Report", align="C")
    pdf.ln(5)
    pdf.set_font("CJK", "B", 16)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 10, "From Sand to Chips", align="C")
    pdf.ln(15)
    pdf.set_draw_color(20, 50, 100)
    pdf.set_line_width(1)
    pdf.line(50, pdf.get_y(), 160, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(15)
    pdf.set_font("CJK", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 7, (
        "Author: Fab Owner (28nm + 5nm)\n"
        "Audience: Semiconductor Industry Investors\n"
        "Date: February 2026"
    ), align="C")
    pdf.ln(30)
    pdf.set_font("CJK", "I", 9)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 5, (
        "Disclaimer: This report is based on public information and industry experience. "
        "It does not constitute investment advice. All financial data are estimates."
    ), align="C")

    # ============ TABLE OF CONTENTS ============
    pdf.add_page()
    pdf.chapter_title("Table of Contents")
    pdf.set_font("CJK", "", 10)
    pdf.set_text_color(30, 30, 30)
    toc = [
        ("Ch 1", "Value Chain Overview"),
        ("Ch 2", "Upstream: Materials & Equipment"),
        ("Ch 3", "Midstream: EDA & IP"),
        ("Ch 4", "Midstream: IC Design (Fabless)"),
        ("Ch 5", "Midstream: Wafer Fabrication"),
        ("Ch 6", "Downstream: Packaging & Advanced Packaging"),
        ("Ch 7", "End Markets & Demand Drivers"),
        ("Ch 8", "Business Model Comparison: IDM vs Fabless vs Foundry"),
        ("Ch 9", "Industry Landscape & Trends"),
        ("Ch 10", "Key Risks & Challenges"),
        ("Ch 11", "Investment Opportunities & Thesis"),
        ("Appendix", "Key Company Reference"),
    ]
    for ch, title in toc:
        pdf.cell(25, 8, ch)
        pdf.cell(0, 8, title)
        pdf.ln(8)

    # ============ CHAPTER 1 ============
    pdf.add_page()
    pdf.chapter_title("Chapter 1: Value Chain Overview")

    pdf.body(
        "The semiconductor supply chain is the most complex industrial chain in human history. "
        "A single advanced chip requires crossing 16 countries, 70+ border crossings, 1000+ process steps, "
        "and 4-6 months from design to finished product."
    )

    pdf.section_title("Supply Chain Flow")
    pdf.code_block(
        "Sand(SiO2) --> Polysilicon --> Ingot --> Wafer\n"
        "                                          |\n"
        "EDA + IP --> Chip Design --> Mask          v\n"
        "                                    Fab (Manufacturing)\n"
        "Equipment + Materials ------------>       |\n"
        "                                          v\n"
        "                                  Packaging --> Test\n"
        "                                          |\n"
        "                                          v\n"
        "                              Finished Chip --> End Products"
    )

    pdf.section_title("Value Distribution (per $100 Mobile SoC)")
    pdf.table(
        ["Segment", "Value %", "Gross Margin", "Characteristics"],
        [
            ["EDA/IP", "~3%", "75-85%", "High margin, small market"],
            ["IC Design", "~35-50%", "50-70%", "Highest profit, asset-light"],
            ["Equipment", "~8-12%", "45-65%", "Cyclical, high barriers"],
            ["Materials", "~10-15%", "30-50%", "Japan-dominated"],
            ["Fabrication", "~15-25%", "40-60%", "Most capital-intensive"],
            ["Packaging/Test", "~5-10%", "15-50%", "Advanced pkg changing game"],
        ],
        [47, 30, 38, 75],
    )

    # ============ CHAPTER 2 ============
    pdf.add_page()
    pdf.chapter_title("Chapter 2: Upstream - Materials & Equipment")

    pdf.section_title("2.1 Semiconductor Materials (300+ types)")

    pdf.sub_section("Silicon Wafers (~35% of material cost)")
    pdf.body(
        "Silicon wafers are the 'canvas' on which all circuits are etched. "
        "Mainstream 300mm (12-inch) wafers can yield ~500 mobile chips per wafer. "
        "A single wafer costs ~$100-150 but becomes $5,000-50,000 worth of chips."
    )
    pdf.table(
        ["Company", "Market Share", "Notes"],
        [
            ["Shin-Etsu (Japan)", "~30%", "Global #1, quality benchmark"],
            ["SUMCO (Japan)", "~25%", "Japan #2"],
            ["GlobalWafers (Taiwan)", "~15%", "Acquired Siltronic"],
            ["SK Siltron (Korea)", "~13%", "SK Group subsidiary"],
        ],
        [60, 40, 90],
    )
    pdf.insight_box("Fab Owner View:", "Wafer supply is our largest single material cost. When tight, we lock contracts 12-18 months ahead.", (30, 80, 140))

    pdf.page_break_check(50)
    pdf.sub_section("Photoresist (Key Chokepoint)")
    pdf.body(
        "Photoresists transfer circuit patterns onto wafers during lithography. "
        "EUV photoresist is the most advanced type - one liter costs $5,000-10,000. "
        "Japan dominates: JSR (~25%), TOK (~22%), Shin-Etsu (~15%)."
    )
    pdf.bullet("KrF resist (248nm): mature nodes")
    pdf.bullet("ArF resist (193nm): advanced nodes")
    pdf.bullet("EUV resist (13.5nm): highest barrier, export-controlled")

    pdf.page_break_check(40)
    pdf.sub_section("Other Critical Materials")
    pdf.table(
        ["Material", "Use", "Key Suppliers"],
        [
            ["Specialty Gases", "Etch, Deposition", "Air Liquide, Linde"],
            ["CMP Slurry", "Planarization", "Cabot Micro, Fujimi"],
            ["Sputtering Targets", "Metal films", "JX Metals, Honeywell"],
            ["Photomask Blanks", "Mask carrier", "HOYA, AGC"],
            ["Wet Chemicals", "Cleaning, Etching", "Stella Chemifa"],
        ],
        [50, 50, 90],
    )

    # Equipment section
    pdf.add_page()
    pdf.section_title("2.2 Semiconductor Equipment")
    pdf.bold_body("This is the segment with the HIGHEST barriers and DEEPEST moats in the entire chain.")

    pdf.table(
        ["Process Step", "Function", "Leader", "Share", "Price/Unit"],
        [
            ["Lithography", "Pattern exposure", "ASML", "~90%", "EUV: $350-400M"],
            ["Etch", "Remove material", "Lam Research", "~45%", "$5-15M"],
            ["Deposition", "Thin film deposit", "Applied Materials", "~40%", "$3-10M"],
            ["Ion Implant", "Doping", "Applied Materials", "~70%", "$3-5M"],
            ["CMP", "Planarization", "Applied Materials", "~60%", "$5M"],
            ["Cleaning", "Contamination removal", "Screen (Japan)", "~50%", "$2-5M"],
            ["Inspection", "Defect detection", "KLA", "~55%", "$5-30M"],
        ],
        [32, 34, 36, 22, 36, 30],
    )

    pdf.page_break_check(50)
    pdf.sub_section("ASML: The Most Critical Chokepoint")
    pdf.body(
        "ASML is the ONLY company that can build EUV (Extreme Ultraviolet) lithography machines. "
        "Without EUV, no chips below 7nm can be manufactured."
    )
    pdf.bullet("One EUV machine: ~150 tons, ~100,000 parts, 40 containers to ship, 6 months to install")
    pdf.bullet("Annual capacity: only ~50 EUV units, perpetually sold out")
    pdf.bullet("Customers: only TSMC, Samsung, Intel can afford and use them")
    pdf.bullet("Next-gen High-NA EUV: ~$350-400M per unit, shipping from 2025")

    pdf.insight_box(
        "Fab Owner View:",
        "My 5nm fab has 10 EUV tools = $1.5-2B just for lithography. ASML lead time is 18-24 months. "
        "This is why capacity expansion isn't just about money - equipment is the bottleneck.",
        (30, 80, 140),
    )

    pdf.page_break_check(50)
    pdf.sub_section("Building a 5nm Fab: Equipment Investment")
    pdf.table(
        ["Equipment Type", "Quantity", "Total Investment"],
        [
            ["EUV Lithography", "10-15 units", "$3.5-6.0B"],
            ["DUV Lithography", "30-50 units", "$1.0-1.5B"],
            ["Etch Tools", "80-120 units", "$1.0-1.5B"],
            ["Deposition Tools", "100-150 units", "$0.8-1.2B"],
            ["Inspection/Metrology", "50-80 units", "$0.5-1.0B"],
            ["Others", "200+ units", "$1.0-1.5B"],
            ["TOTAL", "~500-600 units", "$8-13B"],
        ],
        [63, 63, 64],
    )
    pdf.body("Including cleanroom construction, a single advanced fab costs $15-20 BILLION.")

    # ============ CHAPTER 3 ============
    pdf.add_page()
    pdf.chapter_title("Chapter 3: EDA & IP")

    pdf.section_title("3.1 EDA (Electronic Design Automation)")
    pdf.body(
        "EDA is the software that chip designers use to create chips - like CAD for architects, "
        "but orders of magnitude more complex. A modern SoC contains BILLIONS of transistors; "
        "manual design is impossible."
    )
    pdf.bullet("Logic synthesis: convert code to circuits")
    pdf.bullet("Place & route: lay out circuits on chip")
    pdf.bullet("Timing analysis: ensure signal integrity")
    pdf.bullet("Physical verification: check manufacturing rules")
    pdf.bullet("Simulation: verify functionality")

    pdf.bold_body("Market: US Three-Company Oligopoly")
    pdf.table(
        ["Company", "Ticker", "2025 Rev", "Share", "Strength"],
        [
            ["Synopsys", "SNPS", "~$6.5B", "~33%", "Synthesis, Sim, IP"],
            ["Cadence", "CDNS", "~$4.5B", "~30%", "Analog, Verification"],
            ["Siemens EDA", "Private", "~$2.0B", "~15%", "PCB, IC Packaging"],
        ],
        [35, 25, 30, 25, 75],
    )

    pdf.bold_body("Why EDA is a Great Business:")
    pdf.bullet("Subscription model (SaaS), predictable recurring revenue")
    pdf.bullet("Extremely high switching costs (engineer training + design flow lock-in)")
    pdf.bullet("40+ years of accumulated algorithms and process libraries")
    pdf.bullet("Gross margin ~80%, operating margin ~30-35%")

    pdf.page_break_check(50)
    pdf.section_title("3.2 IP Cores (Intellectual Property)")
    pdf.body(
        "IP cores are pre-designed, reusable circuit blocks. Chip designers buy IP to accelerate "
        "development, similar to how programmers use open-source libraries."
    )
    pdf.sub_section("ARM: The Most Important IP Company")
    pdf.bullet("ARM designs CPU architecture and licenses it - makes zero chips")
    pdf.bullet("99% of smartphones, 95% of IoT devices use ARM architecture")
    pdf.bullet("Business model: License fee ($1-10M/customer) + Royalty ($0.01-0.05/chip)")
    pdf.bullet("2025 revenue ~$3.8B, but influences $200B+ worth of chips")

    pdf.table(
        ["Company", "Core IP", "Notes"],
        [
            ["Synopsys", "Interface IP (USB, PCIe, DDR)", "EDA + IP double moat"],
            ["Cadence", "Analog/Mixed-signal IP", ""],
            ["Imagination Tech", "GPU IP", "Apple used then went custom"],
            ["CEVA", "DSP, Wireless IP", "Cellular & WiFi/BT"],
            ["Rambus", "Memory Interface IP", "Patent licensing focus"],
        ],
        [45, 70, 75],
    )

    # ============ CHAPTER 4 ============
    pdf.add_page()
    pdf.chapter_title("Chapter 4: IC Design (Fabless)")
    pdf.bold_body("This is the MOST profitable and FASTEST growing segment in the semiconductor value chain.")
    pdf.body("Fabless companies design chips only, outsourcing manufacturing to foundries like TSMC.")

    pdf.section_title("4.1 Major Chip Categories & Leaders")
    pdf.table(
        ["Category", "Global Leader", "2025 Rev", "Margin", "Moat"],
        [
            ["GPU / AI", "NVIDIA (NVDA)", "~$130B", "73-78%", "CUDA ecosystem"],
            ["Mobile SoC", "Qualcomm (QCOM)", "~$42B", "55-58%", "Baseband patents"],
            ["Mobile SoC #2", "MediaTek", "~$18B", "45-48%", "Cost-effective"],
            ["Datacenter CPU", "Intel / AMD", "~$15B (AMD)", "50-55%", "x86 ecosystem"],
            ["Networking", "Broadcom (AVGO)", "~$51B", "65-70%", "M&A + diversity"],
            ["FPGA", "AMD (Xilinx)", "~$3B", "60-65%", "Programmability"],
            ["Custom Silicon", "Apple/Google/AMZN", "N/A", "N/A", "Vertical integration"],
        ],
        [30, 38, 28, 24, 40, 30],
    )

    pdf.page_break_check(50)
    pdf.section_title("4.2 Design Cost Escalation")
    pdf.body("The cost of designing a chip at the leading edge has skyrocketed:")
    pdf.table(
        ["Process Node", "Design Cost", "Team Size", "Timeline"],
        [
            ["28nm", "~$50M", "100-200", "12-18 months"],
            ["7nm", "~$300M", "300-500", "18-24 months"],
            ["5nm", "~$500M", "500-800", "18-24 months"],
            ["3nm", "~$700M-1B", "800-1500", "24-30 months"],
            ["2nm (GAA)", "~$1-1.5B", "1000+", "24-36 months"],
        ],
        [40, 50, 50, 50],
    )
    pdf.insight_box(
        "Fab Owner View:",
        "3nm mask set alone costs $20-30M. Only companies with $10B+ revenue can sustain leading-edge design. "
        "Advanced node customers have shrunk from hundreds (28nm era) to fewer than 10 (3nm).",
        (30, 80, 140),
    )

    pdf.page_break_check(50)
    pdf.section_title("4.3 NVIDIA: The AI Cash Machine")
    pdf.bullet("Market cap: ~$3 TRILLION (global top 3)")
    pdf.bullet("Core products: H100/H200/B100/B200 GPUs for AI training & inference")
    pdf.bullet("Moat: NOT hardware, but CUDA software ecosystem - millions of AI developers locked in")
    pdf.bullet("Gross margin: 75%+ (every $1 sold, $0.75 is gross profit)")
    pdf.bullet("Manufacturing: 100% outsourced to TSMC (5nm/4nm)")
    pdf.body(
        "Investment insight: NVIDIA proves that in the Fabless model, competitive advantage comes from "
        "architecture innovation + software ecosystem, NOT manufacturing capability."
    )

    # ============ CHAPTER 5 ============
    pdf.add_page()
    pdf.chapter_title("Chapter 5: Wafer Fabrication")

    pdf.section_title("5.1 Manufacturing Essence: Sculpting at Atomic Scale")
    pdf.body(
        "Manufacturing a chip requires 1000+ process steps. Core steps are repeated 50-80 times (layers):"
    )
    pdf.code_block(
        "Lithography --> Etch --> Deposition --> Ion Implant --> CMP --> Clean\n"
        "     ^                                                          |\n"
        "     |________________________________________________________|\n"
        "                  Repeat 50-80 layers (advanced nodes)"
    )
    pdf.bullet("3nm: transistor gate = 3nm = ~15 atoms wide")
    pdf.bullet("Cleanroom: Class 1 (10,000x cleaner than an operating room)")
    pdf.bullet("Water: ~50,000 tons/day per advanced fab (like a small city)")
    pdf.bullet("Electricity: ~2-3 billion kWh/year per fab")

    pdf.section_title("5.2 Process Node Evolution")
    pdf.table(
        ["Node", "Year", "Structure", "Players", "Products"],
        [
            ["28nm", "2011", "Planar", "TSMC,Samsung,GF,SMIC", "IoT, Auto, Display"],
            ["14/16nm", "2014", "FinFET", "TSMC,Samsung,Intel,GF", "Mid-range phone"],
            ["7nm", "2018", "FinFET", "TSMC, Samsung", "Flagship, AMD CPU"],
            ["5nm", "2020", "FinFET", "TSMC, Samsung", "iPhone, M1, AI"],
            ["3nm", "2022", "FinFET/GAA", "TSMC, Samsung", "iPhone 15 Pro, M3"],
            ["2nm", "2025", "GAA Nanosheet", "TSMC,Samsung,Intel", "Next-gen flagship"],
            ["A14(1.4nm)", "2027-28", "GAA", "TSMC", "Future flagship"],
        ],
        [22, 20, 32, 56, 40, 20],
    )
    pdf.body(
        "Key inflection: FinFET to GAA (Gate-All-Around) is the biggest structural change since "
        "FinFET in 2011. GAA uses nanosheet stacking instead of fins for better current control, "
        "but manufacturing complexity increases significantly."
    )

    pdf.page_break_check(50)
    pdf.section_title("5.3 Global Foundry Landscape")
    pdf.bold_body("TSMC: The Undisputed King")
    pdf.table(
        ["Metric", "Data"],
        [
            ["Advanced Node Share", "~90%"],
            ["Overall Foundry Share", "~60%"],
            ["2025 Revenue", "~$90B"],
            ["Gross Margin", "55-60%"],
            ["CapEx (2025)", "~$38B"],
            ["Employees", "~76,000"],
        ],
        [80, 110],
    )

    pdf.page_break_check(50)
    pdf.bold_body("Competitive Landscape:")
    pdf.table(
        ["Foundry", "Best Node", "Share", "Key Customers", "Status"],
        [
            ["TSMC", "3nm/2nm", "~60%", "Apple,NVIDIA,AMD", "Tech+yield leader"],
            ["Samsung", "3nm GAA", "~12%", "Qualcomm,Google", "First GAA but low yield"],
            ["Intel Foundry", "18A(~2nm)", "~3%", "Internal,MSFT?", "Turnaround uncertain"],
            ["GlobalFoundries", "12nm", "~6%", "AMD(mature),Auto", "Mature+specialty focus"],
            ["SMIC", "7nm(DUV)", "~6%", "Huawei,China", "Sanctioned, no EUV"],
            ["UMC", "14nm", "~7%", "Display,WiFi", "Mature node, stable"],
        ],
        [32, 27, 20, 43, 38, 30],
    )

    pdf.page_break_check(60)
    pdf.section_title("5.4 Fab Economics (Real Owner Perspective)")
    pdf.sub_section("28nm Fab (40K wafers/month, ~$5B total investment)")
    pdf.table(
        ["Cost Item", "Annual Spend", "% of Total"],
        [
            ["Depreciation (equip+building)", "$600M", "40%"],
            ["Materials (wafer,resist,gas)", "$300M", "20%"],
            ["Labor", "$250M", "17%"],
            ["Utilities (water,power)", "$150M", "10%"],
            ["Maintenance", "$100M", "7%"],
            ["Other", "$100M", "6%"],
            ["TOTAL Operating Cost", "~$1.5B", "100%"],
        ],
        [75, 55, 60],
    )
    pdf.bullet("Wafer cost: ~$3,000 | ASP: ~$4,500-5,000 | Gross margin: ~35-40%")
    pdf.bullet("After depreciation ends: margin jumps to 50%+ = cash cow!")

    pdf.page_break_check(50)
    pdf.sub_section("5nm Fab (50K wafers/month, ~$18B total investment)")
    pdf.table(
        ["Cost Item", "Annual Spend", "% of Total"],
        [
            ["Depreciation", "$2.5B", "50%"],
            ["Materials", "$800M", "16%"],
            ["Labor", "$500M", "10%"],
            ["Utilities", "$300M", "6%"],
            ["Maintenance + Spares", "$400M", "8%"],
            ["EUV light source etc.", "$200M", "4%"],
            ["Other", "$300M", "6%"],
            ["TOTAL Operating Cost", "~$5.0B", "100%"],
        ],
        [75, 55, 60],
    )
    pdf.bullet("Wafer cost: ~$8,500 | ASP (Apple/NVIDIA): ~$16,000-18,000 | Margin: ~50-55%")
    pdf.bullet("Critical: yield from 50% (initial) to 90%+ (mature) determines profit/loss")

    pdf.bold_body("Core Operating Challenges:")
    pdf.bullet("Yield management: 1000+ steps, each must be >99.9% or final yield collapses")
    pdf.bullet("Equipment utilization target >90%. EUV bottleneck: ~120 wafers/hour, must run 24/7")
    pdf.bullet("Customer concentration: top 3 = 50%+ revenue, losing one is catastrophic")
    pdf.bullet("Tech iteration: must invest in next node every 2-3 years or become obsolete")

    # ============ CHAPTER 6 ============
    pdf.add_page()
    pdf.chapter_title("Chapter 6: Packaging & Advanced Packaging")

    pdf.section_title("6.1 Traditional OSAT")
    pdf.body(
        "Packaging protects the bare die and routes electrical signals to the PCB. "
        "Traditional packaging (Wire Bond, Flip Chip) has the lowest margins in the chain, "
        "but advanced packaging is completely changing this."
    )
    pdf.table(
        ["Company", "HQ", "2025 Rev", "Share", "Key Customers"],
        [
            ["ASE", "Taiwan", "~$20B", "~30%", "Apple, NVIDIA, AMD"],
            ["Amkor", "US", "~$7B", "~15%", "Apple, Qualcomm"],
            ["JCET", "China", "~$4B", "~10%", "China domestic"],
            ["TFME", "China", "~$2.5B", "~6%", "AMD"],
            ["PTI", "Taiwan", "~$2B", "~5%", "Memory packaging"],
        ],
        [30, 25, 30, 25, 80],
    )

    pdf.section_title("6.2 Advanced Packaging: The Game Changer")
    pdf.body(
        "When single-chip process improvements slow down (Moore's Law deceleration), "
        "packaging MULTIPLE chips together becomes the new performance path. "
        "This is 'More than Moore.'"
    )
    pdf.table(
        ["Technology", "Provider", "Application", "Key Feature"],
        [
            ["CoWoS", "TSMC", "NVIDIA H100/B100", "GPU+HBM on silicon interposer"],
            ["InFO", "TSMC", "iPhone AP", "No substrate, thinner"],
            ["EMIB", "Intel", "Intel GPU", "Small silicon bridge"],
            ["Foveros", "Intel", "Meteor Lake", "3D stacking"],
            ["HBM", "SK Hynix/Samsung", "AI GPUs", "8-12 layer DRAM stack"],
            ["Chiplet", "AMD/Intel/Apple", "EPYC, M3 Ultra", "Multi-die interconnect"],
        ],
        [30, 42, 46, 72],
    )

    pdf.page_break_check(40)
    pdf.bold_body("CoWoS Bottleneck Effect:")
    pdf.bullet("2024 CoWoS capacity: ~35K wafers/month")
    pdf.bullet("2025 target: ~60K wafers/month")
    pdf.bullet("Demand still far exceeds supply")
    pdf.bullet("TSMC CoWoS revenue: ~$2B (2022) -> ~$10B+ (2025)")
    pdf.insight_box(
        "Investment Insight:",
        "Advanced packaging is transforming from 'low-margin commodity' to 'high-value scarce resource.' "
        "TSMC's dominance in advanced packaging is even stronger than in foundry.",
        (20, 100, 60),
    )

    pdf.page_break_check(50)
    pdf.section_title("6.3 HBM: The 'Ammunition' of the AI Era")
    pdf.body("HBM (High Bandwidth Memory) vertically stacks multiple DRAM layers for ultra-high bandwidth.")
    pdf.table(
        ["Generation", "Bandwidth", "Layers", "Capacity", "Used In"],
        [
            ["HBM2e", "460 GB/s", "8", "16GB", "A100"],
            ["HBM3", "819 GB/s", "8", "24GB", "H100"],
            ["HBM3e", "1.2 TB/s", "8-12", "36-48GB", "H200, B100"],
            ["HBM4", "2+ TB/s", "12-16", "48-64GB", "2026+"],
        ],
        [32, 38, 30, 38, 52],
    )
    pdf.table(
        ["Company", "HBM Share", "Advantage"],
        [
            ["SK Hynix", "~50%", "1-2 gen ahead, NVIDIA preferred"],
            ["Samsung", "~35%", "Large capacity, catching up"],
            ["Micron", "~15%", "Late entrant, price competition"],
        ],
        [50, 40, 100],
    )
    pdf.body("SK Hynix HBM gross margin: 70%+ (vs normal DRAM ~40%). HBM is their most profitable business.")

    # ============ CHAPTER 7 ============
    pdf.add_page()
    pdf.chapter_title("Chapter 7: End Markets & Demand Drivers")

    pdf.section_title("7.1 Demand Structure (2025 Global Semi Market ~$600-650B)")
    pdf.table(
        ["End Market", "Share", "Growth Driver", "Key Chip Types"],
        [
            ["Data Center / AI", "~30%", "AI training & inference", "GPU, ASIC, HBM"],
            ["Smartphones", "~22%", "On-device AI, 5G", "Mobile SoC, Memory"],
            ["PC / Server CPU", "~15%", "AI PC, enterprise refresh", "x86/ARM CPU"],
            ["Automotive", "~12%", "EV, autonomous driving", "Power semi, MCU"],
            ["Industrial / IoT", "~10%", "Factory automation", "MCU, Sensors"],
            ["Consumer Electronics", "~8%", "AR/VR, wearables", "Various"],
            ["Telecom Infra", "~3%", "5G base stations", "FPGA, DSP"],
        ],
        [40, 20, 52, 50, 28],
    )

    pdf.section_title("7.2 AI: The Strongest Demand Driver")
    pdf.body("AI compute demand is growing 4-5x annually:")
    pdf.bullet("2024: Global AI chip market ~$60B")
    pdf.bullet("2025: Estimated ~$90-100B")
    pdf.bullet("2028: Estimated ~$200-300B")
    pdf.body(
        "This directly drives: NVIDIA GPUs (design) -> TSMC advanced nodes (fab) -> "
        "SK Hynix HBM (memory) -> CoWoS (packaging) -> ASML EUV (equipment)"
    )

    pdf.page_break_check(40)
    pdf.section_title("7.3 Automotive: Most Underestimated Growth Market")
    pdf.bullet("Traditional ICE car: $300-500 semiconductor content")
    pdf.bullet("High-end EV (Tesla Model S): $1,500-3,000 semiconductor content")
    pdf.bullet("L4 autonomous vehicle: potentially $5,000+")
    pdf.bold_body("Key growth areas:")
    pdf.bullet("Power semiconductors (IGBT, SiC): Infineon, STMicro, ON Semi")
    pdf.bullet("Autonomous driving SoC: NVIDIA Drive, Mobileye, Qualcomm")
    pdf.bullet("Automotive MCU: NXP, Renesas, TI")

    # ============ CHAPTER 8 ============
    pdf.add_page()
    pdf.chapter_title("Chapter 8: Business Models Compared")

    pdf.section_title("8.1 IDM (Integrated Device Manufacturer)")
    pdf.body("Definition: Design + Manufacturing + Packaging all in-house.")
    pdf.table(
        ["Company", "Products", "Advantage", "Disadvantage"],
        [
            ["Intel", "CPU, FPGA", "Design-mfg co-optimize", "Huge capex, inflexible"],
            ["Samsung", "Memory, Foundry", "Scale economics", "Customer-competitor conflict"],
            ["TI", "Analog IC", "Long lifecycle, stable", "Slow growth"],
            ["Infineon", "Power semi", "Vertical integration", "Auto/industrial cycles"],
        ],
        [30, 40, 55, 65],
    )

    pdf.section_title("8.2 Fabless (Design Only)")
    pdf.body("Definition: Design only, outsource manufacturing.")
    pdf.table(
        ["Company", "Products", "Advantage", "Disadvantage"],
        [
            ["NVIDIA", "GPU, AI", "Asset-light, innovation", "Foundry capacity dependent"],
            ["AMD", "CPU, GPU", "Flexible node choice", "NVIDIA competition"],
            ["Qualcomm", "Mobile SoC", "Patent + chip dual rev", "Apple custom risk"],
            ["Broadcom", "Network, ASIC", "M&A + diversification", "Integration risk"],
        ],
        [30, 40, 55, 65],
    )

    pdf.section_title("8.3 Pure-Play Foundry")
    pdf.body("Definition: Manufacturing only, no competing chip designs.")
    pdf.table(
        ["Company", "Advantage", "Disadvantage"],
        [
            ["TSMC", "No customer competition, high trust", "Customer concentration"],
            ["GlobalFoundries", "Specialty process differentiation", "No advanced node growth"],
            ["UMC", "Mature node profit stability", "Growth ceiling"],
        ],
        [50, 70, 70],
    )

    pdf.page_break_check(50)
    pdf.section_title("8.4 Business Model Evolution")
    pdf.code_block(
        "1970-90s: IDM dominant (Intel, TI, Motorola do everything)\n"
        "     |\n"
        "1990-2010s: Fabless rises (NVIDIA, Qualcomm, AMD spins off GF)\n"
        "     |\n"
        "2020s+: System companies design own chips\n"
        "  - Apple M-series + TSMC\n"
        "  - Google TPU\n"
        "  - Amazon Graviton\n"
        "  - Tesla FSD chip\n"
        "  - Microsoft Maia"
    )
    pdf.insight_box(
        "Investment Insight:",
        "Fabless wins in the AI era. But system companies (Apple, Google, Amazon) designing "
        "custom silicon threatens traditional chip companies like Qualcomm and Intel.",
        (20, 100, 60),
    )

    # ============ CHAPTER 9 ============
    pdf.add_page()
    pdf.chapter_title("Chapter 9: Industry Trends")

    pdf.section_title("Trend 1: AI-Driven Super Cycle")
    pdf.bullet("AI compute demand doubles every 3.4 months (far faster than Moore's Law's 2 years)")
    pdf.bullet("Each AI datacenter: $5-10B investment, 60-70% is semiconductors")
    pdf.bullet("MSFT+Google+Meta+AMZN AI capex: ~$100B (2022) -> ~$250B (2025)")

    pdf.section_title("Trend 2: Geopolitics Reshaping Supply Chains")
    pdf.table(
        ["Policy", "Country", "Amount", "Impact"],
        [
            ["CHIPS Act", "US", "$52.7B", "TSMC/Samsung/Intel build US fabs"],
            ["EU Chips Act", "EU", "$49B", "Target 20% global share by 2030"],
            ["Big Fund III", "China", "$47B", "Domestic substitution"],
            ["Export Controls", "US", "N/A", "Restrict advanced chips/equip to China"],
        ],
        [35, 25, 30, 100],
    )
    pdf.insight_box(
        "Fab Owner View:",
        "Geopolitics makes everything more expensive. TSMC's Arizona fab costs 4-5x more than Taiwan. "
        "But customers (especially US government) will pay a premium for supply chain security.",
        (30, 80, 140),
    )

    pdf.page_break_check(40)
    pdf.section_title("Trend 3: Chiplet & Heterogeneous Integration")
    pdf.bullet("Different modules at different nodes (compute at 3nm, I/O at 7nm) = lower cost, higher yield")
    pdf.bullet("UCIe standard driving cross-company chiplet interoperability")
    pdf.bullet("Examples: AMD EPYC (compute chiplets + I/O die), Apple M3 Ultra (two M3 Max fused)")

    pdf.section_title("Trend 4: Mature Node Hidden Value")
    pdf.bullet("~60% of chips globally still use 28nm and above")
    pdf.bullet("Auto, industrial, IoT heavily use 40nm-180nm")
    pdf.bullet("Fully depreciated mature fabs = 50%+ profit margin cash machines")
    pdf.bullet("Risk: China massively expanding mature node capacity")

    pdf.section_title("Trend 5: Third-Gen Semiconductors (Wide Bandgap)")
    pdf.table(
        ["Material", "Properties", "Applications", "Key Players"],
        [
            ["SiC", "High voltage/temp/efficiency", "EV inverters, chargers", "Wolfspeed, ST, Infineon"],
            ["GaN", "High frequency/efficiency", "Fast charge, 5G, DC power", "EPC, Navitas"],
        ],
        [25, 50, 50, 65],
    )
    pdf.body("SiC market: ~$2B (2022) -> ~$10B (2027), CAGR ~35%")

    pdf.section_title("Trend 6: Silicon Photonics & Quantum Computing")
    pdf.bullet("Silicon photonics: light replaces electrons for datacenter interconnect bandwidth")
    pdf.bullet("Quantum computing: IBM, Google, IonQ advancing, but 5-10 years from commercial viability")

    pdf.page_break_check(40)
    pdf.section_title("Current Cycle Position (Early 2026)")
    pdf.bullet("AI (GPU, HBM, CoWoS): demand exceeds supply, pricing strong")
    pdf.bullet("Mobile/PC: mild recovery from 2024 bottom, AI phone/PC upgrade cycle")
    pdf.bullet("Auto/Industrial: destocking 2023-24, gradual recovery 2025")
    pdf.bullet("Mature foundry: overcapacity pressure from China expansion")
    pdf.bullet("Memory: HBM strong; traditional DRAM/NAND recovering with supply discipline")

    # ============ CHAPTER 10 ============
    pdf.add_page()
    pdf.chapter_title("Chapter 10: Key Risks & Challenges")

    pdf.section_title("Risk 1: Geopolitical Escalation")
    pdf.table(
        ["Scenario", "Probability", "Impact"],
        [
            ["Further China export restrictions", "High", "ASML/Lam/AMAT China rev -15-25%"],
            ["Taiwan Strait tensions escalate", "Medium", "Global chip shortage panic"],
            ["US demands allied export bans", "High", "Japan/Netherlands equip makers hit"],
            ["China full self-sufficiency", "Low(short)", "Reshapes global competition"],
        ],
        [55, 35, 100],
    )
    pdf.bold_body("Taiwan Risk:")
    pdf.bullet("TSMC produces ~60% of global chips and ~90% of advanced chips")
    pdf.bullet("Any supply disruption: smartphone production -60%, AI chips to zero, trillions in losses")

    pdf.section_title("Risk 2: AI Demand Sustainability")
    pdf.bullet("Is AI capex sustainable? If ROI disappoints, tech giants may cut spending")
    pdf.bullet("NVIDIA pricing (H100 ~$30K, B100 ~$60K): will competition erode pricing power?")
    pdf.bullet("Alternatives (Google TPU, AWS Trainium, AMD MI300, custom ASICs): market share threat")

    pdf.section_title("Risk 3: China Mature Node Overcapacity")
    pdf.bullet("China adding ~30 new fabs in 2024-2026, focused on 28nm-55nm")
    pdf.bullet("Could trigger global mature-node price war")
    pdf.bullet("Most impacted: UMC, GlobalFoundries, TSMC mature lines")

    pdf.section_title("Risk 4: Technical Bottlenecks")
    pdf.table(
        ["Challenge", "Current State", "Mitigation"],
        [
            ["Moore's Law slowing", "Perf gain: 40%->15-20%/gen", "Chiplet, 3D packaging"],
            ["EUV cost explosion", "High-NA: $350-400M/unit", "Only few can afford"],
            ["Power wall", "AI chips: 500-1000W", "Liquid cooling, new arch"],
            ["Yield challenges", "2nm GAA yield issues", "Time and experience"],
        ],
        [45, 60, 85],
    )

    pdf.section_title("Risk 5: Cyclicality")
    pdf.code_block(
        "2018-19: Trade war + memory downturn\n"
        "2020:    COVID shock then demand surge\n"
        "2021:    Global chip shortage, capacity buildout\n"
        "2022-23: Inventory glut, prices crash (memory -50%+)\n"
        "2024-25: AI-driven recovery\n"
        "2026-?:  If AI spending slows...?"
    )

    # ============ CHAPTER 11 ============
    pdf.add_page()
    pdf.chapter_title("Chapter 11: Investment Opportunities & Thesis")

    pdf.section_title("11.1 Investment Framework: By Certainty & Time Horizon")
    pdf.sub_section("High Certainty / Short-Term (1-2 years)")
    pdf.table(
        ["Opportunity", "Key Picks", "Thesis"],
        [
            ["AI compute demand", "NVDA, AVGO, MRVL", "Training/inference still exploding"],
            ["HBM undersupply", "SK Hynix", "HBM margin 70%+, expanding"],
            ["CoWoS bottleneck", "TSM (TSMC)", "Advanced pkg = scarce resource"],
            ["EUV equipment demand", "ASML", "High-NA EUV, backlog >$30B"],
        ],
        [50, 45, 95],
    )

    pdf.sub_section("High Certainty / Medium-Term (2-5 years)")
    pdf.table(
        ["Opportunity", "Key Picks", "Thesis"],
        [
            ["AI inference market", "NVDA, AVGO, MRVL", "Inference may exceed training"],
            ["Auto semiconductors", "ON, MBLY, ADI, NXPI", "EV + ADAS penetration"],
            ["SiC wide bandgap", "WOLF, ON, STM", "EV power demand"],
            ["Mature node consolidation", "GFS, UMC", "Stronger after price war"],
        ],
        [50, 50, 90],
    )

    pdf.sub_section("Medium Certainty / Long-Term (5-10 years)")
    pdf.table(
        ["Opportunity", "Key Picks", "Thesis"],
        [
            ["Edge AI / On-device", "QCOM, ARM", "AI moves from cloud to edge"],
            ["Silicon photonics", "AVGO, MRVL, LITE", "DC optical interconnect"],
            ["Chiplet ecosystem", "AMD, SNPS, CDNS", "UCIe standardization"],
            ["Quantum computing", "IONQ, IBM", "Very long-term, high risk"],
        ],
        [50, 50, 90],
    )

    pdf.page_break_check(60)
    pdf.section_title("11.2 Seven Core Investment Theses")

    pdf.bold_body('Thesis 1: "Shovel Sellers" > "Gold Miners"')
    pdf.body(
        "Chip designers win and lose, but equipment and EDA companies sell to ALL of them. "
        "ASML, LRCX, AMAT, KLAC, SNPS, CDNS benefit regardless of who wins. "
        "But valuations are already rich."
    )

    pdf.bold_body("Thesis 2: TSMC = Semiconductor Infrastructure")
    pdf.body(
        "Like AWS for the internet era - everyone runs on it. "
        "Advanced process + advanced packaging = double monopoly. "
        "Risk: Taiwan geopolitics (mitigated by US/Japan/EU fab buildout)."
    )

    pdf.bold_body("Thesis 3: AI Chain Investment Priority")
    pdf.code_block("GPU(NVDA) > HBM(SKH) > Foundry(TSM) > Pkg(CoWoS) > Equipment(ASML) > Materials")
    pdf.body("Closer to demand = higher beta; closer to upstream = higher stability.")

    pdf.bold_body("Thesis 4: Memory = High-Beta Cyclical")
    pdf.body(
        "SK Hynix, Samsung, Micron: buy at cycle bottom, sell at top. "
        "HBM gives SK Hynix structural premium. "
        "Micron (MU) as only US memory company has policy support premium."
    )

    pdf.bold_body("Thesis 5: Auto Semiconductors = Slow Bull")
    pdf.body(
        "Slower than AI but higher certainty. Infineon, NXP, ON Semi, STMicro are core picks. "
        "SiC is the fastest-growing sub-sector."
    )

    pdf.bold_body('Thesis 6: EDA/IP = "Utilities", Hold Long-Term')
    pdf.body(
        "Synopsys, Cadence, ARM have the closest business model to SaaS. "
        "High subscription revenue, high stickiness, high margins. "
        "Expensive (P/E ~50-60x) but arguably deserved."
    )

    pdf.bold_body("Thesis 7: Don't Ignore Mature Node Cash Flows")
    pdf.body(
        "UMC, GlobalFoundries: fully depreciated = high profit margins. "
        "Auto/industrial long-tail demand provides floor. Risk: China capacity flood."
    )

    pdf.page_break_check(70)
    pdf.section_title("11.3 My Top 5 Picks (As a Fab Owner)")

    pdf.bold_body("1. TSMC (TSM)")
    pdf.body(
        "The safest semiconductor investment. Advanced process monopoly + advanced packaging scarcity + "
        "AI super cycle's biggest beneficiary. 2nm and A14 roadmap is clear. Only risk: Taiwan."
    )
    pdf.bold_body("2. ASML")
    pdf.body(
        "Irreplaceable equipment company. High-NA EUV is the only production solution. "
        "Order backlog extends to 2027+. Less cyclical than peers (perpetual undersupply)."
    )
    pdf.bold_body("3. NVIDIA (NVDA) or Broadcom (AVGO)")
    pdf.body(
        "Two AI chip routes: general GPU vs custom ASIC. NVDA has deep ecosystem moat but expensive valuation. "
        "AVGO builds custom AI ASICs for Google/Meta plus VMware software. Both are strong."
    )
    pdf.bold_body("4. SK Hynix (000660.KS)")
    pdf.body(
        "Absolute HBM leader. AI chips need as much HBM as GPU. HBM margins far exceed normal memory. "
        "Korean market discount provides additional margin of safety."
    )
    pdf.bold_body("5. ARM Holdings (ARM)")
    pdf.body(
        "Long-term beneficiary of AI going to the edge. Whether AI PC, AI phone, or AI car, "
        "ARM architecture is everywhere. Pure IP company = zero manufacturing risk. "
        "But current valuation is very rich."
    )

    # ============ APPENDIX ============
    pdf.add_page()
    pdf.chapter_title("Appendix: Key Company Reference")

    pdf.section_title("Design (Fabless / System Custom)")
    pdf.table(
        ["Company", "Ticker", "Products", "2025 Rev", "Process"],
        [
            ["NVIDIA", "NVDA", "GPU, AI Accelerator", "~$130B", "5/4nm TSMC"],
            ["Broadcom", "AVGO", "Network, ASIC, VMware", "~$51B", "5/3nm TSMC"],
            ["AMD", "AMD", "CPU, GPU, FPGA", "~$26B", "5/4/3nm TSMC"],
            ["Qualcomm", "QCOM", "Mobile SoC, RF", "~$42B", "4nm TSMC/SS"],
            ["MediaTek", "2454.TW", "Mobile/IoT SoC", "~$18B", "4/3nm TSMC"],
            ["Marvell", "MRVL", "DC, Custom ASIC", "~$6B", "5/3nm TSMC"],
        ],
        [28, 28, 48, 28, 38, 20],
    )

    pdf.section_title("Manufacturing (Foundry / IDM)")
    pdf.table(
        ["Company", "Ticker", "Model", "Best Node", "2025 Rev"],
        [
            ["TSMC", "TSM", "Pure-play", "3nm/2nm", "~$90B"],
            ["Samsung", "005930.KS", "IDM+Foundry", "3nm GAA", "~$240B(group)"],
            ["Intel", "INTC", "IDM+Foundry", "Intel 18A", "~$54B"],
            ["GlobalFoundries", "GFS", "Pure-play", "12nm", "~$7.5B"],
            ["SMIC", "0981.HK", "Pure-play", "7nm(DUV)", "~$8B"],
            ["UMC", "UMC", "Pure-play", "14nm", "~$7B"],
        ],
        [36, 32, 30, 32, 34, 26],
    )

    pdf.section_title("Equipment")
    pdf.table(
        ["Company", "Ticker", "Core Equipment", "2025 Rev", "Share"],
        [
            ["ASML", "ASML", "EUV/DUV Litho", "~$30B", "Litho ~90%"],
            ["Applied Materials", "AMAT", "Dep, Etch, CMP", "~$28B", "Overall #1"],
            ["Lam Research", "LRCX", "Etch, Deposition", "~$18B", "Etch ~45%"],
            ["Tokyo Electron", "8035.T", "Coater/Dev, Dep", "~$18B", "Coater ~90%"],
            ["KLA", "KLAC", "Inspection, Metrology", "~$11B", "Inspect ~55%"],
        ],
        [38, 25, 42, 28, 37, 20],
    )

    pdf.page_break_check(50)
    pdf.section_title("Memory")
    pdf.table(
        ["Company", "Ticker", "Products", "2025 Rev", "HBM Rank"],
        [
            ["SK Hynix", "000660.KS", "DRAM, HBM, NAND", "~$55B", "#1"],
            ["Samsung", "005930.KS", "DRAM, HBM, NAND", "~$70B(semi)", "#2"],
            ["Micron", "MU", "DRAM, HBM, NAND", "~$30B", "#3"],
        ],
        [30, 32, 48, 40, 40],
    )

    pdf.section_title("EDA / IP")
    pdf.table(
        ["Company", "Ticker", "Products", "2025 Rev", "Gross Margin"],
        [
            ["Synopsys", "SNPS", "EDA + IP", "~$6.5B", "~80%"],
            ["Cadence", "CDNS", "EDA + IP", "~$4.5B", "~88%"],
            ["ARM Holdings", "ARM", "CPU Architecture IP", "~$3.8B", "~95%"],
        ],
        [35, 25, 50, 35, 45],
    )

    pdf.section_title("Analog / Power / Automotive")
    pdf.table(
        ["Company", "Ticker", "Products", "2025 Rev"],
        [
            ["Texas Instruments", "TXN", "Analog IC", "~$16B"],
            ["Analog Devices", "ADI", "High-perf Analog", "~$10B"],
            ["Infineon", "IFNNY", "Power semi, Auto", "~$17B"],
            ["NXP", "NXPI", "Auto MCU/Processor", "~$13B"],
            ["ON Semi", "ON", "SiC, Power, Imaging", "~$7.5B"],
            ["STMicro", "STM", "Auto, Industrial", "~$14B"],
        ],
        [42, 25, 63, 40, 20],
    )

    # Final note
    pdf.ln(10)
    pdf.set_font("CJK", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 4, (
        "This report is based on public information and industry experience. It does not constitute "
        "investment advice. The semiconductor industry is highly cyclical and technology changes rapidly. "
        "Please conduct your own due diligence before investing. All financial data are estimates."
    ), align="C")

    # Save
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    pdf.output(OUTPUT_PATH)
    print(f"PDF saved to: {OUTPUT_PATH}")
    print(f"Pages: {pdf.page_no()}")


if __name__ == "__main__":
    build_pdf()
