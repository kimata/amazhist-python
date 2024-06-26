FROM ubuntu:22.04

# NOTE:
# python:3.11.4-bookworm とかを使った場合，Selenium を同時に複数動かせないので，
# Ubuntu イメージを使う

ENV TZ=Asia/Tokyo
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install --assume-yes \
    curl \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN curl -O  https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

RUN apt-get update && apt-get install --assume-yes \
    language-pack-ja fonts-ipaexfont-gothic \
    python3 python3-pip \
    ./google-chrome-stable_current_amd64.deb \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/amazhist

RUN locale-gen en_US.UTF-8
RUN locale-gen ja_JP.UTF-8

# NOTE: apt にあるものはバージョンが古いので直接入れる
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

COPY . .

RUN poetry config virtualenvs.create false \
 && poetry install \
 && rm -rf ~/.cache

RUN useradd -m ubuntu

RUN mkdir -p data
RUN chown -R ubuntu:ubuntu .

USER ubuntu

ENV TERM=xterm-256color

CMD ["./app/amazhist.py"]
