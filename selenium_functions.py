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

def rakuten_login_check(email, password):
    """
    楽天サイトにログインできるかチェック
    
    Args:
        email: メールアドレス
        password: パスワード
    
    Returns:
        bool: ログイン成功ならTrue、失敗ならFalse
    """
    try:
        log_with_timestamp("INFO", f"ログイン確認開始 | Email: {email}")
        
        with sync_playwright() as p:
            # ヘッドレスブラウザ起動
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
            log_with_timestamp("PLAYWRIGHT", "ブラウザ起動完了")
            
            # 楽天ログインページにアクセス
            log_with_timestamp("PLAYWRIGHT", "楽天ログインページにアクセス中...")
            page.goto("https://portal.mobile.rakuten.co.jp/dashboard#plans", timeout=30000)
            
            # メールアドレス入力
            log_with_timestamp("PLAYWRIGHT", "メールアドレス入力フィールド待機中...")
            email_field = page.wait_for_selector("input[type='text'], input[type='email']", timeout=15000)
            email_field.clear()
            email_field.fill(email)
            log_with_timestamp("PLAYWRIGHT", "メールアドレス入力完了")
            
            # 次へボタンクリック
            log_with_timestamp("PLAYWRIGHT", "次へボタンをクリック中...")
            next_button = page.wait_for_selector("#cta001", timeout=15000)
            next_button.click()
            log_with_timestamp("PLAYWRIGHT", "次へボタンクリック完了")
            
            # パスワード入力画面待機
            log_with_timestamp("PLAYWRIGHT", "パスワード入力フィールド待機中...")
            password_field = page.wait_for_selector("input[type='password']", timeout=15000)
            
            # パスワード入力
            log_with_timestamp("PLAYWRIGHT", "パスワード入力中...")
            password_field.clear()
            password_field.fill(password)
            log_with_timestamp("PLAYWRIGHT", "パスワード入力完了")
            
            # ENTERキーで送信
            log_with_timestamp("PLAYWRIGHT", "ENTERキーでログイン送信中...")
            password_field.press("Enter")
            log_with_timestamp("PLAYWRIGHT", "ログイン送信完了 - URL監視開始")
            
            # URL監視（最大60秒）
            max_wait = 60
            start_time = time.time()
            last_log_time = start_time
            
            while time.time() - start_time < max_wait:
                elapsed = time.time() - start_time
                current_url = page.url
                
                # 2秒ごとにログ出力
                if time.time() - last_log_time >= 2:
                    log_with_timestamp("PLAYWRIGHT", f"URL監視中... ({int(elapsed)}秒経過) | Current: {current_url}")
                    last_log_time = time.time()
                
                # 成功判定（複数パターン）
                if any([
                    "/dashboard" in current_url and "/auth/callback" not in current_url and "sign_in" not in current_url,
                    current_url.endswith("/dashboard"),
                    current_url.endswith("/dashboard#plans")
                ]):
                    log_with_timestamp("SUCCESS", f"ログイン成功 | Email: {email} | 所要時間: {int(elapsed)}秒")
                    browser.close()
                    return True
                
                # エラーメッセージチェック
                if "login" in current_url or "grp01" in current_url or "sign_in" in current_url:
                    try:
                        error_elements = page.query_selector_all("//*[contains(text(), 'ユーザIDまたはパスワードが正しくありません') or contains(text(), '正しくありません') or contains(text(), 'incorrect')]")
                        if error_elements:
                            for elem in error_elements:
                                if elem.is_visible():
                                    log_with_timestamp("FAILED", f"ログイン失敗: エラーメッセージ検出 | Email: {email}")
                                    browser.close()
                                    return False
                    except:
                        pass
                
                # 0.1秒間隔でチェック
                time.sleep(0.1)
            
            # タイムアウト
            final_url = page.url
            log_with_timestamp("FAILED", f"ログイン失敗: タイムアウト（dashboardに到達せず） | Email: {email}")
            log_with_timestamp("PLAYWRIGHT", f"最終URL: {final_url}")
            browser.close()
            return False
                
    except PlaywrightTimeout as e:
        log_with_timestamp("ERROR", f"Playwrightタイムアウト | Email: {email} | Error: {str(e)}")
        return False
    except Exception as e:
        log_with_timestamp("ERROR", f"Playwrightエラー発生 | Email: {email} | Error: {str(e)}")
        return False