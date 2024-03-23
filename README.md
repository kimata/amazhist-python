# amazhist-python

amazhist-python は，Amazon.co.jp の買い物履歴情報を取得し，
サムネイル付きの Excel 形式で出力するソフトウェアです．

## 準備

### 必要なパッケージのインストール

実行に際して `docker-compose` を使用しますので，インストールします．
Ubuntu の場合，以下のようにします．

```
sudo apt install docker-compose
```
### Amazon.co.jp へのログイン情報の設定

`config.example.yaml` を `config.yaml` に名前変更して，下記の部分を書き換えます．

```yaml:config.yaml
  user: Amazon.co.jp のユーザ名
  pass: Amazon.co.jp のパスワード
```

## 実行

以下のようにします．`build` は一回だけ実行すればOKです．

```
docker-compose build
docker-compose run --rm amazhist
```

### 注意点

稀に画像認証を求められることがあります．その場合，下記のようなメッセージが表示されますので，
画像を確認してそこに書かれている文字列を入力してください．(最後に ENTER が必要です)

```
「output/captcha.png」に書かれているテキストを入力してくだい:
```

### Docker を使いたくない場合

[Poetry](https://python-poetry.org/) と Google Chrome がインストールされた環境であれば，
下記のようにして Docker を使わずに実行することもできます．

```
poetry install
poetry run app/amazhist.py
```

## 参考

Amazon 公式では購入履歴の CSV を提供するサービスが行われています．
購入日・商品・価格等だけがあれば十分な場合はこちらを利用するのが便利です．

利用するには，Amazon.co.jp の「アカウントサービス」 →「 [データをリクエストする](https://www.amazon.co.jp/hz/privacy-central/data-requests/preview.html)」
から手続きを行います．

## ライセンス

Apache License Version 2.0 を適用します．
