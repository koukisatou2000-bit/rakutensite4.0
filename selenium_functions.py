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
            
            # ステップ1: 楽天トップページにアクセス
            log_with_timestamp("PLAYWRIGHT", "楽天トップページにアクセス中...")
            page.goto("https://my.rakuten.co.jp/", timeout=30000)
            
            # ログインボタンをクリック
            log_with_timestamp("PLAYWRIGHT", "ログインボタン待機中...")
            login_button = page.wait_for_selector("#btn-sign-in", timeout=15000)
            login_button.click()
            log_with_timestamp("PLAYWRIGHT", "ログインボタンクリック完了")
            
            # ステップ2: メールアドレス入力ページ
            log_with_timestamp("PLAYWRIGHT", "メールアドレス入力フィールド待機中...")
            email_field = page.wait_for_selector("#user_id", timeout=15000)
            email_field.fill(email)
            log_with_timestamp("PLAYWRIGHT", "メールアドレス入力完了")
            
            # 次へボタンクリック
            log_with_timestamp("PLAYWRIGHT", "次へボタン（メール画面）をクリック中...")
            next_button_1 = page.wait_for_selector("#cta001", timeout=15000)
            next_button_1.click()
            log_with_timestamp("PLAYWRIGHT", "次へボタンクリック完了")
            
            # ページ遷移を待つ（URLが変わるまで待機）
            log_with_timestamp("PLAYWRIGHT", "ページ遷移待機中...")
            page.wait_for_load_state("networkidle", timeout=15000)
            log_with_timestamp("PLAYWRIGHT", f"遷移後URL: {page.url}")
            
            # ステップ3: パスワード入力ページ（複数のセレクタを試す）
            log_with_timestamp("PLAYWRIGHT", "パスワード入力フィールド待機中...")
            
            # まず #password_current を試す
            password_field = None
            try:
                password_field = page.wait_for_selector("#password_current", timeout=5000)
                log_with_timestamp("PLAYWRIGHT", "パスワードフィールド検出: #password_current")
            except:
                log_with_timestamp("PLAYWRIGHT", "#password_current が見つからない、別のセレクタを試します...")
                
                # 代替セレクタを試す
                try:
                    password_field = page.wait_for_selector("input[type='password']", timeout=5000)
                    log_with_timestamp("PLAYWRIGHT", "パスワードフィールド検出: input[type='password']")
                except:
                    log_with_timestamp("ERROR", "パスワードフィールドが見つかりません")
                    browser.close()
                    return False
            
            if not password_field:
                log_with_timestamp("ERROR", "パスワードフィールドが見つかりません")
                browser.close()
                return False
            password_field.fill(password)
            log_with_timestamp("PLAYWRIGHT", "パスワード入力完了")
            
            # ログインボタンクリック
            log_with_timestamp("PLAYWRIGHT", "ログインボタン（パスワード画面）をクリック中...")
            next_button_2 = page.wait_for_selector("#cta011", timeout=15000)
            
            # クリック前のURLを記録
            url_before_click = page.url
            log_with_timestamp("PLAYWRIGHT", f"クリック前URL: {url_before_click}")
            
            next_button_2.click()
            log_with_timestamp("PLAYWRIGHT", "ログインボタンクリック完了 - URL監視開始")
            
            # ステップ4: URL変化を監視（最大60秒）
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
                
                # 成功判定: URLが変わった
                if current_url != url_before_click:
                    log_with_timestamp("SUCCESS", f"ログイン成功（URL変化検出） | Email: {email} | 所要時間: {int(elapsed)}秒")
                    log_with_timestamp("PLAYWRIGHT", f"変化後URL: {current_url}")
                    browser.close()
                    return True
                
                # エラーメッセージチェック
                try:
                    error_elements = page.query_selector_all("text=/ユーザIDまたはパスワードが正しくありません|正しくありません|incorrect/i")
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
            log_with_timestamp("FAILED", f"ログイン失敗: タイムアウト（URL変化なし） | Email: {email}")
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