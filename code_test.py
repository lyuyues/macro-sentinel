#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import pandas as pd
import yfinance as yf


# code_test_stooq.py
from dcf_utils import get_latest_price_stooq  # 或直接复制上面函数

print(get_latest_price_stooq("AAPL"))
print(get_latest_price_stooq("NVDA"))