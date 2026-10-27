# Weather Art Curation

美術館の公開データからパブリックドメイン作品を収集し、ローカル CLIP と色解析で分類し、人がレビューした作品だけを `artworks.json` に出力するツールです。元仕様は `curation-tool-overview.md`、タグ定義は `categories.md` を参照してください。

## セットアップ

Python 3.12+ と [uv](https://docs.astral.sh/uv/) を使用します。

```sh
uv sync --extra dev
uv run curation --help
```

CLIP 分類を使う場合だけ重い依存を追加します（初回はモデルのダウンロードが発生します）。

```sh
uv sync --extra dev --extra clip
```

## 基本フロー

```sh
uv run curation collect --source met --limit 100
uv run curation collect --source cma --limit 100
uv run curation fetch-images --source met,cma
uv run curation classify
uv run curation review
uv run curation stats
uv run curation export
```

収集は AIC / Met / CMA に対応します。`limit` は今回追加する新規作品数です。先頭に既存作品があってもAPIを先へ進めます。`collect`、`fetch-images`、`classify` は既存 ID またはキャッシュをスキップするため、中断後に同じコマンドを再実行できます。既定で画像取得は1秒間隔です。AIC API も1秒間隔、Met は0.02秒、CMA は0.1秒に制限しています。大量収集時は各館のデータダンプを優先してください。

Metの検索には現行のCollection API v1.1を使用し、ページングした候補をv1詳細APIでパブリックドメイン・画像・絵画か再検証します。CMAは約3,900件のCC0作品群から、landscape、sky、cloud、weather、rain、snow、fog、storm、seascape、cityscapeを個別検索し、重複を除外します。検索語を調整したい場合は `--query` を反復またはカンマ区切りで指定できます。

```sh
uv run curation collect --source met --limit 50 --query landscape --query seascape
uv run curation collect --source cma --limit 50 --query rain,snow,fog
```

収集完了時には使用した検索語、新規追加数、走査数、既存スキップ数、検索語間の重複数、条件不適合作品数を表示します。候補・キャッシュ・分類結果・レビューは削除せず追記または原子的更新するため、安全に再実行できます。

AICのAPIと画像へのアクセス時は利用者を識別できる連絡先が必要です。`collect` と `fetch-images` の `--aic-contact` にメールアドレスまたはプロジェクトURLを指定するか、`CURATION_AIC_CONTACT` 環境変数を設定してください。AIC候補があり連絡先が未設定の場合、画像通信を始める前にコマンドをエラー終了します。Met/CMAではこの設定は不要です。

画像取得でHTTPエラーや一時的なネットワーク障害が起きても、他の作品の取得は継続します。失敗した作品IDと理由は標準エラーに、成功・キャッシュ済み・失敗の件数は最後に表示されます。不完全な `.part` ファイルは削除されるため、同じコマンドを再実行すると失敗分だけを再試行します。

取得元は `--source` で限定できます。オプションの反復とカンマ区切りの両方に対応します。

```sh
uv run curation fetch-images --source met
uv run curation fetch-images --source met --source cma
uv run curation fetch-images --source met,cma
```

### AIC画像配信の既知制約

2026-10-27現在、AIC公式の `www.artic.edu/iiif` はCloudflare managed challengeにより、通常の非ブラウザHTTPクライアントからの画像取得を403で拒否します。User-Agentや連絡先の指定では解決できず、公式メタデータにも代替画像URLはありません。状況は[AIC api-data Issue #9](https://github.com/art-institute-of-chicago/api-data/issues/9)を参照してください。

本ツールはchallengeを検出すると、それ以降のAIC画像への連続アクセスを止めて具体的な案内を表示します。Cloudflareの回避は行いません。当面はMet/CMAを収集・取得してください。

```sh
uv run curation collect --source met --limit 200
uv run curation collect --source cma --limit 200
uv run curation fetch-images --source met,cma
```

分類も `--source met,cma` のように対象を限定できます。画像なし作品はIDを大量表示せず、収集元別の件数を最後にまとめます。

レビュー画面は `http://127.0.0.1:8000` に開きます。`A` 承認、`R` 却下、`S` スキップ。スキップもレビュー結果として保存されます。タグのチェックを変更してから承認でき、天気・時間・判定状態で絞り込めます。画面には承認・却下・スキップ・未判定の進捗、収集元別件数、カテゴリの目標数と不足数を表示します。各判定は直ちに一時ファイル経由で `data/reviews.json` に保存され、再分類では消えません。

`export` は承認済み作品だけを書き出し、`schema/artwork.schema.json` に不適合なら失敗します。`evaluate` は `eval/labeled.jsonl` の各行（`{"id":"aic-1","tags":{...}}`）と比較し、軸別 accuracy と混同行列を表示します。

## 開発

```sh
uv run pytest
uv run ruff check .
```

人の判断である `data/reviews.json` と `eval/labeled.jsonl`、成果物 `dist/artworks.json` は Git 管理します。画像、候補、分類結果は `.gitignore` 対象です。レビュー前に Git コミットを作り、定期的にレビュー結果をコミットしてください。
