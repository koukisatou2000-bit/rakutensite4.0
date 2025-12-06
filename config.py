"""
サブサーバーの設定ファイル
"""
import os

# Flask設定
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# 本サーバーのURL (Renderにデプロイ後に変更)
MASTER_SERVER_URL = os.environ.get('MASTER_SERVER_URL', 'https://your-master-server.onrender.com')

# このサブサーバーのURL (Renderにデプロイ後に変更)
CALLBACK_URL = os.environ.get('CALLBACK_URL', 'https://your-sub-server.onrender.com/api/callback')