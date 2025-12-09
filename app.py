"""
サブサーバーのメインアプリケーション
"""
from flask import Flask, request, jsonify, render_template
import requests
from datetime import datetime
import threading
import time
from config import SECRET_KEY, DEBUG, MASTER_SERVER_URL, CALLBACK_URL

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY

# 接続チェック結果を保存 (簡易的にメモリ保存)
connection_check_results = {}

# ポーリング中のリクエストを管理
polling_requests = {}

# ===========================
# HTTPエンドポイント
# ===========================

@app.route('/')
def index():
    """トップページ"""
    return render_template('index.html', 
                         master_server_url=MASTER_SERVER_URL,
                         callback_url=CALLBACK_URL)

@app.route('/api/check-connection', methods=['POST'])
def check_connection():
    """接続チェックリクエストを送信"""
    try:
        print(f"[INFO] 接続チェックリクエスト送信開始")
        print(f"[INFO] 本サーバーURL: {MASTER_SERVER_URL}/api/request")
        
        # 本サーバーにリクエスト送信
        response = requests.post(f"{MASTER_SERVER_URL}/api/request", json={
            'genre': 'connectioncheck',
            'callback_url': CALLBACK_URL  # これは形式的に残す
        }, timeout=10)
        
        print(f"[INFO] 本サーバーレスポンス: status={response.status_code}")
        
        if response.status_code == 201:
            data = response.json()
            request_id = data['request_id']
            
            print(f"[INFO] 接続チェックリクエスト送信成功: {request_id}")
            
            # 結果を初期化
            connection_check_results[request_id] = {
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            }
            
            # ポーリングを開始
            start_polling(request_id)
            
            return jsonify({
                'success': True,
                'request_id': request_id,
                'message': '接続チェックリクエストを送信しました'
            }), 200
        else:
            print(f"[ERROR] 本サーバーエラー: {response.status_code} - {response.text}")
            return jsonify({
                'success': False,
                'error': f'本サーバーエラー: {response.status_code}'
            }), 500
            
    except Exception as e:
        print(f"[ERROR] 接続チェックリクエスト送信エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def start_polling(request_id):
    """バックグラウンドでポーリング開始"""
    def poll():
        max_attempts = 30  # 最大30回（60秒）
        attempt = 0
        
        while attempt < max_attempts:
            try:
                print(f"[DEBUG] ポーリング試行 {attempt + 1}/{max_attempts}: request_id={request_id}")
                
                # 本サーバーに結果を問い合わせ
                response = requests.get(
                    f"{MASTER_SERVER_URL}/api/request-result/connectioncheck/{request_id}",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status')
                    
                    print(f"[DEBUG] ポーリング結果: status={status}")
                    
                    if status in ['success', 'failed', 'timeout']:
                        # 完了
                        connection_check_results[request_id] = {
                            'status': status,
                            'pc_id': data.get('locked_by'),
                            'received_at': datetime.now().isoformat()
                        }
                        print(f"[INFO] 接続チェック結果取得完了: {request_id} = {status}")
                        break
                    else:
                        # まだpending
                        print(f"[DEBUG] まだ処理中: {status}")
                
                elif response.status_code == 404:
                    print(f"[WARNING] リクエストが見つかりません: {request_id}")
                    break
                
            except Exception as e:
                print(f"[ERROR] ポーリングエラー: {e}")
            
            attempt += 1
            time.sleep(2)  # 2秒ごとにポーリング
        
        # タイムアウト
        if attempt >= max_attempts:
            connection_check_results[request_id] = {
                'status': 'timeout',
                'received_at': datetime.now().isoformat()
            }
            print(f"[WARNING] ポーリングタイムアウト: {request_id}")
    
    # バックグラウンドスレッドで実行
    thread = threading.Thread(target=poll, daemon=True)
    thread.start()
    polling_requests[request_id] = thread

@app.route('/api/callback', methods=['POST'])
def callback():
    """本サーバーからの結果受信 (使用しないが互換性のため残す)"""
    try:
        data = request.json
        
        print(f"[INFO] ===== コールバック受信 =====")
        print(f"[INFO] 受信データ: {data}")
        
        genre = data.get('genre')
        request_id = data.get('request_id')
        status = data.get('status')
        pc_id = data.get('pc_id')
        
        print(f"[INFO] コールバック詳細: genre={genre}, request_id={request_id}, status={status}, pc_id={pc_id}")
        
        # 結果を保存
        if genre == 'connectioncheck':
            connection_check_results[request_id] = {
                'status': status,
                'pc_id': pc_id,
                'received_at': datetime.now().isoformat()
            }
            print(f"[INFO] 接続チェック結果保存完了: {request_id} = {status}")
        
        print(f"[INFO] ===== コールバック処理完了 =====")
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        print(f"[ERROR] コールバック処理エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/check-result/<request_id>', methods=['GET'])
def get_check_result(request_id):
    """接続チェック結果を取得"""
    print(f"[INFO] 結果取得リクエスト: request_id={request_id}")
    
    result = connection_check_results.get(request_id)
    
    if result:
        print(f"[INFO] 結果返却: {result}")
        return jsonify(result), 200
    else:
        print(f"[WARNING] 結果が見つかりません: {request_id}")
        print(f"[INFO] 現在の結果一覧: {list(connection_check_results.keys())}")
        return jsonify({'error': 'Result not found'}), 404

# ===========================
# メイン処理
# ===========================

if __name__ == '__main__':
    print("=" * 60)
    print("サブサーバー起動")
    print("=" * 60)
    print(f"本サーバー: {MASTER_SERVER_URL}")
    print(f"コールバックURL: {CALLBACK_URL}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5001, debug=DEBUG)