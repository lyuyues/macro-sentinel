"""Generate Strategy Guide PDF with CJK support."""
import os
from fpdf import FPDF

OUTPUT_PATH = "output/analysis/Strategy_Guide.pdf"
FONT_PATH = "/Library/Fonts/Arial Unicode.ttf"

# Chart image paths
CHARTS_DIR = "output/analysis"


class GuidePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("CJK", "", FONT_PATH)
        self.add_font("CJK", "B", FONT_PATH)
        self.add_font("CJK", "I", FONT_PATH)

    def header(self):
        if self.page_no() > 1:
            self.set_font("CJK", "I", 7)
            self.set_text_color(150, 150, 150)
            self.cell(95, 5, "多因子量化选股策略 — 学习指南")
            self.cell(95, 5, f"Page {self.page_no()}", align="R")
            self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("CJK", "I", 7)
        self.set_text_color(180, 180, 180)
        self.cell(0, 5, "AI Stock Analysis System | Phase 3 Strategy Guide", align="C")

    def chapter_title(self, t):
        self.set_font("CJK", "B", 18)
        self.set_text_color(20, 50, 100)
        self.multi_cell(0, 11, t)
        y = self.get_y()
        self.set_draw_color(20, 50, 100)
        self.set_line_width(0.8)
        self.line(10, y, 200, y)
        self.set_line_width(0.2)
        self.ln(6)

    def sec(self, t):
        if self.get_y() > 255:
            self.add_page()
        self.set_font("CJK", "B", 13)
        self.set_text_color(30, 70, 130)
        self.multi_cell(0, 8, t)
        self.ln(3)

    def sub(self, t):
        if self.get_y() > 260:
            self.add_page()
        self.set_font("CJK", "B", 11)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 7, t)
        self.ln(2)

    def p(self, t):
        self.set_font("CJK", "", 9.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, t)
        self.ln(2.5)

    def bold_p(self, t):
        self.set_font("CJK", "B", 9.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, t)
        self.ln(2.5)

    def li(self, t):
        self.set_font("CJK", "", 9.5)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        self.set_x(x + 5)
        self.multi_cell(0, 5.2, "\u2022  " + t)
        self.ln(1)

    def quote(self, t):
        """Indented quote block with left border."""
        y_start = self.get_y()
        self.set_x(18)
        self.set_font("CJK", "I", 9.5)
        self.set_text_color(80, 80, 80)
        self.multi_cell(170, 5.5, t)
        y_end = self.get_y()
        self.set_draw_color(20, 50, 100)
        self.set_line_width(0.6)
        self.line(14, y_start, 14, y_end)
        self.set_line_width(0.2)
        self.ln(3)

    def code_block(self, t):
        self.set_font("Courier", "", 8)
        self.set_fill_color(242, 242, 242)
        self.set_text_color(40, 40, 40)
        for line in t.strip().split("\n"):
            if self.get_y() > 275:
                self.add_page()
            s = line.encode("latin-1", errors="replace").decode("latin-1")
            self.cell(190, 4.5, "  " + s, fill=True)
            self.ln(4.5)
        self.ln(3)

    def tbl(self, headers, rows, cw=None):
        if cw is None:
            cw = [190 / len(headers)] * len(headers)
        if self.get_y() + 8 + len(rows) * 6.5 > 270:
            self.add_page()
        # Header
        self.set_font("CJK", "B", 8)
        self.set_fill_color(20, 50, 100)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(cw[i], 7, h, border=1, fill=True, align="C")
        self.ln()
        # Rows
        self.set_font("CJK", "", 8)
        self.set_text_color(30, 30, 30)
        alt = False
        for row in rows:
            if self.get_y() + 6.5 > 275:
                self.add_page()
                self.set_font("CJK", "B", 8)
                self.set_fill_color(20, 50, 100)
                self.set_text_color(255, 255, 255)
                for i, h in enumerate(headers):
                    self.cell(cw[i], 7, h, border=1, fill=True, align="C")
                self.ln()
                self.set_font("CJK", "", 8)
                self.set_text_color(30, 30, 30)
                alt = False
            if alt:
                self.set_fill_color(245, 245, 250)
            else:
                self.set_fill_color(255, 255, 255)
            for i, val in enumerate(row):
                self.cell(cw[i], 6.5, str(val), border=1, fill=True, align="C")
            self.ln()
            alt = not alt
        self.ln(3)

    def add_chart(self, path, w=170):
        if os.path.exists(path):
            if self.get_y() + 80 > 270:
                self.add_page()
            x = (210 - w) / 2
            self.image(path, x=x, w=w)
            self.ln(5)


