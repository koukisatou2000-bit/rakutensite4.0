"""
サブサーバーのメインアプリケーション
"""
from flask import Flask, request, jsonify, render_template
import requests
from datetime import datetime
from config import SECRET_KEY, DEBUG, MASTER_SERVER_URL, CALLBACK_URL

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY

# 接続チェック結果を保存 (簡易的にメモリ保存)
connection_check_results = {}

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
        print(f"[INFO] コールバックURL: {CALLBACK_URL}")
        
        # 本サーバーにリクエスト送信
        response = requests.post(f"{MASTER_SERVER_URL}/api/request", json={
            'genre': 'connectioncheck',
            'callback_url': CALLBACK_URL
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
            
            print(f"[INFO] リクエスト結果初期化: {request_id} = pending")
            
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

@app.route('/api/callback', methods=['POST'])
def callback():
    """本サーバーからの結果受信"""
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
            print(f"[INFO] 現在の結果一覧: {connection_check_results}")
        else:
            print(f"[WARNING] 未知のジャンル: {genre}")
        
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

# ==========================
# メイン処理
# ==========================

if __name__ == '__main__':
    print("=" * 60)
    print("サブサーバー起動")
    print("=" * 60)
    print(f"本サーバー: {MASTER_SERVER_URL}")
    print(f"コールバックURL: {CALLBACK_URL}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5001, debug=DEBUG)