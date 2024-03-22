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
docker-compose up
```

### 注意点

ごくたまに


## ライセンス

Apache License Version 2.0 を適用します．