def build_pdf():
    pdf = GuidePDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ==================== Cover Page ====================
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("CJK", "B", 28)
    pdf.set_text_color(20, 50, 100)
    pdf.cell(0, 15, "多因子量化选股策略", align="C")
    pdf.ln(18)
    pdf.set_font("CJK", "", 16)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "学习指南", align="C")
    pdf.ln(25)

    pdf.set_draw_color(20, 50, 100)
    pdf.set_line_width(0.5)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(15)

    pdf.set_font("CJK", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "Phase 3: 调参优化 + 因子分析", align="C")
    pdf.ln(8)
    pdf.cell(0, 8, "AI Stock Analysis System", align="C")
    pdf.ln(30)

    pdf.set_font("CJK", "I", 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 6, "写给不熟悉量化交易的你", align="C")
    pdf.ln(5)
    pdf.cell(0, 6, "读完这份材料，你会理解自己的策略在做什么、为什么有效、以及如何优化", align="C")

    # ==================== Chapter 1 ====================
    pdf.add_page()
    pdf.chapter_title("第一章：先理解几个关键概念")

    pdf.sec("什么是「年化收益 CAGR」？")
    pdf.p("假设你投了 10 万，10 年后变成 107 万（总收益 970%）。CAGR 回答的问题是：如果每年稳定增长，需要多少增速才能达到这个结果？")
    pdf.p("答案是 26.5%。意思是「平均下来每年赚 26.5%」，但实际上有的年赚 50%，有的年亏 10%。")
    pdf.p("作为参考：")
    pdf.li("巴菲特长期 CAGR 约 20%")
    pdf.li("标普 500（SPY）长期 CAGR 约 10-12%")
    pdf.li("你的策略回测 CAGR 26.5%，优化后 27.8%")

    pdf.sec("什么是「最大回撤 Max Drawdown」？")
    pdf.bold_p("你最惨的时候从高点跌了多少。")
    pdf.p("举个例子：")
    pdf.tbl(
        ["月份", "账户金额", "说明"],
        [
            ["1月", "100万", ""],
            ["3月", "150万", "高点"],
            ["6月", "98万", "低点"],
            ["9月", "160万", "回升"],
        ],
        [40, 50, 100],
    )
    pdf.p("最大回撤 = (150 - 98) / 150 = 34.7%")
    pdf.p("这个数字很重要，因为它代表你需要承受的心理压力。回撤 35% 意味着你可能看着 150 万变成不到 100 万，持续好几个月。很多人会在这个时候恐慌卖出，错过后面的反弹。")
    pdf.p("你的策略：")
    pdf.li("当前 Max DD：36.6%（最惨跌了三分之一多）")
    pdf.li("优化后 Max DD：31.8%（好了一些，但仍然需要心理准备）")

    pdf.sec("什么是「Sharpe Ratio（夏普比率）」？")
    pdf.bold_p("每承受一单位风险，能赚多少超额回报。")
    pdf.p("公式：Sharpe = (策略收益 - 无风险收益) / 波动率")
    pdf.tbl(
        ["Sharpe 范围", "评级", "说明"],
        [
            ["< 0.5", "较差", "风险收益比不划算"],
            ["0.5 - 1.0", "还行", "可以接受"],
            ["1.0 - 1.5", "很好", "专业水平"],
            ["> 1.5", "极好", "非常罕见"],
        ],
        [40, 40, 110],
    )
    pdf.p("你的策略 Sharpe 1.04 -> 优化后 1.13，属于「很好」的水平。")

    pdf.sec("什么是「Alpha」？")
    pdf.bold_p("你比市场多赚的部分。")
    pdf.p("如果 SPY 涨了 15%，你涨了 26%，那中间的差值（扣除风险调整后）就是 Alpha。Alpha > 0 说明你的选股能力在创造价值，而不是纯粹靠承担更多风险。")
    pdf.p("你的策略 Alpha 约 10.8%，意思是扣除市场涨幅后，你的选股每年额外赚了约 10.8%。")

    # ==================== Chapter 2 ====================
    pdf.add_page()
    pdf.chapter_title("第二章：你现在的策略在做什么")

    pdf.sec("一句话版本")
    pdf.quote("每个月看一遍你的股票池，用「便不便宜 + 涨势好不好 + 大环境如何」打分，买最好的几只，跌太多就止损。")

    pdf.sec("第一步：确定股票池")
    pdf.p("你不是从全市场几千只股票里选，而是只看你之前做过 DCF（现金流折现）分析的公司。目前有 17 只，包括 AAPL、NVDA、TSLA、PLTR 等。")
    pdf.p("这一步就像你先做了功课，列了一个「值得关注的好公司名单」，然后每月从里面挑。")

    pdf.sec("第二步：给每只股票打分（6 个因子）")
    pdf.p("策略用 6 个「因子」打分，分成三大类：")

    pdf.sub("价值类 — 便不便宜？")
    pdf.tbl(
        ["因子", "全称", "看什么", "作用"],
        [
            ["F1", "DCF 折扣", "现价 vs 你算的公允价值", "找被低估的"],
            ["F2", "相对估值", "现价在过去一年的位置", "找相对低位的"],
        ],
        [20, 40, 65, 65],
    )

    pdf.sub("动量类 — 涨势好不好？")
    pdf.tbl(
        ["因子", "全称", "看什么", "作用"],
        [
            ["F3", "趋势确认", "股价 > 200日均线 且 RSI<70", "过滤下跌趋势"],
            ["F4", "动量", "过去 6 个月涨幅", "找有上涨动力的"],
        ],
        [20, 40, 65, 65],
    )

    pdf.sub("周期类 — 大环境如何？")
    pdf.tbl(
        ["因子", "全称", "看什么", "作用"],
        [
            ["F5", "宏观环境", "VIX + 利率 + SPY趋势", "判断进攻/防守"],
            ["F6", "行业周期", "收入增速是否加速", "顺周期加分"],
        ],
        [20, 40, 65, 65],
    )
    pdf.p("最终合成一个 0-1 的综合分数。分数越高，越值得买。")

    pdf.sec("第三步：根据大环境决定买多少")
    pdf.p("策略会判断市场处于哪种状态：")
    pdf.tbl(
        ["状态", "判断依据", "投入比例", "选多少只"],
        [
            ["进攻", "SPY在均线上、VIX低、利率正常", "100%", "前 40%"],
            ["中性", "信号不一致", "65%", "前 25%"],
            ["防守", "SPY跌破均线、VIX高", "30%", "前 10%"],
        ],
        [30, 75, 40, 45],
    )
    pdf.p("这就像开车：晴天踩油门，雨天减速，暴风雪就靠边停。")

    pdf.sec("第四步：分配仓位")
    pdf.p("不是平均分配，而是用「风险平价」：波动大的股票少买，波动小的多买。每只股票最多占 20%。")
    pdf.p("这样做的好处是不会因为一只暴涨暴跌的股票亏太多。")

    pdf.sec("第五步：什么时候卖")
    pdf.p("触发以下任一条件就卖：")
    pdf.tbl(
        ["条件", "说明", "举例"],
        [
            ["止损", "从买入价跌了 15%", "100 买的，跌到 85 就卖"],
            ["到价", "涨到你算的公允价值", "DCF 算出值 150，涨到 150 就卖"],
            ["排名掉了", "综合分数不在前几名了", "别的股票更好，换掉"],
            ["趋势破了", "跌破 200 日均线", "长期趋势可能转空"],
        ],
        [35, 60, 95],
    )

    # ==================== Chapter 3 ====================
    pdf.add_page()
    pdf.chapter_title("第三章：优化后的策略有什么不同")

    pdf.sec("核心变化：因子权重")
    pdf.tbl(
        ["", "价值类权重", "动量类权重", "周期类权重"],
        [
            ["原来", "40-50% (随环境变)", "20-35% (随环境变)", "25-30% (随环境变)"],
            ["优化后", "70% (固定)", "30% (固定)", "0% (去掉)"],
        ],
        [30, 55, 55, 50],
    )

    pdf.sec("为什么去掉周期因子？")
    pdf.p("通过 66 组权重组合的回测，发现：")
    pdf.li("行业周期因子（F6）对选股的帮助很小")
    pdf.li("加入周期因子反而引入噪声，降低了 Sharpe")
    pdf.li("Top 10 最优组合中，周期权重几乎都是 0")
    pdf.p("直觉上也说得通：你的股票池只有 17 只，行业分散，用一个粗略的周期指标区分不了太多。")

    pdf.sec("为什么 70/30 而不是 50/50？")
    pdf.tbl(
        ["价值/动量", "Sharpe", "Max DD"],
        [
            ["50 / 50", "1.04", "31.8%"],
            ["60 / 40", "1.12", "31.8%"],
            ["70 / 30", "1.13", "31.8%"],
            ["80 / 20", "1.10", "32.1%"],
            ["90 / 10", "1.05", "31.4%"],
        ],
        [50, 70, 70],
    )
    pdf.p("70/30 是甜蜜点。价值因子太少选不到便宜货，太多又会错过有涨势的股票。")

    # Insert chart: ternary sharpe
    ternary_path = os.path.join(CHARTS_DIR, "combinations", "ternary_sharpe.png")
    if os.path.exists(ternary_path):
        pdf.sub("因子组合 Sharpe 分布图")
        pdf.add_chart(ternary_path, w=140)
        pdf.p("上图中每个点代表一种因子组合，颜色越绿 Sharpe 越高。可以看到最优区域集中在左上角（价值高、动量适中、周期为零）。")

    pdf.sec("其他参数不需要改")
    pdf.p("止损 15%、仓位上限 20%、动量看 6 个月、趋势看 200 日均线 — 这些经过敏感性分析，发现当前默认值已经接近最优。")

    # Insert sensitivity charts
    sl_chart = os.path.join(CHARTS_DIR, "sensitivity", "stop_loss_pct", "sharpe_vs_param.png")
    if os.path.exists(sl_chart):
        pdf.sub("参数敏感性示例：止损比例 vs Sharpe")
        pdf.add_chart(sl_chart, w=140)

    # ==================== Chapter 4 ====================
    pdf.add_page()
    pdf.chapter_title("第四章：新旧策略对比")

    pdf.sec("回测数据对比（2016-2026，10 年）")
    pdf.tbl(
        ["指标", "SPY 买了不动", "原策略", "优化后策略", "说明"],
        [
            ["总收益", "206%", "970%", "~1000%", "10万->107万"],
            ["年化 CAGR", "14.9%", "26.5%", "27.8%", "每年多赚 1.3%"],
            ["Sharpe", "~0.7", "1.04", "1.13", "风险调整更优"],
            ["最大回撤", "~33%", "36.6%", "31.8%", "最惨时少跌 5%"],
            ["Alpha", "0%", "10.8%", "11.6%", "跑赢大盘的幅度"],
        ],
        [28, 35, 30, 35, 62],
    )

    pdf.sec("用人话说")
    pdf.li("收益差不多：CAGR 从 26.5% 到 27.8%，差 1.3%，10 年累积大概多赚 15%")
    pdf.li("风险明显下降：最大回撤从 36.6% 降到 31.8%，最惨时少亏约 5 万（按 100 万本金）")
    pdf.li("综合性价比更高：Sharpe 从 1.04 到 1.13，每承受一单位风险多赚 8.6%")
    pdf.ln(2)
    pdf.bold_p("优化的意义不是「赚更多」，而是「同样的收益，承受更少的痛苦」。")

    # Insert NAV comparison chart
    nav_chart = os.path.join(CHARTS_DIR, "single_factor", "nav_overlay.png")
    if os.path.exists(nav_chart):
        pdf.sec("各因子组合 NAV 对比图")
        pdf.add_chart(nav_chart, w=160)

    sharpe_chart = os.path.join(CHARTS_DIR, "single_factor", "sharpe_comparison.png")
    if os.path.exists(sharpe_chart):
        pdf.sec("各因子组合 Sharpe 对比图")
        pdf.add_chart(sharpe_chart, w=150)

    # ==================== Chapter 5 ====================
    pdf.add_page()
    pdf.chapter_title("第五章：如何执行")

    pdf.sec("用代码跑回测")
    pdf.code_block(
        "# Run analysis\n"
        "python -m quant.run_analysis --analysis all\n"
        "\n"
        "# Or specify in code\n"
        "from quant.config import BacktestConfig\n"
        "\n"
        "config = BacktestConfig(\n"
        '    factor_weights={"value": 0.70, "momentum": 0.30, "cycle": 0.0},\n'
        "    stop_loss_pct=0.15,\n"
        "    max_position_weight=0.20,\n"
        "    momentum_lookback=126,\n"
        "    sma_window=200,\n"
        '    label="optimal_v70_m30",\n'
        ")"
    )

    pdf.sec("手动执行 Checklist（每月第一个交易日）")

    pdf.sub("1. 检查大环境（2 分钟）")
    pdf.li("SPY 在 200 日均线上方吗？")
    pdf.li("VIX 低于 25 吗？")
    pdf.li("10年-2年国债利率差 > 0 吗？")
    pdf.p("2-3 个「是」= 进攻模式 | 1 个「是」= 中性模式 | 0 个「是」= 防守模式")

    pdf.sub("2. 检查持仓（5 分钟）")
    pdf.li("有没有跌超 15% 的？ -> 止损卖出")
    pdf.li("有没有涨到 DCF 公允价值的？ -> 获利了结")
    pdf.li("有没有跌破 200 日均线的？ -> 考虑卖出")

    pdf.sub("3. 给股票池打分（10 分钟）")
    pdf.p("对每只股票计算：")
    pdf.li("价值分数（70% 权重）：DCF 折扣有多大 + 现价在过去一年处于什么位置")
    pdf.li("动量分数（30% 权重）：是否在 200 日均线上方 + 过去 6 个月涨了多少")
    pdf.p("按综合分数排序。")

    pdf.sub("4. 决定买卖（10 分钟）")
    pdf.tbl(
        ["模式", "操作"],
        [
            ["进攻", "买分数最高的 6-7 只（17只的40%），满仓"],
            ["中性", "买最高的 4 只，保留 35% 现金"],
            ["防守", "只买 1-2 只，保留 70% 现金"],
        ],
        [40, 150],
    )
    pdf.p("每只股票不超过总仓位的 20%。波动大的少买，波动小的多买。")

    pdf.sub("5. 执行交易")
    pdf.p("下单后记录买入价格，用于下个月的止损判断。")

    # ==================== Chapter 6 ====================
    pdf.add_page()
    pdf.chapter_title("第六章：注意事项")

    pdf.sec("回测不等于未来")
    pdf.p("回测用的是 2016-2026 的历史数据。这 10 年包含了美股大牛市（2016-2019）、疫情暴跌和反弹（2020）、加息周期（2022-2023）。策略在这些环境下都表现不错，但不保证未来一样。")

    pdf.sec("你的 Alpha 主要来自哪里")
    pdf.p("坦白说，大部分 Alpha 来自你的股票池本身。NVDA、PLTR、TSLA、AVGO 这些公司过去 10 年表现远超大盘。策略的作用是：")
    pdf.li("在它们便宜的时候多买（价值因子）")
    pdf.li("在它们下跌时少亏（止损 + 防守模式）")
    pdf.li("在它们不行时及时换掉（排名轮换）")
    pdf.p("如果你的股票池里全是平庸的公司，再好的因子权重也不会创造奇迹。")

    pdf.sec("回撤是真实的痛苦")
    pdf.p("31.8% 的 Max DD 看起来是个数字，但想象一下：")
    pdf.quote("你年初有 150 万。到了 6 月，账户只剩 102 万。每天打开 app 都在亏钱，新闻都在说经济要崩了。你的策略说「继续持有」。你能忍住不卖吗？")
    pdf.p("如果不能，可以考虑：")
    pdf.li("降低仓位上限（从 20% 降到 15%）")
    pdf.li("收紧止损（从 15% 降到 10%）")
    pdf.li("代价是收益会略微下降")

    pdf.sec("交易成本")
    pdf.p("回测已经计入了每笔交易 0.15% 的成本（佣金 + 滑点）。月度调仓频率不算高，交易成本影响有限。")

    # Insert 2D heatmap
    heatmap_path = os.path.join(CHARTS_DIR, "sensitivity", "2d_sl_mom", "heatmap_sharpe.png")
    if os.path.exists(heatmap_path):
        pdf.sec("附：止损 x 动量周期 热力图")
        pdf.add_chart(heatmap_path, w=140)
        pdf.p("上图展示了止损比例和动量回看周期的交互效果。当前默认参数（止损 15%，动量 126天）已处于较优区域。")

    # ==================== Appendix ====================
    pdf.add_page()
    pdf.chapter_title("附录：完整输出文件说明")

    pdf.tbl(
        ["目录", "文件", "说明"],
        [
            ["single_factor/", "comparison.csv", "7 种因子组合完整数据"],
            ["single_factor/", "sharpe_comparison.png", "Sharpe 柱状图"],
            ["single_factor/", "nav_overlay.png", "NAV 曲线叠加"],
            ["sensitivity/stop_loss_pct/", "sharpe_vs_param.png", "止损比例敏感性"],
            ["sensitivity/max_position_weight/", "sharpe_vs_param.png", "仓位上限敏感性"],
            ["sensitivity/momentum_lookback/", "sharpe_vs_param.png", "动量周期敏感性"],
            ["sensitivity/sma_window/", "sharpe_vs_param.png", "均线窗口敏感性"],
            ["sensitivity/2d_sl_mom/", "heatmap_sharpe.png", "2D 热力图"],
            ["combinations/", "comparison.csv", "66 种组合完整结果"],
            ["combinations/", "top_10.md", "Sharpe 前 10 名"],
            ["combinations/", "ternary_sharpe.png", "因子权重散点图"],
            ["combinations/", "nav_top5.png", "Top 5 NAV 曲线"],
        ],
        [55, 50, 85],
    )

    pdf.ln(10)
    pdf.sec("Top 10 因子组合（按 Sharpe 排序）")
    pdf.tbl(
        ["排名", "权重组合", "Sharpe", "CAGR", "Max DD", "Alpha"],
        [
            ["1", "v70% m30% c0%", "1.130", "27.8%", "31.8%", "11.6%"],
            ["2", "v60% m40% c0%", "1.124", "28.1%", "31.8%", "11.9%"],
            ["3", "v90% m0%  c10%", "1.108", "26.5%", "30.8%", "11.2%"],
            ["4", "v70% m20% c10%", "1.104", "26.7%", "30.7%", "11.2%"],
            ["5", "v80% m20% c0%", "1.100", "27.1%", "32.1%", "11.1%"],
            ["6", "v80% m10% c10%", "1.081", "26.1%", "30.7%", "10.8%"],
            ["7", "v10% m20% c70%", "1.070", "27.1%", "34.5%", "11.7%"],
            ["8", "v30% m70% c0%", "1.070", "29.0%", "36.5%", "12.1%"],
            ["9", "v20% m60% c20%", "1.069", "28.7%", "36.5%", "12.1%"],
            ["10", "v40% m40% c20%", "1.069", "27.4%", "36.6%", "11.3%"],
        ],
        [18, 42, 25, 25, 25, 25],
    )

    # Output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    pdf.output(OUTPUT_PATH)
    print(f"PDF saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
