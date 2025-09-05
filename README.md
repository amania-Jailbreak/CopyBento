# CopyBento

macOS メニューバー常駐のクリップボード履歴 + プラグイン対応ツール。

-   クリップボードのテキスト/画像を監視して履歴化
-   メニューを開くと直近の履歴がトップレベルに並び、クリックで再コピー
-   プラグイン機構でコピー内容を書き換え/スキップが可能

## 要件

-   macOS
-   Python 3.9+
-   必須パッケージ: rumps, pyobjc, pillow

## セットアップ

```bash
# 任意: 仮想環境
python -m venv .venv
source .venv/bin/activate

# 依存をインストール
pip install -r requirements.txt
```

## 起動

```bash
python main.py
```

メニューバーに「CopyBento」が現れます。メニューを開くと履歴が直接並び、選択で元の内容をクリップボードへ復元します。

## プラグイン

プラグインは `Plugins/` に配置する Python ファイルです。各プラグインは次の関数を実装します。

```python
# Plugins/example.py
NAME = "My Plugin"  # 任意

def on_clipboard(data_type, value):
    """
    data_type: "text" | "image"
    value: str | PIL.Image.Image

    return None                      # 変更なし（次のプラグインへ）
    return ("text", new_text)        # テキストへ置換
    return ("image", new_image)      # 画像へ置換
    return PluginManager.SKIP        # このコピーをスキップ
    # または: return ("skip", None)
    """
    return None
```

同梱のサンプル:

-   `Plugins/uppercase.py` — テキストを大文字化

プラグインの有効/無効はメニューの「Plugins」からトグルできます。

## 実装メモ

-   監視: `Library/event.py` の簡易イベントループで `wait_for_clipboard_change()` をポーリング
-   クリップボード I/F: `Library/mcb.py`（pyobjc + Pillow）
-   メニューバー UI: `rumps`
-   プラグイン管理: `Library/plugin.py`

## 開発

-   ログレベルは `main.py` 冒頭で `logging.basicConfig(level=logging.INFO)` を変更
-   履歴点数や更新間隔は `main.py` 内の `_build_history_items`/タイマーから調整

## ライセンス

See [LICENSE](LICENSE)
