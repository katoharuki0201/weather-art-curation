# 絵画分類ツール 開発概要

## 1. 背景と目的

天気に合わせて「その空に近い絵画」を表示する Web アプリを開発している。
アプリは実行時に美術館の API を呼ばず、**事前にキュレーションした作品一覧(`artworks.json`)** から作品を選んで表示する。

本ツールは、その `artworks.json` を作るためのものである。
美術館の公開データから作品を集め、**無料のローカル AI モデル(CLIP)で天気・時間帯・季節を自動分類**し、**人間が最終確認**したうえで書き出す。

- アプリ本体とは **別リポジトリ** で開発する
- アプリとの接点は **`artworks.json` の形式のみ**
- カテゴリの定義は別紙 **`categories.md`** に従う(本書と一緒に参照すること)

---

## 2. 処理の流れ

```
① 収集      美術館のデータから候補作品を集め、共通形式にそろえる
   ↓          → data/candidates.jsonl
② 画像取得  分類用の画像をダウンロードしてキャッシュする
   ↓          → data/cache/images/
③ 自動分類  CLIP と色解析でタグと確信度を付ける
   ↓          → data/classified.jsonl
④ レビュー  人間がブラウザで承認・却下・修正する
   ↓          → data/reviews.json
⑤ 書き出し  承認済みの作品を artworks.json として出力し、スキーマで検証する
              → dist/artworks.json
```

- 各段階はファイルで結果を受け渡し、**途中から再実行できる**ようにする
- すでに処理済みの作品は **スキップ** する(再実行しても無駄な処理・通信をしない)

---

## 3. 対象データ

| 館 | 取得元 | 認証 | 主な注意点 |
|---|---|---|---|
| Art Institute of Chicago(AIC) | API `https://api.artic.edu/api/v1/`、またはデータダンプ(GitHub: `art-institute-of-chicago/api-data`) | 不要 | API は 1 分 60 リクエストまで。画像は IIIF(`https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg`)。画像の取得は 1 枚ずつ、1 秒程度の間隔を空ける。`AIC-User-Agent` ヘッダーにプロジェクト名と連絡先を入れる |
| The Metropolitan Museum of Art(Met) | API `https://collectionapi.metmuseum.org/public/collection/v1/` | 不要 | 毎秒 80 リクエストまで。検索は ID 一覧のみを返すため、詳細は 1 件ずつ取得する。`isPublicDomain` と `primaryImageSmall` を使う |
| Cleveland Museum of Art(CMA) | API `https://openaccess-api.clevelandart.org/api/artworks/`、またはデータ一式(GitHub: `ClevelandMuseumArt/openaccess`) | 不要 | `cc0`、`has_image=1`、`type=Painting` で絞り込める。画像 URL(`images.web.url`)が直接含まれる |

### 候補の絞り込み条件

- パブリックドメイン(または CC0)であること
- 画像があること
- 絵画であること(版画・素描を含めるかは設定で切り替えられるようにする)
- 風景・海景・都市景観など、空が描かれていそうな主題であること(各館の主題タグ等で大まかに絞る)

---

## 4. 自動分類の方針

### 4.1 CLIP によるゼロショット分類

- 画像と説明文の近さを CLIP で計算し、最も近い説明文のカテゴリを採用する
- 判定は **軸ごとに独立して行う**
  - 空が見えるか(見えない作品は除外候補)
  - 天気(`clear` / `cloudy` / `fog` / `rain` / `snow` / `storm`)
  - 時間帯(`day` / `twilight` / `night`)
  - 季節(`spring` / `summer` / `autumn` / `winter` / 判断不能)
- 1 カテゴリにつき **複数の説明文** を用意し、結果を平均して安定させる
- 説明文は **コードから分離** し(設定ファイル等)、調整しやすくする
- 1 位と 2 位の差などから **確信度** を算出する
- 複数タグを付けてよい(例:雪と曇り)。付与の閾値は設定で調整できるようにする

### 4.2 色解析による補助

- 画像上部(空の部分と想定)の明るさ・色相・彩度を求める
- 例:暗い → 夜の可能性、暖色 → 朝夕の可能性、低彩度の灰色 → 曇りの可能性
- CLIP の結果と組み合わせて確信度を補正する

### 4.3 モデル

- open_clip または transformers の CLIP を使用する(無料・ローカル実行)
- CPU でも動作すること。GPU / Apple Silicon(MPS)があれば利用する
- モデル名は設定で切り替えられるようにする(軽量モデルと高精度モデルを比較できるように)

---

## 5. 精度評価

- 人が手でタグを付けた **正解データ**(`eval/labeled.jsonl`、100 件程度)を用意する
- 分類結果と正解データを比較し、**軸ごとの正解率と混同行列** を出力するコマンドを用意する
- 説明文やモデルを変えたときに、精度を数字で比較できるようにする

---

## 6. レビューツール

- ローカルで起動する Web 画面(FastAPI + HTML 1 枚を想定)
- カテゴリごとに作品のサムネイルを並べ、**確信度の高い順** に表示する
- **キーボード操作** で素早く判定できること
  - 承認 / 却下 / 別カテゴリへの付け替え / 複数タグの編集
