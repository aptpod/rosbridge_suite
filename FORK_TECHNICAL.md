# ROS 2 Humble rosbridge_suite - Developer Build Guide

このドキュメントは、開発者向けのローカルビルド手順とCI/CD技術詳細を説明します。

> **📖 一般ユーザーの方へ**: 事前ビルド済みパッケージをお探しの場合は、[FORK_README.md](FORK_README.md)をご覧ください。GitHub Releaseから簡単にインストールできます。

## 目的

- 開発・デバッグ用のローカルビルド環境構築
- CI/CDシステムの理解と改良
- カスタムパッチの適用と検証
- マルチアーキテクチャビルドの技術詳細

## サポートアーキテクチャ

公式ros-humble-rosbridge-suiteのサポート状況に合わせて、以下のアーキテクチャをサポートします：

| アーキテクチャ | サポート状況 | Tier | パッケージ形式 | 備考 |
|---------|--------|------|----------|------|
| **amd64** | ✅ 完全サポート | Tier 1 | バイナリパッケージ | 標準的なx86_64 Linux |
| **arm64** | ✅ 完全サポート | Tier 1 | バイナリパッケージ | Raspberry Pi 4、Apple Silicon等 |
| **armhf** | ❌ 非サポート | Tier 3 | ソースからビルド必要 | 公式ROSパッケージなし |

### 参考：公式パッケージ

ROS 2公式リポジトリ (`repo.ros2.org`) に存在するパッケージ：
- `ros-humble-rosbridge-suite_2.0.1-1jammy.20250701.065406_amd64.deb`
- `ros-humble-rosbridge-suite_2.0.1-1jammy.20250701.173947_arm64.deb`

**armhfアーキテクチャはサポートしていません。**

## 必要な環境

- Docker
- Ubuntu 22.04 (パッケージのインストール先)
- **ROS 2 Humble** (パッケージのインストール先) - **必須**

⚠️ **注意**: このパッケージはROS 2 Humble専用です。他のROSディストリビューション（Foxy、Galactic、Iron等）では動作しません。

## ビルド方法

### 1. ビルドの実行

```bash
# リポジトリのルートディレクトリで実行

# 現在のアーキテクチャのみビルド（最も高速）
./build-deb.sh

# 全サポートアーキテクチャビルド
./build-deb.sh --all

# 特定のアーキテクチャのみ
./build-deb.sh amd64

# 複数アーキテクチャ
./build-deb.sh amd64 arm64

# クリーンビルド
./build-deb.sh --clean --all
```

このスクリプトは以下を実行します：
1. Debian パッケージビルド用のDockerイメージを作成
2. colconでrosbridge_suite全体をビルド
3. 単一のDebianパッケージを作成
4. 成果物を`debian-packages/`ディレクトリに出力

### 2. ビルド成果物

ビルドが成功すると、以下のファイルが`debian-packages/`ディレクトリに生成されます：

- `ros-humble-rosbridge-suite_<arch>.deb` - 統合パッケージ（amd64, arm64）
- `INSTALL.md` - インストール手順

## インストール方法

### パッケージのインストール

```bash
cd debian-packages
sudo apt install ./ros-humble-rosbridge-suite_*.deb
```

これで、BSON対応を含むrosbridge_suite全体がインストールされます。

## 動作確認

```bash
# ROS 2環境の準備
source /opt/ros/humble/setup.bash

# インストールの確認
ros2 pkg list | grep rosbridge

# 出力例:
# rosbridge_library
# rosbridge_msgs
# rosbridge_server
# rosbridge_suite
# rosbridge_test_msgs

# WebSocketサーバーの起動
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

WebSocketサーバーは`ws://localhost:9090`でBSON対応を含めて利用可能になります。

### 正常起動時の出力例

```
[INFO] [rosbridge_websocket-1]: process started with pid [24]
[INFO] [rosapi_node-2]: process started with pid [26]
[INFO] [rosbridge_websocket]: Rosbridge WebSocket server started on port 9090
```

## トラブルシューティング

### ビルドエラーの場合

1. Dockerが正しくインストールされているか確認
   ```bash
   docker --version
   ```

2. ビルドログを確認
   ```bash
   # Dockerコンテナ内でインタラクティブに実行
   docker run -it --rm \
     -v "$(pwd):/source:ro" \
     -v "$(pwd)/debian-packages:/output" \
     rosbridge-debian-builder:latest \
     /bin/bash
   ```

### インストールエラーの場合

1. 依存関係の確認
   ```bash
   sudo apt update
   sudo apt install -f
   ```

2. ROS 2 Humbleが正しくインストールされているか確認
   ```bash
   source /opt/ros/humble/setup.bash
   ros2 --version
   ```

### よくある問題と解決策

#### 1. `ros2 launch`でパッケージが見つからない

**問題**:
```
[ERROR] [launch]: package 'rosbridge_server' not found
```

**解決策**:
```bash
# ROS 2環境が正しくセットアップされているか確認
source /opt/ros/humble/setup.bash

# パッケージが認識されているか確認
ros2 pkg list | grep rosbridge
```

#### 2. 共有ライブラリエラー

