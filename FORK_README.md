# ROS 2 rosbridge_suite (aptpod 改良版)

本リポジトリは、オリジナルの[rosbridge_suite](https://github.com/RobotWebTools/rosbridge_suite)にBSONシリアライゼーション機能を追加した**aptpod改良版**です。

> **開発者向け**: 開発環境の詳細は [FORK_DEVELOPER.md](FORK_DEVELOPER.md) をご覧ください。

## 🚀 主な改良点

### BSONシリアライゼーション対応

rosbridge_serverにバイナリJSON（BSON）シリアライゼーション機能を追加しました。

**メリット**:
- **大容量ペイロードの高速データ転送**（画像、点群、センサーデータ等）
- **標準JSONと比較した帯域使用量削減**
- **バイナリメッセージタイプでの性能向上**
- **JSON専用モード**（デフォルト）または**BSON専用モード**を選択可能

## 🚀 性能改善（humbleブランチ追加機能）

### BSON Binary効率化
- **データサイズ削減**: PointCloud2等の大容量バイナリデータで約20%のサイズ削減
- **処理時間短縮**: メッセージ変換処理で約82-84%の高速化を実現
- **Base64回避**: uint8[]配列データをBSON Binaryとして直接処理

### 最適化された処理
- **型名抽出最適化**: 3.8MBメッセージで250ms → 0.05ms（約5000倍高速化）
- **ゼロコピー処理**: `array.array.tobytes()`によるメモリ効率改善
- **レスポンス遅延解決**: KITTIデータセット等の大容量データ処理を高速化

## 📋 対応アーキテクチャ

- ✅ **amd64** (x86_64) - 標準Linuxシステム
- ✅ **arm64** (AArch64) - Raspberry Pi 4、Apple Silicon、ARMサーバー

> **注意**: armhfアーキテクチャは公式ROS 2 Humbleパッケージが存在しないため非対応です。

## 🔧 動作環境

- Ubuntu 22.04 (Jammy Jellyfish)
- ROS 2 Humble Hawksbill
- Python 3.10+

## 📦 インストール・使用方法

> **注意**: このフォーク版は公式パッケージリポジトリでの配信をサポートしていません。GitHub Releasesからのダウンロードが必要です。

**ダウンロード**
1. [Releasesページ](https://github.com/aptpod/rosbridge_suite/releases)にアクセス
2. お使いのアーキテクチャに適したzipファイルをダウンロード

**インストール**
```bash
# 1. パッケージを展開
unzip rosbridge-suite-*-amd64.zip  # または arm64.zip

# 2. 依存関係をインストール
sudo apt update
sudo apt install -y python3-twisted python3-tornado python3-autobahn python3-pymongo python3-pil

# 3. パッケージをインストール
sudo apt install -y ./ros-humble-rosbridge-suite_*.deb
```

**使用方法**
```bash
# ROS 2環境をセットアップ
source /opt/ros/humble/setup.bash

# サーバーを起動（デフォルト：JSON専用モード）
ros2 launch rosbridge_server rosbridge_websocket_launch.xml

# BSON専用モードで起動
ros2 launch rosbridge_server rosbridge_websocket_launch.xml bson_only_mode:=true
```

WebSocketサーバーが `ws://localhost:9090` で利用可能になります。


## 📋 パッケージ構成

このパッケージには以下が含まれています：

- **rosbridge_library** - BSONサポート付きコア機能
- **rosbridge_server** - 強化されたメッセージ処理付きWebSocketサーバー
- **rosapi** - ROS APIサービスインターフェース
- **rosbridge_msgs** - プロトコルメッセージ定義
- **rosapi_msgs** - APIメッセージ定義
- **rosbridge_test_msgs** - テスト用メッセージ定義

## 📄 バージョニング戦略

上流とaptpod独自改良の両方を追跡するバージョニングスキームを使用：

**形式**: `[ディストリビューション]-[上流バージョン]+aptpod[フォークバージョン]([-プレリリース])`

**例**:
- `humble-2.0.1+aptpod0.0.1` - 安定版リリース
- `humble-2.0.1+aptpod0.0.1-beta.1` - プレリリース版

## 🔄 CI/CD自動ビルド

### GitHub Actions統合
このプロジェクトでは、継続的インテグレーションにより品質と互換性を保証しています：

- **自動テスト**: ROS 2 Humble環境でのビルド・テスト
- **統合テスト**: JSON/BSONモード両方の動作検証
- **マルチアーキテクチャビルド**: amd64/arm64対応
- **自動リリース**: タグpush時の自動パッケージ配布

### リリースノート
各リリースには最小限の情報が含まれ、詳細は本ドキュメントを参照するよう設計されています。

## 🙏 謝辞

本プロジェクトは[Robot Web Tools](https://robotwebtools.github.io/)コミュニティの優秀な成果の上に構築されています。基盤となるrosbridge_suite実装に感謝し、オリジナルプロジェクトの目標とコミュニティを尊重してこのフォークを維持しています。

**オリジナルプロジェクト**: https://github.com/RobotWebTools/rosbridge_suite

## 📞 サポート

- **aptpod固有の機能・問題**: このリポジトリでissueを作成
- **一般的なrosbridge**: オリジナルの[ROS wikiドキュメント](http://ros.org/wiki/rosbridge_suite)を参照

---

*この改良版は、産業用IoTおよびロボティクス用途向けにaptpod株式会社が保守しています。*
