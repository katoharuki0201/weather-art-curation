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
uv run curation collect --source aic --limit 20 --aic-contact you@example.com
uv run curation fetch-images
uv run curation classify
uv run curation review
uv run curation stats
uv run curation export
```

収集は AIC / Met / CMA に対応します。`limit` は今回追加する新規作品数です。先頭に既存作品があってもAPIを先へ進めます。`collect`、`fetch-images`、`classify` は既存 ID またはキャッシュをスキップするため、中断後に同じコマンドを再実行できます。既定で画像取得は1秒間隔です。AIC API も1秒間隔、Met は0.02秒、CMA は0.1秒に制限しています。大量収集時は各館のデータダンプを優先してください。

AICへのアクセス時は利用者を識別できる連絡先が必要です。`--aic-contact` にメールアドレスまたはプロジェクトURLを指定するか、`CURATION_AIC_CONTACT` 環境変数を設定してください。未設定の場合は不適切なUser-Agentで通信せず、コマンドをエラー終了します。Met/CMAではこの設定は不要です。

レビュー画面は `http://127.0.0.1:8000` に開きます。`A` 承認、`R` 却下、`S` スキップ。タグのチェックを変更してから承認できます。各判定は直ちに一時ファイル経由で `data/reviews.json` に保存され、再分類では消えません。

`export` は承認済み作品だけを書き出し、`schema/artwork.schema.json` に不適合なら失敗します。`evaluate` は `eval/labeled.jsonl` の各行（`{"id":"aic-1","tags":{...}}`）と比較し、軸別 accuracy と混同行列を表示します。

## 開発

```sh
uv run pytest
uv run ruff check .
```

人の判断である `data/reviews.json` と `eval/labeled.jsonl`、成果物 `dist/artworks.json` は Git 管理します。画像、候補、分類結果は `.gitignore` 対象です。レビュー前に Git コミットを作り、定期的にレビュー結果をコミットしてください。