**問題**:
```
ImportError: librosbridge_msgs__rosidl_generator_py.so: cannot open shared object file
```

**解決策**: パッケージを再インストールしてください：
```bash
sudo dpkg -r ros-humble-rosbridge-suite
sudo dpkg -i ros-humble-rosbridge-suite_*.deb
```

#### 3. WebSocketサーバーが起動しない

**問題**: プロセスが起動後すぐに終了する

**解決策**:
```bash
# 詳細ログを確認
ros2 launch rosbridge_server rosbridge_websocket_launch.xml --ros-args --log-level DEBUG

# 必要な依存関係がインストールされているか確認
sudo apt install python3-twisted python3-tornado python3-autobahn python3-pymongo python3-pil
```

## カスタマイズ

### 個別パッケージビルド

Dockerファイルは`docker/`ディレクトリに整理されています：

- `docker/Dockerfile.debian-build` - ビルド環境用Dockerfile
- `docker/build-single-deb.sh` - パッケージビルドスクリプト

手動でDockerを使用する場合：

```bash
docker build -f docker/Dockerfile.debian-build -t rosbridge-debian-builder .
docker run --rm -v "$(pwd):/source:ro" -v "$(pwd)/debian-packages:/output" rosbridge-debian-builder
```

### 全アーキテクチャ用ビルド

サポートアーキテクチャ（amd64、arm64）用のパッケージを一括ビルド：

```bash
# 注意: QEMUエミュレーションが必要（時間がかかります）
./build-deb.sh --all
```

※ QEMUエミュレーションを使用するため、ネイティブビルドより時間がかかります

### 新しい機能

```bash
# サポートアーキテクチャ一覧の表示
./build-deb.sh --list

# ビルド前のクリーンアップ
./build-deb.sh --clean --all

# 短縮形
./build-deb.sh -a    # --all と同じ

# ヘルプ表示
./build-deb.sh --help
```

### 実用的な使用例

```bash
# 開発時：現在のアーキテクチャのみ（最も高速）
./build-deb.sh

# CI/CD：全アーキテクチャビルド
./build-deb.sh --all

# リリース準備：クリーンビルド
./build-deb.sh --clean --all

# 特定環境向け：複数アーキテクチャ
./build-deb.sh amd64 arm64

# トラブルシューティング：重複排除テスト
./build-deb.sh amd64 amd64 arm64  # 自動的に amd64 arm64 になる

# 現在の環境確認
./build-deb.sh --list
```

## GitHub Release の自動作成

### 概要

このプロジェクトでは、タグをpushすることで自動的にGitHub Releaseが作成され、アーキテクチャ別のzipファイルが配布されます。

### 使用方法

```bash
# タグを作成してpush（例：ベータ版）
git tag humble-2.0.1+aptpod0.0.1-beta.1
git push origin humble-2.0.1+aptpod0.0.1-beta.1

# タグを作成してpush（例：正式版）
git tag humble-2.0.1+aptpod0.0.1
git push origin humble-2.0.1+aptpod0.0.1
```

### 自動生成される配布物

タグpush後、GitHub Actionsが以下を自動生成します：

1. **GitHub Release**: タグに基づいたリリースページ
2. **配布用zipファイル**:
   - `rosbridge-suite-amd64.zip` - x86_64 Linux向け
   - `rosbridge-suite-arm64.zip` - ARM64 Linux向け
3. **詳細なリリースノート**: インストール手順、対応アーキテクチャ、機能説明

### zipファイルの構成

各zipファイルには以下が含まれます：
- `ros-humble-rosbridge-suite_<arch>.deb` - Debianパッケージ
- `INSTALL.md` - インストール手順

### ビルド時間

- **amd64**: 約5-10分
- **arm64**: 約30-60分（QEMUエミュレーション使用）

### エンドユーザー向けインストール

エンドユーザー向けのインストール手順については、[FORK_README.md](FORK_README.md)の「📦 インストール・使用方法」セクションをご覧ください。

### 対応タグパターン

- **全てのタグ**: 任意のタグ名でReleaseが作成されます
- **推奨パターン**: `humble-<version>+aptpod<version>[-prerelease]`
  - 例: `humble-2.0.1+aptpod0.0.1`
  - 例: `humble-2.0.1+aptpod0.0.1-beta.1`

### GitHub Actions ワークフロー

GitHub Actionsは以下の条件で実行されます：

| トリガー | artifact保存期間 | Release作成 |
|----------|-----------------|-------------|
| **ブランチpush** | 1日 | なし |
| **Pull Request** | 1日 | なし |
| **タグpush** | 1日 | **あり** |

## システムアーキテクチャー