- 自動分類の結果(各カテゴリのスコア)を横に表示する
- 判定はその都度 `data/reviews.json` に保存し、**中断しても再開できる**
- 判定済みの作品は、再分類しても判定が消えないこと
- カテゴリごとの承認数を表示し、`categories.md` の目安件数と比べられること

---

## 7. 出力:`artworks.json`

- 承認済みの作品のみを出力する
- **アプリ側が提供する JSON Schema(`schema/artwork.schema.json`)で検証** し、不合格ならエラーにする
- 1 件の形式(暫定案。最終的にはアプリ側のスキーマに従う):

```json
{
  "id": "aic-12345",
  "source": "aic",
  "title": "Winter Evening",
  "artist": "Artist Name",
  "date": "1885",
  "image": {
    "url": "https://www.artic.edu/iiif/2/xxxx/full/843,/0/default.jpg",
    "thumbUrl": "https://www.artic.edu/iiif/2/xxxx/full/200,/0/default.jpg"
  },
  "sourceUrl": "https://www.artic.edu/artworks/12345",
  "credit": "Art Institute of Chicago, Public Domain",
  "tags": {
    "weather": ["snow", "cloudy"],
    "time": ["twilight"],
    "season": ["winter"]
  }
}
```

- `id` は `{館の略称}-{館の作品ID}` とし、館をまたいで一意にする
- `season` が空配列の場合は「季節タグなし(どの季節にも出せる)」を意味する

---

## 8. 技術スタック

| 用途 | 採用 |
|---|---|
| 言語 | Python 3.12 以上 |
| 環境・依存管理 | uv |
| データモデル | Pydantic |
| 分類モデル | open_clip または transformers(CLIP) |
| 画像処理 | Pillow、NumPy |
| HTTP | httpx |
| レビューツール | FastAPI(+ 素の HTML / JS) |
| 出力検証 | jsonschema |
| CLI | Typer 等 |
| 品質 | ruff、pytest |

---

## 9. ディレクトリ構成(案)

```
weather-art-curation/
├─ src/curation/
│   ├─ models.py          Pydantic モデル(候補、分類結果、レビュー結果)
│   ├─ categories.py      カテゴリ定義(categories.md をコード化)
│   ├─ collect/           収集と正規化(aic.py、met.py、cma.py)
│   ├─ images.py          画像のダウンロードとキャッシュ(間隔制御付き)
│   ├─ classify/
│   │   ├─ prompts.yaml   カテゴリごとの説明文
│   │   ├─ clip.py        CLIP による判定
│   │   ├─ color.py       色解析
│   │   └─ combine.py     結果の統合と確信度の算出
│   ├─ evaluate.py        正解データとの比較
│   ├─ review/            レビューツール(サーバーと画面)
│   ├─ export.py          artworks.json の書き出しと検証
│   └─ cli.py             コマンドの入口
├─ schema/artwork.schema.json   アプリ側から受け取る JSON Schema
├─ data/                  中間データ
├─ eval/labeled.jsonl     正解データ
├─ dist/artworks.json     成果物
├─ tests/
└─ pyproject.toml
```

### Git 管理の方針

| パス | Git 管理 | 理由 |
|---|---|---|
| `data/raw/`、`data/cache/` | しない | 大きく、再取得できる |
| `data/candidates.jsonl` | しない | 再生成できる |
| `data/classified.jsonl` | 任意 | 再生成できるが時間がかかる |
| `data/reviews.json` | **する** | 人の作業結果で、再現できない |
| `eval/labeled.jsonl` | **する** | 人の作業結果で、再現できない |
| `dist/artworks.json` | する | 成果物 |

---

## 10. コマンド(案)

| コマンド | 内容 |
|---|---|
| `curation collect --source aic --limit 200` | 候補を収集する |
| `curation fetch-images` | 画像をダウンロードしてキャッシュする |
| `curation classify` | 自動分類する |
| `curation evaluate` | 正解データで精度を測る |
| `curation review` | レビューツールを起動する |
| `curation export` | artworks.json を書き出して検証する |
| `curation stats` | カテゴリごとの件数を表示する |

---

## 11. 開発の進め方

1 館・少数で最後まで通してから、規模を広げる。

1. 土台(プロジェクト作成、Pydantic モデル、カテゴリ定義)
2. AIC からの収集(風景系 200 件程度)
3. 画像の取得とキャッシュ
4. 正解データの作成(100 件程度、人手)
5. CLIP による分類と精度評価、説明文の調整
6. 色解析の追加と精度の比較
7. レビューツール
8. artworks.json の書き出しと検証
9. Met・CMA の追加と件数の拡大

---

## 12. 守ること

- **パブリックドメイン / CC0 の作品のみ** を扱う
- 各館の **利用ルールとリクエスト制限を守る**(大量取得はデータダンプを優先し、API は間隔を空けて単一スレッドで呼ぶ)
- 一度取得したデータ・画像は **キャッシュし、再取得しない**
- 人の作業結果(`reviews.json`、`labeled.jsonl`)を **上書きや破損で失わない** こと(書き込みは一時ファイル経由で行う等)
- 有料の API やサービスは使わない

---

## 13. 対象外

- アプリ本体の実装
- 書き出した `artworks.json` をアプリのリポジトリへ反映する仕組み(当面は手動でコピーする)
- 画像そのものの配信(アプリは美術館の画像 URL を直接参照する)
