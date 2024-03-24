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
    package_list = [
        "enlighten",
        "selenium.webdriver.support",
        "openpyxl",
        "logging.handlers",
        "coloredlogs",
        "yaml",
    ]

    build_command = (
        "poetry run nuitka3 --follow-imports {package_include} --include-package-data=selenium "
        "--product-name={name} --file-version={version} --product-version={version} "
        "--windows-icon-from-ico={icon_image} --jobs={jobs} "
        "--standalone --onefile --output-dir=build --script-name=app/amazhist.py"
    ).format(
        jobs=JOBS,
        package_include=" ".join(
            map(
                lambda package_name: "--include-package={package}".format(package=package_name),
                package_list,
            )
        ),
        name="amazhist",
        version="0.1.0",
        icon_image="img/icon.png",
    )

    subprocess.call(build_command, shell=True)


if __name__ == "__main__":
    import docopt

    build()
