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

def try_click_element(page, selectors, element_name, timeout=5000):
    """
    複数のセレクタとクリック方法を試行
    
    Args:
        page: Playwrightのページオブジェクト
        selectors: 試行するセレクタのリスト
        element_name: 要素名（ログ用）
        timeout: タイムアウト時間（ms）
    
    Returns:
        bool: クリック成功ならTrue
    """
    for selector in selectors:
        try:
            log_with_timestamp("PLAYWRIGHT", f"{element_name}を試行: {selector}")
            element = page.wait_for_selector(selector, timeout=timeout)
            
            if not element:
                continue
            
            # 要素が見つかったことを確認
            log_with_timestamp("PLAYWRIGHT", f"要素発見: {selector}")
            
            # 要素が表示されているか確認
            is_visible = element.is_visible()
            log_with_timestamp("PLAYWRIGHT", f"要素の表示状態: {is_visible}")
            
            # クリック方法1: 通常のクリック
            try:
                log_with_timestamp("PLAYWRIGHT", "通常クリックを試行...")
                element.click(timeout=3000)
                log_with_timestamp("SUCCESS", f"{element_name}クリック成功（通常クリック）: {selector}")
                time.sleep(0.5)  # クリック後の短い待機
                return True
            except Exception as e:
                log_with_timestamp("PLAYWRIGHT", f"通常クリック失敗: {str(e)}, force clickを試行")
            
            # クリック方法2: force click
            try:
                log_with_timestamp("PLAYWRIGHT", "force clickを試行...")
                element.click(force=True, timeout=3000)
                log_with_timestamp("SUCCESS", f"{element_name}クリック成功（force click）: {selector}")
                time.sleep(0.5)
                return True
            except Exception as e:
                log_with_timestamp("PLAYWRIGHT", f"force click失敗: {str(e)}, JavaScriptクリックを試行")
            
            # クリック方法3: JavaScriptでクリック
            try:
                log_with_timestamp("PLAYWRIGHT", "JavaScriptクリックを試行...")
                page.evaluate('(element) => element.click()', element)
                log_with_timestamp("SUCCESS", f"{element_name}クリック成功（JSクリック）: {selector}")
                time.sleep(0.5)
                return True
            except Exception as e:
                log_with_timestamp("PLAYWRIGHT", f"JSクリック失敗: {str(e)}")
            
            # クリック方法4: dispatchEventでクリック
            try:
                log_with_timestamp("PLAYWRIGHT", "dispatchEventクリックを試行...")
                page.evaluate('''(element) => {
                    element.dispatchEvent(new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true
                    }));
                }''', element)
                log_with_timestamp("SUCCESS", f"{element_name}クリック成功（dispatchEvent）: {selector}")
                time.sleep(0.5)
                return True
            except Exception as e:
                log_with_timestamp("PLAYWRIGHT", f"dispatchEventクリック失敗: {str(e)}")
                
        except Exception as e:
            log_with_timestamp("DEBUG", f"{selector} で要素が見つかりませんでした: {str(e)}")
            continue
    
    log_with_timestamp("ERROR", f"{element_name}のクリックに失敗しました")
    return False

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
            log_with_timestamp("PLAYWRIGHT", "ブラウザ起動完了")
            
            # ステップ1: 楽天トップページにアクセス
            log_with_timestamp("PLAYWRIGHT", "楽天トップページにアクセス中...")
            page.goto("https://my.rakuten.co.jp/", timeout=30000)
            
            # ログインボタンをクリック
            login_selectors = ["#btn-sign-in", "button:has-text('ログイン')", "[id*='sign-in']"]
            if not try_click_element(page, login_selectors, "ログインボタン", 5000):
                browser.close()
                return False
            
            # ステップ2: メールアドレス入力ページ
            log_with_timestamp("PLAYWRIGHT", "メールアドレス入力フィールド待機中...")
            email_selectors = ["#user_id", "input[type='email']", "input[name='user_id']"]
            
            email_field = None
            for selector in email_selectors:
                try:
                    log_with_timestamp("PLAYWRIGHT", f"メールアドレス欄を試行: {selector}")
                    email_field = page.wait_for_selector(selector, timeout=5000)
                    if email_field:
                        email_field.fill(email)
                        log_with_timestamp("SUCCESS", f"メールアドレス入力完了: {selector}")
                        break
                except:
                    continue
            
            if not email_field:
                log_with_timestamp("ERROR", "メールアドレス入力欄が見つかりません（5秒タイムアウト）")
                browser.close()
                return False
            
            # 次へボタンをクリック（複数の方法を試行）
            next_button_selectors = [
                "#cta001",
                "div[id='cta001']",
                "div[role='button']:has-text('次へ')",
                "button:has-text('次へ')",
                "[tabindex='0']:has-text('次へ')",
                ".sbt:has-text('次へ')"
            ]
            
            if not try_click_element(page, next_button_selectors, "次へボタン（メール画面）", 5000):
                browser.close()
                return False
            
            log_with_timestamp("PLAYWRIGHT", f"次へクリック後のURL: {page.url}")
            
            # ステップ3: パスワード入力ページ
            log_with_timestamp("PLAYWRIGHT", "パスワード入力フィールド待機中...")
            password_selectors = [
                "#password_current",
                "input[type='password']",
                "input[name='password']",
                "input[autocomplete='current-password']",
                "input[aria-label='パスワード']",
                ".it[type='password']",
                "input.it[type='password']"
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
                except Exception as e:
                    log_with_timestamp("DEBUG", f"{selector} 失敗: {str(e)}")
                    continue
            
            if not password_field:
                log_with_timestamp("ERROR", "パスワード入力欄が見つかりません（5秒タイムアウト）")
                browser.close()
                return False
            
            # ログインボタンをクリック（複数の方法を試行）
            login_button_selectors = [
                "#cta011",
                "div[id='cta011']",
                "div[role='button']:has-text('ログイン')",
                "button:has-text('ログイン')",
                "[tabindex='0']:has-text('ログイン')",
                ".sbt:has-text('ログイン')"
            ]
            
            # クリック前のURLを記録
            url_before_click = page.url
            log_with_timestamp("PLAYWRIGHT", f"ログインボタンクリック前URL: {url_before_click}")
            
            if not try_click_element(page, login_button_selectors, "ログインボタン（パスワード画面）", 5000):
                browser.close()
                return False
            
            # クリック直後のURL確認
            time.sleep(1)
            url_after_click = page.url
            log_with_timestamp("PLAYWRIGHT", f"ログインボタンクリック後URL（1秒後）: {url_after_click}")
            
            if url_after_click != url_before_click:
                log_with_timestamp("PLAYWRIGHT", "URLが即座に変化 - クリック成功確認")
            else:
                log_with_timestamp("WARNING", "URLが変化していない - ボタンが押せていない可能性")
            
            # ステップ4: URL変化を監視（最大20秒）
            max_wait = 20
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