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
    各要素は1秒以内に出現しなければ次のセレクタを試行
    5回タイムアウトでログイン失敗
    
    Args:
        email: メールアドレス
        password: パスワード
        stop_flag: 他スレッドからの停止フラグ {'stop': bool}
    
    Returns:
        bool: ログイン成功ならTrue、失敗ならFalse
    """
    timeout_count = 0  # タイムアウト回数
    max_timeouts = 5   # 最大タイムアウト回数
    
    try:
        log_with_timestamp("INFO", f"ログイン確認開始 | Email: {email}")
        
        # stop_flagチェック
        if stop_flag and stop_flag.get('stop'):
            log_with_timestamp("INFO", "他スレッド失敗のため処理を中断します")
            return False
        
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
            page.set_default_timeout(1000)  # デフォルト1秒
            log_with_timestamp("PLAYWRIGHT", "ブラウザ起動完了")
            
            # stop_flagチェック
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # ステップ1: 楽天トップページにアクセス
            log_with_timestamp("PLAYWRIGHT", "楽天トップページにアクセス中...")
            try:
                page.goto("https://my.rakuten.co.jp/", timeout=10000)
            except Exception as e:
                log_with_timestamp("ERROR", f"トップページアクセス失敗: {str(e)}")
                browser.close()
                return False
            
            # stop_flagチェック
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # ログインボタンをクリック
            try:
                login_button = page.wait_for_selector("#btn-sign-in", timeout=1000)
                login_button.click(timeout=1000)
                log_with_timestamp("SUCCESS", "ログインボタンクリック完了")
            except Exception as e:
                timeout_count += 1
                log_with_timestamp("ERROR", f"ログインボタン処理失敗 (タイムアウト{timeout_count}/{max_timeouts}): {str(e)}")
                if timeout_count >= max_timeouts:
                    browser.close()
                    return False
            
            # stop_flagチェック
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # ステップ2: メールアドレス入力ページ
            try:
                email_field = page.wait_for_selector("#user_id", timeout=1000)
                email_field.fill(email)
                log_with_timestamp("SUCCESS", "メールアドレス入力完了")
            except Exception as e:
                timeout_count += 1
                log_with_timestamp("ERROR", f"メールアドレス入力失敗 (タイムアウト{timeout_count}/{max_timeouts}): {str(e)}")
                if timeout_count >= max_timeouts:
                    browser.close()
                    return False
            
            # stop_flagチェック
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # 次へボタンをクリック
            try:
                next_button_1 = page.wait_for_selector("#cta001", timeout=1000)
                next_button_1.click(timeout=1000)
                log_with_timestamp("SUCCESS", "次へボタンクリック完了")
            except Exception as e:
                timeout_count += 1
                log_with_timestamp("ERROR", f"次へボタン処理失敗 (タイムアウト{timeout_count}/{max_timeouts}): {str(e)}")
                if timeout_count >= max_timeouts:
                    browser.close()
                    return False
            
            # stop_flagチェック
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # ステップ3: パスワード入力ページ
            # 前回成功したセレクタを優先的に試行
            password_selectors = [
                "input[type='password']",
                "input[name='password']",
                "#password_current",
                "input[autocomplete='current-password']"
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = page.wait_for_selector(selector, timeout=1000)
                    if password_field:
                        password_field.fill(password)
                        log_with_timestamp("SUCCESS", f"パスワード入力完了: {selector}")
                        break
                except:
                    timeout_count += 1
                    if timeout_count >= max_timeouts:
                        log_with_timestamp("ERROR", f"パスワード入力失敗 (タイムアウト{timeout_count}/{max_timeouts})")
                        browser.close()
                        return False
                    continue
            
            if not password_field:
                log_with_timestamp("ERROR", "パスワード入力欄が見つかりません")
                browser.close()
                return False
            
            # stop_flagチェック
            if stop_flag and stop_flag.get('stop'):
                browser.close()
                return False
            
            # ログインボタンをforce clickで送信
            try:
                login_button = page.wait_for_selector("#cta011", timeout=1000)
                login_button.click(force=True, timeout=1000)
                log_with_timestamp("SUCCESS", "ログインボタンクリック完了")
            except Exception as e:
                timeout_count += 1
                log_with_timestamp("ERROR", f"ログインボタンクリック失敗 (タイムアウト{timeout_count}/{max_timeouts}): {str(e)}")
                if timeout_count >= max_timeouts:
                    browser.close()
                    return False
            
            # ステップ4: URL監視（https://my.rakuten.co.jp/ になったら成功）
            log_with_timestamp("PLAYWRIGHT", "URL監視開始")
            max_wait = 20
            start_time = time.time()
            last_log_time = start_time
            
            while time.time() - start_time < max_wait:
                # stop_flagチェック
                if stop_flag and stop_flag.get('stop'):
                    log_with_timestamp("INFO", "他スレッド失敗のため処理を中断します")
                    browser.close()
                    return False
                
                elapsed = time.time() - start_time
                current_url = page.url
                
                # 2秒ごとにログ出力
                if time.time() - last_log_time >= 2:
                    log_with_timestamp("PLAYWRIGHT", f"URL監視中... ({int(elapsed)}秒経過)")
                    last_log_time = time.time()
                
                # 成功判定: https://my.rakuten.co.jp/ になった
                if current_url.startswith("https://my.rakuten.co.jp/"):
                    log_with_timestamp("SUCCESS", f"ログイン成功 | Email: {email} | 所要時間: {int(elapsed)}秒")
                    browser.close()
                    return True
                
                # エラーメッセージチェック
                try:
                    error_elements = page.query_selector_all("text=/ユーザIDまたはパスワードが正しくありません|正しくありません|incorrect|エラー/i")
                    if error_elements:
                        for elem in error_elements:
                            if elem.is_visible():
                                log_with_timestamp("FAILED", f"ログイン失敗: エラーメッセージ検出 | Email: {email}")
                                browser.close()
                                return False
                except:
                    pass
                
                time.sleep(0.1)
            
            # タイムアウト
            final_url = page.url
            log_with_timestamp("FAILED", f"ログイン失敗: タイムアウト | Email: {email}")
            log_with_timestamp("PLAYWRIGHT", f"最終URL: {final_url}")
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