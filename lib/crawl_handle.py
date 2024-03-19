#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pathlib
import functools
import enlighten
import datetime

from selenium.webdriver.support.wait import WebDriverWait
from selenium_util import create_driver, clear_cache

import serializer

CACHE_FILE = "amazhist_cache.dat"


def create(config):
    driver = create_driver(
        os.path.splitext(__file__)[0],
        pathlib.Path(pathlib.Path(os.path.dirname(__file__))).parent / config["data"]["selenium"],
    )
    wait = WebDriverWait(driver, 5)

    clear_cache(driver)

    handle = {
        "selenium": {
            "driver": driver,
            "wait": wait,
        },
        "progress_manager": enlighten.get_manager(),
        "progress_bar": {},
        "config": config,
    }

    load_order_info(handle)

    return handle


def get_queue_dirver(handle):
    return (handle["selenium"]["driver"], handle["selenium"]["wait"])


def record_item(handle, item):
    handle["order"]["item_list"].append(item)
    handle["order"]["order_no_stat"][item["no"]] = True


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


def store_order_info(handle):
    handle["order"]["last_modified"] = datetime.datetime.now()

    cache_file = pathlib.Path(pathlib.Path(os.path.dirname(__file__))).parent / CACHE_FILE
    serializer.store(cache_file, handle["order"])


def set_year_checked(handle, year):
    # NOTE: 今年はまだ注文が増える可能性があるので，チェックしない．
    if year == datetime.datetime.now().year:
        return

    handle["order"]["year_stat"][year] = True
    store_order_info(handle)


def get_year_checked(handle, year):
    return year in handle["order"]["year_stat"]


def load_order_info(handle):
    cache_file = pathlib.Path(pathlib.Path(os.path.dirname(__file__))).parent / CACHE_FILE

    handle["order"] = serializer.load(
        cache_file,
        {
            "year_list": [],
            "year_count": {},
            "year_stat": {},
            "item_list": [],
            "order_no_stat": {},
            "last_modified": datetime.datetime(1994, 7, 5),
        },
    )


def get_progress_bar(handle, desc):
    return handle["progress_bar"][desc]
