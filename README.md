# amazhist-python

amazhist-python は，Amazon.co.jp の買い物履歴情報を取得し，Excel 形式で出力するソフトウェアです．

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

```
docker-compose run --rm amazhist
```

### 注意点

稀に画像認証を求められることがあります．その場合，下記のようなメッセージが表示されますので，
画像を確認してそこに書かれている文字列を入力してください．(最後に ENTER が必要です)

```
「output/captcha.png」に書かれているテキストを入力してくだい:
```

## ライセンス

Apache License Version 2.0 を適用します．
