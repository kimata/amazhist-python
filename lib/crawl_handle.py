#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pathlib
import functools
import enlighten
import datetime

from selenium.webdriver.support.wait import WebDriverWait
from selenium_util import create_driver, clear_cache

import store_amazon_const
import serializer


def create(config):
    handle = {
        "progress_manager": enlighten.get_manager(),
        "progress_bar": {},
        "config": config,
    }

    load_order_info(handle)

    return handle


def get_selenium_driver(handle):
    if "selenium" in handle:
        return (handle["selenium"]["driver"], handle["selenium"]["wait"])
    else:
        driver = create_driver(
            pathlib.Path(os.path.dirname(__file__)).parent.name,
            pathlib.Path(os.path.dirname(__file__)).parent / handle["config"]["data"]["selenium"],
        )
        wait = WebDriverWait(driver, 5)

        clear_cache(driver)

        handle["selenium"] = {
            "driver": driver,
            "wait": wait,
        }

        return (driver, wait)


def record_item(handle, item):
    handle["order"]["item_list"].append(item)
    handle["order"]["order_no_stat"][item["no"]] = True


def get_item_list(handle):
    return sorted(handle["order"]["item_list"], key=lambda x: x["date"], reverse=True)


def get_last_item(handle, time_filter):
    return next(filter(lambda item: item["order_time_filter"] == time_filter, get_item_list(handle)), None)


def get_thubm_path(handle, asin):
    pathlib.Path(handle["config"]["data"]["cache"]["thumb"]).mkdir(parents=True, exist_ok=True)

    if asin is None:
        return None
    else:
        return pathlib.Path(handle["config"]["data"]["cache"]["thumb"]) / (asin + ".png")


def get_order_stat(handle, no):
    return no in handle["order"]["order_no_stat"]


def set_year_list(handle, year_list):
    handle["order"]["year_list"] = year_list


def set_order_count(handle, year, order_count):
    handle["order"]["year_count"][year] = order_count


def get_cache_last_modified(handle):
    return handle["order"]["last_modified"]


def get_order_count(handle, year):
    return handle["order"]["year_count"][year]


def get_total_order_count(handle):
    return functools.reduce(lambda a, b: a + b, handle["order"]["year_count"].values())


def get_year_list(handle):
    return handle["order"]["year_list"]


def set_progress_bar(handle, desc, total):
    BAR_FORMAT = (
        "{desc:21s}{desc_pad}{percentage:3.0f}% |{bar}| {count:5d} / {total:5d} "
        + "[{elapsed}<{eta}, {rate:6.2f}{unit_pad}{unit}/s]"
    )
    COUNTER_FORMAT = (
        "{desc:20s}{desc_pad}{count:5d} {unit}{unit_pad}[{elapsed}, {rate:6.2f}{unit_pad}{unit}/s]{fill}"
    )

    handle["progress_bar"][desc] = handle["progress_manager"].counter(
        total=total, desc=desc, bar_format=BAR_FORMAT, counter_format=COUNTER_FORMAT
    )


def set_status(handle, status):
    if "status" not in handle:
        handle["status"] = handle["progress_manager"].status_bar(
            status_format="Amazhist{fill}{status}{fill}{elapsed}",
            color="bold_bright_white_on_lightslategray",
            justify=enlighten.Justify.CENTER,
            status=status,
            autorefresh=True,
            min_delta=0.5,
        )
    else:
        handle["status"].update(status=status)


def finish(handle):
    if "selenium" in handle:
        handle["selenium"]["driver"].quit()
        handle.pop("selenium")

    handle["progress_manager"].stop()


def get_order_cache_path(handle):
    return pathlib.Path(os.path.dirname(__file__)).parent / handle["config"]["data"]["cache"]["order"]


def store_order_info(handle):
    handle["order"]["last_modified"] = datetime.datetime.now()

    # NOTE: 次回再開した時には巡回すべきなので削除しておく
    for time_filter in [datetime.datetime.now().year, store_amazon_const.ARCHIVE_LABEL]:
        if time_filter in handle["order"]["page_stat"]:
            del handle["order"]["page_stat"][time_filter]

    serializer.store(get_order_cache_path(handle), handle["order"])


def set_page_checked(handle, year, page):
    if year in handle["order"]["page_stat"]:
        handle["order"]["page_stat"][year][page] = True
    else:
        handle["order"]["page_stat"][year] = {page: True}


def get_page_checked(handle, year, page):
    if (year in handle["order"]["page_stat"]) and (page in handle["order"]["page_stat"][year]):
        return handle["order"]["page_stat"][year][page]
    else:
        return False


def set_year_checked(handle, year):
    handle["order"]["year_stat"][year] = True
    store_order_info(handle)


def get_year_checked(handle, year):
    return year in handle["order"]["year_stat"]


def load_order_info(handle):
    handle["order"] = serializer.load(
        get_order_cache_path(handle),
        {
            "year_list": [],
            "year_count": {},
            "year_stat": {},
            "page_stat": {},
            "item_list": [],
            "order_no_stat": {},
            "last_modified": datetime.datetime(1994, 7, 5),
        },
    )


def get_progress_bar(handle, desc):
    return handle["progress_bar"][desc]
