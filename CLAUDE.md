# Project Notes

## TODO

- **dcf_screener.py: 不适合 DCF 的公司应该报错/跳过**
  - 银行 (BANK)、保险 (INSURANCE) 等金融公司不适合用 FCF-based DCF 估值
  - 当 `infer_sector_from_facts()` 返回 BANK 或 INSURANCE 时，screener 应该跳过该公司并记录原因，而不是输出不可靠的估值结果
  - 可考虑的过滤条件：SIC code 6000-6499（金融服务）、REIT、负 FCF 连续多年的公司
