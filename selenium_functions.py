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
    各要素は5秒以内に出現しなければタイムアウト
    
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
            page.set_default_timeout(5000)  # デフォルトタイムアウトを5秒に設定
            log_with_timestamp("PLAYWRIGHT", "ブラウザ起動完了")
            
            # ステップ1: 楽天トップページにアクセス
            log_with_timestamp("PLAYWRIGHT", "楽天トップページにアクセス中...")
            page.goto("https://my.rakuten.co.jp/", timeout=30000)
            
            # ログインボタンをクリック
            try:
                log_with_timestamp("PLAYWRIGHT", "ログインボタン待機中...")
                login_button = page.wait_for_selector("#btn-sign-in", timeout=5000)
                login_button.click(timeout=3000)
                log_with_timestamp("SUCCESS", "ログインボタンクリック完了")
            except Exception as e:
                log_with_timestamp("ERROR", f"ログインボタン処理失敗: {str(e)}")
                browser.close()
                return False
            
            # ステップ2: メールアドレス入力ページ
            log_with_timestamp("PLAYWRIGHT", "メールアドレス入力フィールド待機中...")
            try:
                email_field = page.wait_for_selector("#user_id", timeout=5000)
                email_field.fill(email)
                log_with_timestamp("SUCCESS", "メールアドレス入力完了")
            except Exception as e:
                log_with_timestamp("ERROR", f"メールアドレス入力失敗: {str(e)}")
                browser.close()
                return False
            
            # 次へボタンをクリック
            try:
                log_with_timestamp("PLAYWRIGHT", "次へボタン（メール画面）待機中...")
                next_button_1 = page.wait_for_selector("#cta001", timeout=5000)
                next_button_1.click(timeout=3000)
                log_with_timestamp("SUCCESS", "次へボタンクリック完了")
            except Exception as e:
                log_with_timestamp("ERROR", f"次へボタン処理失敗: {str(e)}")
                browser.close()
                return False
            
            # ステップ3: パスワード入力ページ
            log_with_timestamp("PLAYWRIGHT", "パスワード入力フィールド待機中...")
            password_selectors = [
                "#password_current",
                "input[type='password']",
                "input[name='password']",
                "input[autocomplete='current-password']"
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    log_with_timestamp("PLAYWRIGHT", f"パスワード欄を試行: {selector}")
                    password_field = page.wait_for_selector(selector, timeout=5000)
                    if password_field:
                        password_field.fill(password)
                        log_with_timestamp("SUCCESS", f"パスワード入力完了: {selector}")
                        break
                except:
                    continue
            
            if not password_field:
                log_with_timestamp("ERROR", "パスワード入力欄が見つかりません")
                browser.close()
                return False
            
            # クリック前のURLを記録
            url_before_submit = page.url
            log_with_timestamp("PLAYWRIGHT", f"送信前URL: {url_before_submit}")
            
            # 方法1: Enterキーで送信を試みる
            log_with_timestamp("PLAYWRIGHT", "Enterキーで送信を試行...")
            try:
                password_field.press("Enter")
                log_with_timestamp("SUCCESS", "Enterキー送信完了")
                time.sleep(1.5)
                
                # URL変化を確認
                current_url = page.url
                if current_url != url_before_submit:
                    log_with_timestamp("SUCCESS", "Enterキーで送信成功 - URL監視開始")
                else:
                    log_with_timestamp("PLAYWRIGHT", "Enterキーでは送信されなかった - ボタンクリックを試行")
                    
                    # 方法2: ログインボタンをクリック（複数方法を試行）
                    submit_success = False
                    
                    # 2-1: 通常クリック
                    try:
                        log_with_timestamp("PLAYWRIGHT", "ログインボタン（#cta011）待機中...")
                        login_button = page.wait_for_selector("#cta011", timeout=3000)
                        log_with_timestamp("PLAYWRIGHT", "通常クリックを試行...")
                        login_button.click(timeout=2000)
                        log_with_timestamp("SUCCESS", "通常クリック完了")
                        submit_success = True
                    except Exception as e:
                        log_with_timestamp("PLAYWRIGHT", f"通常クリック失敗: {str(e)}")
                    
                    # 2-2: Force click
                    if not submit_success:
                        try:
                            log_with_timestamp("PLAYWRIGHT", "force clickを試行...")
                            login_button = page.wait_for_selector("#cta011", timeout=2000)
                            login_button.click(force=True, timeout=2000)
                            log_with_timestamp("SUCCESS", "force click完了")
                            submit_success = True
                        except Exception as e:
                            log_with_timestamp("PLAYWRIGHT", f"force click失敗: {str(e)}")
                    
                    # 2-3: JavaScript click
                    if not submit_success:
                        try:
                            log_with_timestamp("PLAYWRIGHT", "JavaScriptクリックを試行...")
                            page.evaluate('document.querySelector("#cta011").click()')
                            log_with_timestamp("SUCCESS", "JSクリック完了")
                            submit_success = True
                        except Exception as e:
                            log_with_timestamp("PLAYWRIGHT", f"JSクリック失敗: {str(e)}")
                    
                    # 2-4: フォームsubmit
                    if not submit_success:
                        try:
                            log_with_timestamp("PLAYWRIGHT", "フォームsubmitを試行...")
                            page.evaluate('''
                                const form = document.querySelector('form');
                                if (form) {
                                    form.submit();
                                }
                            ''')
                            log_with_timestamp("SUCCESS", "フォームsubmit完了")
                            submit_success = True
                        except Exception as e:
                            log_with_timestamp("ERROR", f"フォームsubmit失敗: {str(e)}")
                    
                    if submit_success:
                        time.sleep(1.5)
                    else:
                        log_with_timestamp("ERROR", "すべての送信方法が失敗しました")
                        browser.close()
                        return False
                        
            except Exception as e:
                log_with_timestamp("ERROR", f"送信処理でエラー: {str(e)}")
                browser.close()
                return False
            
            # ステップ4: URL変化を監視（最大20秒）
            log_with_timestamp("PLAYWRIGHT", "URL監視開始")
            max_wait = 20
            start_time = time.time()
            last_log_time = start_time
            
            while time.time() - start_time < max_wait:
                elapsed = time.time() - start_time
                current_url = page.url
                
                # 2秒ごとにログ出力
                if time.time() - last_log_time >= 2:
                    log_with_timestamp("PLAYWRIGHT", f"URL監視中... ({int(elapsed)}秒経過)")
                    last_log_time = time.time()
                
                # 成功判定: URLが変わった
                if current_url != url_before_submit:
                    log_with_timestamp("SUCCESS", f"ログイン成功（URL変化検出） | Email: {email} | 所要時間: {int(elapsed)}秒")
                    log_with_timestamp("PLAYWRIGHT", f"変化後URL: {current_url}")
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