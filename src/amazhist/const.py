#!/usr/bin/env python3

ARCHIVE_LABEL = "archive"

ORDER_COUNT_PER_PAGE = 10
HIST_URL = "https://www.amazon.co.jp/your-orders/orders"
HIST_URL_BY_YEAR = "https://www.amazon.co.jp/your-orders/orders?timeFilter=year-{year}&startIndex={start}"
HIST_URL_IN_ARCHIVE = "https://www.amazon.co.jp/your-orders/orders?timeFilter=archived&startIndex={start}"
HIST_URL_BY_ORDER_NO = "https://www.amazon.co.jp/gp/your-account/order-details/?orderID={no}"
