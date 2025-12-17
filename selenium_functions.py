"""
サブサーバー用の楽天ログイン確認処理
ヘッドレスブラウザ（Playwright）で実際のサイトにログインし、成功/失敗を判定
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import time
from datetime import datetime

def log_with_timestamp(level, message):
    """タイムスタンプ付きログ出力"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] [SUB-SERVER] [{level}] {message}")

def rakuten_login_check(email, password, stop_flag=None):
    """
    楽天サイトにログインできるかチェック
    
    Args:
        email: メールアドレス
        password: パスワード
        stop_flag: 他スレッドからの停止フラグ {'stop': bool}
    
    Returns:
        bool: ログイン成功ならTrue、失敗ならFalse
    """
    try:
        log_with_timestamp("INFO", f"ログイン確認開始 | Email: {email}")
        
        if stop_flag and stop_flag.get('stop'):
            log_with_timestamp("INFO", "他スレッド失敗のため処理を中断します")
            return False
        
        with sync_playwright() as p:
            log_with_timestamp("PLAYWRIGHT", "ブラウザ起動中...")
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            context = browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            page = context.new_page()
            page.set_default_timeout(30000)  # 30秒に延長
            log_with_timestamp("PLAYWRIGHT", "ブラウザ起動完了")
            
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # トップページアクセス
            log_with_timestamp("PLAYWRIGHT", "楽天トップページにアクセス中...")
            try:
                page.goto("https://my.rakuten.co.jp/", timeout=30000)
                time.sleep(2)  # 2秒待機
            except Exception as e:
                log_with_timestamp("ERROR", f"トップページアクセス失敗: {str(e)}")
                browser.close()
                return False
            
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # ログインボタンクリック
            try:
                login_button = page.wait_for_selector("#btn-sign-in", timeout=30000)
                login_button.click()
                log_with_timestamp("SUCCESS", "ログインボタンクリック完了")
                time.sleep(2)  # 2秒待機
            except Exception as e:
                log_with_timestamp("ERROR", f"ログインボタン処理失敗: {str(e)}")
                browser.close()
                return False
            
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # メールアドレス入力
            try:
                email_field = page.wait_for_selector("#user_id", timeout=30000)
                email_field.fill(email)
                log_with_timestamp("SUCCESS", "メールアドレス入力完了")
                time.sleep(1)
            except Exception as e:
                log_with_timestamp("ERROR", f"メールアドレス入力失敗: {str(e)}")
                browser.close()
                return False
            
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # 次へボタンクリック
            try:
                next_button = page.wait_for_selector("#cta001", timeout=30000)
                next_button.click()
                log_with_timestamp("SUCCESS", "次へボタンクリック完了")
                time.sleep(5)  # ★★★ 5秒待機に延長 ★★★
            except Exception as e:
                log_with_timestamp("ERROR", f"次へボタン処理失敗: {str(e)}")
                browser.close()
                return False
            
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # パスワード入力
            try:
                # パスワードフィールドが表示されるまで待機
                password_field = page.wait_for_selector("input[type='password']", timeout=30000)
                password_field.fill(password)
                log_with_timestamp("SUCCESS", "パスワード入力完了")
                time.sleep(1)
            except Exception as e:
                log_with_timestamp("ERROR", f"パスワード入力失敗: {str(e)}")
                browser.close()
                return False
            
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # Enterキーでログイン送信
            log_with_timestamp("PLAYWRIGHT", "ログイン送信中...")
            try:
                password_field.press("Enter")
                log_with_timestamp("SUCCESS", "Enter送信完了")
                time.sleep(2)
            except Exception as e:
                log_with_timestamp("ERROR", f"Enter送信失敗: {str(e)}")
                browser.close()
                return False
            
            # URL変化を待機（最大15秒）
            log_with_timestamp("PLAYWRIGHT", "URL変化を待機中（最大15秒）...")
            try:
                # パスワード画面から抜けたら成功
                page.wait_for_url(lambda url: "#/sign_in/password" not in url, timeout=15000)
                log_with_timestamp("SUCCESS", f"ログイン成功 | Email: {email}")
                log_with_timestamp("SUCCESS", f"最終URL: {page.url}")
                browser.close()
                return True
            except:
                log_with_timestamp("WARNING", "URL変化タイムアウト - 現在のURLを確認中...")
                current_url = page.url
                log_with_timestamp("PLAYWRIGHT", f"現在のURL: {current_url}")
                
                # パスワード画面から変化していればログイン成功と判断
                if "#/sign_in/password" not in current_url:
                    log_with_timestamp("SUCCESS", f"ログイン成功（URL確認） | Email: {email}")
                    log_with_timestamp("SUCCESS", f"最終URL: {current_url}")
                    browser.close()
                    return True
                else:
                    log_with_timestamp("FAILED", f"ログイン失敗 | Email: {email}")
                    log_with_timestamp("PLAYWRIGHT", f"最終URL: {current_url}")
                    browser.close()
                    return False
                
    except PlaywrightTimeout as e:
        log_with_timestamp("ERROR", f"Playwrightタイムアウト | Email: {email} | Error: {str(e)}")
        return False
    except Exception as e:
        log_with_timestamp("ERROR", f"Playwrightエラー発生 | Email: {email} | Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False