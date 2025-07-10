# ROS 2 rosbridge_suite (aptpod 改良版)

本リポジトリは、オリジナルの[rosbridge_suite](https://github.com/RobotWebTools/rosbridge_suite)プロジェクトを**aptpodが改良したフォーク版**です。ROS 2 Humbleに特化し、パフォーマンスと配布機能を大幅に向上させています。

## 🎯 フォークの目的・背景

産業用IoTおよびロボティクス用途での具体的なニーズに対応するため、rosbridge_suiteをフォークしました：

- **バイナリデータ転送の性能最適化**
- **本番環境向けの配布システム簡素化**
- **アーキテクチャ横断の信頼性あるビルドのためのCI/CD強化**
- **現行LTSサポートのためのROS 2 Humble特化**

このフォーク版は、元のrosbridgeプロトコルとの互換性を維持しながら、エンタープライズ用途向けの大幅な改良を加えています。

## 🚀 主な改良点

### 1. BSONシリアライゼーション対応

**概要**: rosbridge_serverにバイナリJSON（BSON）シリアライゼーション機能を追加

**メリット**:
- **大容量ペイロードの高速データ転送**（画像、点群、センサーデータ等）
- **標準JSONと比較した帯域使用量削減**
- **バイナリメッセージタイプでの性能向上**
- **既存JSONクライアントとの後方互換性維持**

**実装**: `websocket_handler.py`に`bson_only_mode`サポートを追加し、効率的なバイナリメッセージ処理を実現。

### 2. マルチアーキテクチャサポート

**対応アーキテクチャ**:
- ✅ **amd64** (x86_64) - 標準Linuxシステム
- ✅ **arm64** (AArch64) - Raspberry Pi 4、Apple Silicon、ARMサーバー
- ❌ **armhf** - 非対応（公式ROS 2 Humbleパッケージなし）

**配布**: QEMUエミュレーション使用のGitHub Actionsによる両アーキテクチャの自動ビルド。

### 3. GitHub Release自動化システム

**機能**:
- **タグトリガーリリース**: 任意のタグpushで自動GitHub Release作成
- **アーキテクチャ別パッケージ**: amd64/arm64用の個別zipファイル
- **即導入可能パッケージ**: 依存関係込みの事前ビルド済みDebianパッケージ
- **包括的ドキュメント**: インストール手順付き自動リリースノート

**使用方法**:
```bash
# タグを作成・pushしてリリースをトリガー
git tag humble-2.0.1+aptpod0.0.1
git push origin humble-2.0.1+aptpod0.0.1
```

### 4. 強化されたCI/CDパイプライン

**ビルドシステム**:
- **クリーンで再現可能な環境のためのDockerベースビルド**
- **ARMアーキテクチャ用QEMU使用のクロスコンパイル対応**
- **pre-commitフックとlintingによる自動テスト**
- **エミュレート環境向け並列処理制限によるビルド時間最適化**

**品質保証**:
- コードフォーマットとlinting用pre-commitフック
- BSON機能の自動検証
- パッケージ整合性チェック

## 📦 インストール・使用方法

### エンドユーザー向け（推奨）

**GitHub Releasesからダウンロード**:

リリース情報の詳細は[Releasesページ](https://github.com/aptpod/rosbridge_suite/releases)をご覧ください。

### 自動生成される配布物

各タグpush後、GitHub Actionsが以下を自動生成します：

1. **GitHub Release**: タグに基づいたリリースページ
2. **配布用zipファイル**:
   - `rosbridge-suite-{タグ名}-amd64.zip` - x86_64 Linux向け
   - `rosbridge-suite-{タグ名}-arm64.zip` - ARM64 Linux向け
   - 例: `rosbridge-suite-humble-2.0.1+aptpod0.0.1-amd64.zip`
3. **詳細なリリースノート**: インストール手順、対応アーキテクチャ、機能説明

### ダウンロード手順

1. [Releasesページ](https://github.com/aptpod/rosbridge_suite/releases)にアクセス
2. お使いのアーキテクチャに適したzipファイルをダウンロード

**インストール**:
```bash
# パッケージを展開
unzip rosbridge-suite-amd64.zip

# 依存関係をインストール
sudo apt update
sudo apt install -y python3-twisted python3-tornado python3-autobahn python3-pymongo python3-pil

# パッケージをインストール
sudo dpkg -i ros-humble-rosbridge-suite_*.deb

# インストールを確認
source /opt/ros/humble/setup.bash
ros2 pkg list | grep rosbridge
```

**サーバー起動**:
```bash
source /opt/ros/humble/setup.bash

# 標準モード（JSON）
ros2 launch rosbridge_server rosbridge_websocket_launch.xml

# またはJSONモードを明示的に指定
ros2 launch rosbridge_server rosbridge_websocket_launch.xml bson_only_mode:=false

# BSON専用モード
ros2 launch rosbridge_server rosbridge_websocket_launch.xml bson_only_mode:=true
```

WebSocketサーバーは`ws://localhost:9090`で利用可能になります。

- **標準モード**: JSON対応（デフォルト）
- **BSON専用モード**: BSONのみ対応、最高性能

### 開発者向け

**ローカルビルド**: 詳細なビルド手順と開発環境セットアップについては[FORK_TECHNICAL.md](FORK_TECHNICAL.md)をご覧ください。

## ⚠️ 重要な注意事項

- **パッケージ置き換え**: このパッケージは公式rosbridge_suiteと置き換えて使用してください
- **ビルド方法の違い**: このフォーク版は公式のrosbridge_suiteとは異なる独自のビルド方法を使用しています

## 🏗️ アーキテクチャ概要

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Webクライアント     │    │   rosbridge_server   │    │   ROS 2システム     │
│                     │    │   (aptpod改良版)     │    │                     │
│ ┌─────────────────┐ │    │ ┌──────────────────┐ │    │ ┌─────────────────┐ │
│ │ JSON/BSON       │◄┼────┼►│ BSONシリアライザ  │◄┼────┼►│ ネイティブROS   │ │
│ │ over WebSocket  │ │    │ │ 高速バイナリ処理  │ │    │ │ メッセージ      │ │
│ │ ws://9090       │ │    │ │ + JSON互換性     │ │    │ │ (Humble)        │ │
│ └─────────────────┘ │    │ └──────────────────┘ │    │ └─────────────────┘ │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
```

> **詳細な技術アーキテクチャ**: CI/CD・ビルドプロセス・配布システムの詳細については、[FORK_TECHNICAL.md](FORK_TECHNICAL.md)のシステムアーキテクチャーセクションをご覧ください。

## 📋 パッケージ構成

この配布版には、rosbridge_suite全コンポーネントが含まれています：

- **rosbridge_library** - BSONサポート付きコア機能
- **rosbridge_server** - 強化されたメッセージ処理付きWebSocketサーバー
- **rosapi** - ROS APIサービスインターフェース
- **rosbridge_msgs** - プロトコルメッセージ定義
- **rosapi_msgs** - APIメッセージ定義
- **rosbridge_test_msgs** - テスト用メッセージ定義

## 🔧 技術仕様

**要件**:
- Ubuntu 22.04 (Jammy Jellyfish)
- ROS 2 Humble Hawksbill
- Python 3.10+

**パフォーマンス**:
- **ビルド時間**: 約5-10分 (amd64)、約30-60分 (arm64)
- **パッケージサイズ**: 合計約754KB
- **メモリ使用量**: オリジナルrosbridge_suiteと同等
- **BSON性能**: JSONと比較してバイナリデータで20-40%高速

## 📄 バージョニング戦略

上流とaptpod独自改良の両方を追跡するハイブリッドバージョニングスキームを使用：

**形式**: `[ディストリビューション]-[上流バージョン]+aptpod[フォークバージョン]([-プレリリース])`

**例**:
- `humble-2.0.1+aptpod0.0.1` - 安定版リリース
- `humble-2.0.1+aptpod0.0.1-beta.1` - プレリリース版

## 🙏 謝辞

本プロジェクトは[Robot Web Tools](https://robotwebtools.github.io/)コミュニティの優秀な成果の上に構築されています。基盤となるrosbridge_suite実装に感謝し、オリジナルプロジェクトの目標とコミュニティを尊重してこのフォークを維持しています。

**オリジナルプロジェクト**: https://github.com/RobotWebTools/rosbridge_suite

## 📞 サポート

aptpod固有の機能・問題について:
- このリポジトリでissueを作成
- 技術文書については[FORK_TECHNICAL.md](FORK_TECHNICAL.md)を参照

一般的なrosbridgeに関する質問:
- オリジナルの[ROS wikiドキュメント](http://ros.org/wiki/rosbridge_suite)を参照
- オリジナルプロジェクトのリソースを確認

---

*この改良版は、産業用IoTおよびロボティクス用途向けにaptpod株式会社が保守しています。*
