#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
データをシリアライズしてファイルに保存します．

Usage:
  serializer.py
"""

import logging
import pathlib
import pickle
import tempfile
import traceback


def store(file_path_str, data):
    logging.debug("Store {file_path}".format(file_path=file_path_str))

    file_path = pathlib.Path(file_path_str)
    try:
        f = tempfile.NamedTemporaryFile(dir=str(file_path.parent), delete=False)
        pickle.dump(data, f)
        f.close()

        # NOTE: Windows だと，存在するファイル名には rename できないので一旦別の名前に変えておく．
        if file_path.exists():
            file_path.rename(file_path.with_suffix(".old"))
            file_path = pathlib.Path(file_path_str)

        pathlib.Path(f.name).rename(file_path)
    except:
        logging.error(traceback.format_exc())


def load(file_path, init_value={}):
    logging.debug("Load {file_path}".format(file_path=file_path))

    if not file_path.exists():
        return init_value

    try:
        with open(file_path, "rb") as f:
            data = init_value.copy()
            data.update(pickle.load(f))
            return data
    except:
        logging.error(traceback.format_exc())
        return init_value


if __name__ == "__main__":
    import logger
    from docopt import docopt

    args = docopt(__doc__)

    logger.init("test", level=logging.INFO)

    data = {"a": 1.0}

    f = tempfile.NamedTemporaryFile()
    file_path = pathlib.Path(f.name)
    store(file_path, data)
    f.flush()

    assert load(file_path) == data
