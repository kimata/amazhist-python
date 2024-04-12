# amazhist-python

amazhist-python は，Amazon.co.jp の買い物履歴情報を収集し，
サムネイル付きの Excel 形式で出力するソフトウェアです．

## 動作環境

基本的には，Python と Selenium が動作する環境であれば動作します．
下記の環境での動作を確認しています．

- Linux (Ubuntu 22.04)
- Windows 11

## 設定

同封されている `config.example.yaml` を `config.yaml` に名前変更して，下記の部分を書き換えます．

```yaml:config.yaml
  user: Amazon.co.jp のユーザ名
  pass: Amazon.co.jp のパスワード
```
## Linux での動かし方

### 必要なパッケージのインストール

実行に際して `docker-compose` を使用しますので，インストールします．
Ubuntu の場合，以下のようにします．

```
sudo apt install docker-compose
```
### 実行

以下のようにします．`build` は一回だけ実行すればOKです．

```
docker-compose run --rm amazhist
```

下記のような感じで，動作ログが表示されながらデータ収集が行われ，
データ収取が完了すると `output` ディレクトリに Excel ファイルが生成されます．

![データ収集の様子](img/collect.gif "データ収集の様子")

注文履歴の数が沢山ある場合，1時間以上がかかりますので，放置しておくのがオススメです．

なお，何らかの事情で中断した場合，再度実行することで，途中から再開できます．
コマンドを実行した後に注文履歴が増えた場合も，再度実行することで前回以降のデータからデータ収集を再開できます．

### Docker を使いたくない場合

[Poetry](https://python-poetry.org/) と Google Chrome がインストールされた環境であれば，
下記のようにして Docker を使わずに実行することもできます．

```
poetry install
poetry run app/amazhist.py
```

## Windows での動かし方

### 準備

[リリースページ](https://github.com/kimata/amazhist-python/releases) から「amazhist-windows_x64-binary-*.zip」を
ダウンロードします．

#### 注意

環境によってはファイルがウィルス判定されることがあります．
これは，Python スクリプトを [Nuitka](https://nuitka.net/) を使って実行ファイルを生成していることが原因です．

ウィルス判定されてしまった場合は，検疫されないように Windows Defender の設定を一時的に変更お願いします．

### 実行

`amazhist.exe` をダブルクリックすればOKです．

## FAQ

### データの収集が途中で止まる

稀に画像認証を求められることがあります．その場合，下記のようなメッセージが表示されますので，
画像を確認してそこに書かれている文字列を入力してください．(最後に ENTER が必要です)

```
「output/captcha.png」に書かれているテキストを入力してくだい:
```

## 参考

Amazon 公式では購入履歴の CSV を提供するサービスが行われています．
購入日・商品・価格等だけがあれば十分な場合はこちらを利用するのが便利です．

利用するには，Amazon.co.jp の「アカウントサービス」 →「 [データをリクエストする](https://www.amazon.co.jp/hz/privacy-central/data-requests/preview.html)」
から手続きを行います．

## ライセンス

Apache License Version 2.0 を適用します．
