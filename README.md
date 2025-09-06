# <img src="logo.png" width="50px"> CopyBento

macOS 用のクリップボード履歴 + プラグイン対応ツール。バックグラウンド常駐（Dock/メニューバーに出しません）、ホットキーで Spotlight 風の履歴 GUI を開きます。

-   クリップボードのテキスト/画像を監視して履歴化（最新 200 件）
-   Shift+Cmd+V で履歴 GUI を表示（検索・サムネイル・ぼかし背景・キーボード操作）
-   Return でコピー、Escape で閉じる、コピー後は直前アプリに自動ペースト（Cmd+V）
-   プラグインでコピー内容を書き換え/スキップ（GUI の Settings から ON/OFF）
-   プラグインは内蔵 Plugins と ~/.config/copybento/plugins の両方から読み込み
-   GUI から選んだ画像はプラグイン処理をスキップ（画質劣化や加工を避けるため）

## 要件

-   macOS
-   Python 3.9+
-   必須パッケージ: pyobjc, pillow（アラート用途で rumps を併用）

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

初回は「アクセシビリティ」の許可が必要です（キーボードショートカット用）。許可後、Shift+Cmd+V で履歴 GUI を開けます。

## プラグイン

プラグインは以下の場所に置けます（両方読み込みます）。

-   プロジェクト内: `Plugins/`
-   ユーザー用: `~/.config/copybento/plugins/`（XDG_CONFIG_HOME があればそちら）

各プラグインは次の関数を実装します。

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

# 任意: 起動時フック（ホットキー登録などに使用）
def on_startup(event_manager):
    event_manager.register_hotkey("shift+cmd+v", "open_history_gui")
```

プラグインの有効/無効は GUI の「Settings」からトグルできます。設定は `~/.config/copybento/settings.json` に保存されます（NAME とモジュール名の両方で互換管理）。

## 実装メモ

-   監視: `Library/event.py` の簡易イベントループで `wait_for_clipboard_change()` をポーリング
-   クリップボード I/F: `Library/mcb.py`（pyobjc + Pillow）
-   GUI: `Plugins/GUI.py`（PyObjC / Cocoa、Blur/透明、検索、サムネイル、単一ウィンドウ）
-   プラグイン管理: `Library/plugin.py`（内蔵 + ユーザーディレクトリ対応）
-   設定: `Library/settings.py`（`~/.config/copybento/settings.json`）
-   履歴保存: `History/history.json` と画像 PNG（最新 200 件）
-   備考: GUI 由来の画像コピーにはペーストボードにマーカーを付け、プラグイン処理をスキップ

## 開発

-   ログレベルは `main.py` 冒頭で `logging.basicConfig(level=logging.INFO)` を変更
-   履歴点数や更新間隔は `_persist_history`/`event.run(interval=...)` を調整
-   ユーザープラグインは `~/.config/copybento/plugins/` へ配置すると本体から独立して管理できます

## ライセンス

See [LICENSE](LICENSE)
