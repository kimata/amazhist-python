#!/usr/bin/env python3

ORDER_COUNT_PER_PAGE = 10
HIST_URL = "https://www.amazon.co.jp/your-orders/orders"
HIST_URL_BY_YEAR = "https://www.amazon.co.jp/your-orders/orders?timeFilter=year-{year}&startIndex={start}"
HIST_URL_BY_ORDER_NO = "https://www.amazon.co.jp/gp/your-account/order-details/?orderID={no}"

# リトライ設定
RETRY_URL_ACCESS = 3
RETRY_LOGIN = 2
RETRY_CAPTCHA = 2
RETRY_FETCH = 2
RETRY_THUMBNAIL = 3
RETRY_CATEGORY = 2

RETRY_DELAY_DEFAULT = 1.0
RETRY_DELAY_TIMEOUT = 2.0

# エラータイプ
ERROR_TYPE_TIMEOUT = "timeout"
ERROR_TYPE_PARSE = "parse_error"
ERROR_TYPE_FETCH = "fetch_error"
