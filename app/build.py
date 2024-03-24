#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nuitka を使って，実行ファイルを生成します．

Usage:
  build.py
"""

import subprocess

JOBS = 16


def build():
    build_command = (
        "poetry run nuitka3 --follow-imports --include-package-data=selenium "
        "--product-name={name} --file-version={version} --product-version={version} "
        "--windows-icon-from-ico={icon_image} --macos-app-icon={icon_image} --jobs={jobs} "
        "--standalone --onefile --output-dir=build --script-name=app/amazhist.py"
    ).format(
        jobs=JOBS,
        name="amazhist",
        version="0.1.0",
        icon_image="img/icon.png",
    )

    subprocess.call(build_command, shell=True)


if __name__ == "__main__":
    import docopt

    build()