```plantuml
@startuml
!theme plain
skinparam backgroundColor white
skinparam defaultFontSize 10
skinparam componentStyle uml2
top to bottom direction

package "ソースコード (aptpod Fork版)" as src {
    component "rosbridge_suite/" as A #e1f5fe
    component "rosbridge_library/" as B
    component "rosbridge_server/" as C #ffecb3
    component "rosapi/" as API
    component "rosbridge_msgs/" as E
    component "rosbridge_test_msgs/" as F
    note as BSON #fff9c4
        BSON serialization
        aptpod patch
        高速バイナリ処理
    end note

    A --> B
    A --> C
    A --> API
    A --> E
    A --> F
    C .. BSON : aptpod enhancement
}

package "CI/CD・ビルドプロセス" as build {
    component "GitHub Actions" as GA #e3f2fd
    component "Tag Push\n(v*)" as TP #fff3e0
    component "Docker Multi-Arch\nBuild" as H #fff3e0
    component "amd64 Build\n(native)" as I1 #c8e6c9
    component "arm64 Build\n(QEMU)" as I2 #ffcdd2
    component "colcon build\nROS 2 Humble" as I
    component "Debian Package\nCreation" as J

    TP --> GA
    GA --> H
    H --> I1
    H --> I2
    I1 --> I
    I2 --> I
    I --> J
}

package "GitHub Release配布" as output {
    component "GitHub Release" as GR #f3e5f5

    package "アーキテクチャ別パッケージ" as debs {
        component "rosbridge-suite-amd64.zip" as L1 #c8e6c9
        component "rosbridge-suite-arm64.zip" as L2 #c8e6c9
        note as NOARMHF #ffcdd2
            armhf非対応
            公式ROSパッケージなし
        end note
    }

    GR --> debs
}

package "エンドユーザー環境" as install {
    component "Download & Unzip" as D
    component "dpkg -i ros-humble-rosbridge-suite_*.deb" as P
    component "ROS 2 Humble\nEnvironment" as R #e8f5e8
    component "rosbridge WebSocket\nServer (BSON対応)" as S #fff9c4

    D --> P
    P --> R
    R --> S
}

package "実行時アーキテクチャ" as runtime {
    component "Rosbridge Server\nws://9090" as WS #fff9c4
    component "Webクライアント\n(JSON/BSON)" as WC
    component "ROS 2 Topics/Services" as ROS2

    WC <--> WS
    WS <--> ROS2
    
    WS -[hidden]down-> WC
    WS -[hidden]down-> ROS2
}

src --> build
J --> GR
debs --> D
S --> WS

' レイアウト指定
src -[hidden]down-> build
build -[hidden]down-> output
output -[hidden]down-> install
install -[hidden]down-> runtime

@enduml
```

## dpkg コマンドの使用方法

### 基本的なdpkgコマンド

```bash
# パッケージのインストール
sudo dpkg -i ros-humble-rosbridge-suite_*.deb

# パッケージの削除
sudo dpkg -r ros-humble-rosbridge-suite

# パッケージの完全削除（設定ファイルも削除）
sudo dpkg -P ros-humble-rosbridge-suite

# インストール済みパッケージの確認
dpkg -l | grep rosbridge

# パッケージの詳細情報表示
dpkg -s ros-humble-rosbridge-suite

# パッケージの内容確認
dpkg -L ros-humble-rosbridge-suite

# パッケージファイルの内容確認（インストール前）
dpkg -c ros-humble-rosbridge-suite_*.deb
```

### 依存関係の解決

```bash
# 依存関係エラーの修正
sudo apt install -f

# 依存関係の確認
dpkg -I ros-humble-rosbridge-suite_*.deb

# 強制インストール（依存関係を無視）
sudo dpkg -i --force-depends ros-humble-rosbridge-suite_*.deb
```

### トラブルシューティング

```bash
# パッケージの状態確認
dpkg --audit

# 破損したパッケージの修復
sudo dpkg --configure -a

# パッケージデータベースの再構築
sudo dpkg --configure --pending
```

## 技術的な詳細

### パッケージ構成

このDebianパッケージには以下のコンポーネントが含まれています：

- **rosbridge_library**: 核となるBSON対応WebSocketライブラリ
- **rosbridge_server**: BSON対応WebSocketサーバー
- **rosapi**: ROS APIサービス
- **rosbridge_msgs**: rosbridgeメッセージ定義
- **rosapi_msgs**: rosapi メッセージ定義
- **rosbridge_test_msgs**: テスト用メッセージ定義

### インストール構造

パッケージは以下の場所にインストールされます：

```
/opt/ros/humble/
├── lib/
│   ├── python3.10/site-packages/  # Pythonパッケージ
│   ├── rosbridge_server/          # 実行ファイル
│   ├── rosapi/                    # 実行ファイル
│   └── *.so                       # 共有ライブラリ
├── share/
│   ├── rosbridge_server/          # 設定・起動ファイル
│   ├── rosapi/                    # 設定・起動ファイル
│   └── ament_index/               # ROS 2パッケージ発見用インデックス
```

### BSON対応の詳細

BSON対応は`rosbridge_server/src/rosbridge_server/websocket_handler.py`に実装されています：

- **bson_only_mode**: BSON専用モードのサポート
- **バイナリデータ処理**: 効率的なバイナリメッセージ処理
- **後方互換性**: 既存のJSON APIとの互換性を維持

### パッケージサイズ

- **最終パッケージサイズ**: 約754KB
- **主要コンポーネント**:
  - Pythonライブラリ: ~400KB
  - 共有ライブラリ(.so): ~250KB
  - 設定・メタデータ: ~100KB
