# core/douyin_client.py
"""抖音集成：通过 Playwright 启动真实浏览器，用户扫码登录后获取关注列表与直播状态。

安全策略（降低封号风险）：
1. 冷却时间：两次同步关注列表至少间隔 1 小时，避免高频请求
2. 随机延迟：页面跳转、滚动间加入 2~5 秒随机等待，模拟人类行为
3. 抓取上限：默认只拉第一页（约 20 条），最多不超过 50 条
4. 反检测：隐藏 webdriver 特征、使用真实 UA、随机 viewport
5. 登录态持久化：避免重复登录触发风控
"""
import asyncio
import json
import logging
import random
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Response

logger = logging.getLogger(__name__)

# 后端根目录（core/ 的上一级）
BACKEND_DIR = Path(__file__).resolve().parent.parent

# 持久化浏览器数据目录（保存登录态 cookie）
USER_DATA_DIR = BACKEND_DIR / "data" / "douyin_browser"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# 冷却文件（记录上次同步时间）
COOLDOWN_FILE = BACKEND_DIR / "data" / "douyin_sync_cooldown.json"

# 弹幕去重集合上限：只保留最近这么多条用于判重，防止长场次内存无上限增长
SEEN_LIMIT = 5000

# 登录态快照文件（storage_state 保存的 cookie，用于重启后判断登录状态）
STATE_FILE = BACKEND_DIR / "data" / "douyin_state.json"

# 安全限制
SYNC_COOLDOWN_SECONDS = 3600  # 两次同步至少间隔 1 小时
DEFAULT_MAX_FOLLOWING = 200   # 默认最多拉取条数
MAX_FOLLOWING_LIMIT = 500     # 绝对上限，防止过度爬取

DOUYIN_HOME = "https://www.douyin.com"
# 自己主页的关注 tab（注意：/user/following 是错误地址，会被当成用户 ID）
DOUYIN_SELF_FOLLOWING = "https://www.douyin.com/user/self?showTab=following"


def _human_delay(min_s: float = 2.0, max_s: float = 5.0):
    """模拟人类操作的随机延迟"""
    return asyncio.sleep(random.uniform(min_s, max_s))


def _get_last_sync_time() -> float:
    """读取上次同步时间戳"""
    try:
        if COOLDOWN_FILE.exists():
            data = json.loads(COOLDOWN_FILE.read_text(encoding="utf-8"))
            return float(data.get("last_sync", 0))
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as e:
        # 冷却文件损坏不影响主功能，按「从未同步」处理即可，但记一笔便于排查
        logger.warning("同步冷却文件读取失败，按未同步处理：%s", e)
    return 0.0


def _set_last_sync_time():
    """记录本次同步时间戳"""
    try:
        COOLDOWN_FILE.write_text(
            json.dumps({"last_sync": time.time()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        # 写不进去只会退化成「冷却不生效」，不影响采集本身
        logger.warning("同步冷却文件写入失败（本次冷却将不生效）：%s", e)


def get_cooldown_remaining() -> int:
    """获取冷却剩余秒数，<=0 表示可以同步"""
    elapsed = time.time() - _get_last_sync_time()
    return max(0, int(SYNC_COOLDOWN_SECONDS - elapsed))


class DouyinClient:
    """抖音浏览器自动化客户端"""

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._login_event = asyncio.Event()
        # 直播间弹幕采集状态
        self._capture_page: Optional[Page] = None
        self._capture_task: Optional[asyncio.Task] = None
        self._capturing = False

    @property
    def is_capturing(self) -> bool:
        return self._capturing

    async def start(self, headless: bool = False):
        """启动浏览器（持久化登录态 + 反检测配置）

        若上下文已被用户手动关闭（TargetClosedError），自动重启。
        """
        if self._context:
            try:
                _ = self._context.pages  # 探测上下文是否存活
                return
            except Exception:
                self._context = None
                self._page = None
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=headless,
            viewport={"width": random.choice([1280, 1366, 1440, 1536]), "height": random.choice([720, 800, 864, 900])},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        # 注入脚本隐藏 webdriver 特征
        await self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            "Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});"
            "Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});"
        )

    async def is_logged_in(self) -> bool:
        """检查是否已登录抖音

        优先检查运行中浏览器的实时 cookie；
        浏览器未启动时检查登录后保存的快照文件（后端重启后依然有效）。
        """
        if self._context:
            try:
                cookies = await self._context.cookies(DOUYIN_HOME)
                cookie_names = {c["name"] for c in cookies}
                # sessionid 是抖音登录态的核心 cookie
                if "sessionid" in cookie_names or "sessionid_ss" in cookie_names:
                    return True
            except Exception:
                pass  # 浏览器可能已关闭，退回检查快照文件
        return self._state_file_has_session()

    def _state_file_has_session(self) -> bool:
        """从快照文件检查登录态（含 cookie 过期时间校验）"""
        try:
            if not STATE_FILE.exists():
                return False
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            now = time.time()
            for c in data.get("cookies", []):
                if c.get("name") in ("sessionid", "sessionid_ss"):
                    expires = c.get("expires", -1)
                    # -1 表示会话 cookie（无固定过期时间），视为有效
                    if not expires or expires == -1 or expires > now:
                        return True
            return False
        except Exception:
            return False

    async def save_login_state(self):
        """把当前登录态（cookie + localStorage）保存到快照文件"""
        if not self._context:
            return
        try:
            await self._context.storage_state(path=str(STATE_FILE))
        except Exception:
            pass

    async def open_login(self):
        """打开抖音首页供用户扫码登录"""
        await self.start(headless=False)
        await self._page.goto(DOUYIN_HOME, wait_until="domcontentloaded", timeout=30000)
        await _human_delay(2, 3)

        # 尝试点击登录按钮，弹出二维码登录框
        login_selectors = [
            'text=登录',
            '[class*="login"]',
            'button:has-text("登录")',
            'div:has-text("登录")',
        ]
        for selector in login_selectors:
            try:
                el = self._page.locator(selector).first
                if await el.is_visible(timeout=2000):
                    await el.click()
                    await _human_delay(1, 2)
                    break
            except Exception:
                continue

        self._login_event.clear()

        async def handle_response(response: Response):
            try:
                url = response.url
                if "/passport/web/user/info/" in url and response.status == 200:
                    body = await response.json()
                    if body.get("status_code") == 0:
                        self._login_event.set()
            except Exception:
                pass

        self._page.on("response", handle_response)
        asyncio.create_task(self._poll_login())

    async def _poll_login(self):
        """轮询检查登录态（只检查 cookie，不跳转页面）"""
        for _ in range(180):  # 最多 15 分钟
            if await self.is_logged_in():
                await _human_delay(1, 2)  # 等待 cookie 写入完整
                await self.save_login_state()
                self._login_event.set()
                return
            await asyncio.sleep(5)

    async def wait_for_login(self, timeout: int = 900) -> bool:
        """等待用户完成扫码登录"""
        try:
            await asyncio.wait_for(self._login_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def get_following_list(self, max_count: int = DEFAULT_MAX_FOLLOWING) -> list:
        """获取"我的关注"列表

        流程（2026-09 实测验证）：
        1. 打开自己主页的关注 tab（/user/self?showTab=following）
        2. 点击"关注"tab 触发列表 API（不点击不会加载）
        3. 拦截 /aweme/v1/web/user/following/list/ 响应提取数据
        4. 滚动分页拉取更多，直到无新数据或达到上限

        安全措施：
        - 拉取上限（默认 200，硬上限 500）
        - 每次滚动间随机延迟 2.5~5 秒
        - 按 sec_uid 去重，重复响应不会重复计入
        """
        max_count = min(max_count, MAX_FOLLOWING_LIMIT)

        await self.start(headless=False)

        following_data: dict = {}  # sec_uid -> item
        data_event = asyncio.Event()

        async def handle_response(response: Response):
            if "/aweme/v1/web/user/following/list/" not in response.url:
                return
            try:
                if response.status != 200:
                    return
                body = await response.json()
                followings = body.get("followings") or body.get("data", {}).get("followings") or []
                for item in followings:
                    sec_uid = item.get("sec_uid")
                    if not sec_uid or sec_uid in following_data:
                        continue
                    # 在播信息：room_id 可能直接在 item 上，也可能嵌在 room 对象里
                    room_id = (
                        item.get("room_id")
                        or (item.get("room") or {}).get("id")
                        or item.get("live_room_id")
                    )
                    following_data[sec_uid] = {
                        "sec_uid": sec_uid,
                        "nickname": item.get("nickname"),
                        "avatar": (item.get("avatar_thumb") or {}).get("url_list", [None])[0],
                        "room_id": str(room_id) if room_id else None,
                        "is_live": bool(room_id),
                        "room_url": f"{DOUYIN_HOME}/user/{sec_uid}",
                    }
                if following_data:
                    data_event.set()
            except Exception:
                pass

        self._page.on("response", handle_response)
        try:
            await self._page.goto(DOUYIN_SELF_FOLLOWING, wait_until="domcontentloaded", timeout=30000)
            await _human_delay(3, 5)

            # 点击"关注"tab 触发列表 API（实测 showTab 参数不会自动加载列表）
            for selector in ['div[data-tab="following"]', '[class*="tab"]:has-text("关注")', 'text=关注']:
                try:
                    el = self._page.locator(selector).first
                    if await el.is_visible(timeout=2500):
                        await el.click()
                        await _human_delay(2, 4)
                        break
                except Exception:
                    continue

            # 等待首批数据
            try:
                await asyncio.wait_for(data_event.wait(), timeout=15)
            except asyncio.TimeoutError:
                pass

            # 滚动分页拉全量：连续 3 轮无新数据则停止
            idle_rounds = 0
            while len(following_data) < max_count and idle_rounds < 3:
                before = len(following_data)
                await self._page.mouse.wheel(0, random.randint(600, 1000))
                await _human_delay(2.5, 5)
                if len(following_data) == before:
                    idle_rounds += 1
                else:
                    idle_rounds = 0
        finally:
            try:
                self._page.remove_listener("response", handle_response)
            except Exception:
                pass

        # 记录同步时间，启动冷却
        _set_last_sync_time()
        return list(following_data.values())[:max_count]

    async def start_live_capture(self, room_id: str, on_danmaku, sec_uid: str = None) -> bool:
        """打开直播间页面并开始采集实时弹幕

        采集方式：DOM 轮询（每 2.5~4 秒读取一次聊天区新消息），
        每条新消息回调 on_danmaku(user, content)（异步函数）。

        进入直播间策略：
        1. 优先用 room_id 拼 live.douyin.com/{room_id}（关注列表 API 返回的
           room_id 是内部 ID，多数情况下不是网页房间号，会渲染成落地页）
        2. 失败则回退：访问主播主页，从"直播中"链接提取真实的网页房间号
        """
        if self._capturing:
            return True  # 已在采集中
        await self.start(headless=False)

        page = await self._context.new_page()
        entered = False

        if room_id:
            await page.goto(f"https://live.douyin.com/{room_id}", wait_until="domcontentloaded", timeout=30000)
            await _human_delay(4, 6)
            entered = await self._room_ready(page)

        if not entered and sec_uid:
            web_rid = await self._find_live_web_rid(page, sec_uid)
            if not web_rid:
                await page.close()
                raise RuntimeError("未能进入直播间：可能已下播或页面受限")
            await page.goto(f"https://live.douyin.com/{web_rid}", wait_until="domcontentloaded", timeout=30000)
            await _human_delay(4, 6)
            entered = await self._room_ready(page)

        if not entered:
            await page.close()
            raise RuntimeError("直播间页面加载异常（可能已下播、触发验证或页面变更），请稍后重试")

        # 检测是否触发验证/拦截
        title = await page.title()
        if "验证" in title or "captcha" in page.url.lower():
            await page.close()
            raise RuntimeError("直播间页面触发验证码，请在弹出的浏览器中手动完成验证后重试")

        self._capture_page = page
        self._capturing = True
        self._capture_task = asyncio.create_task(self._capture_loop(on_danmaku))
        return True

    async def _room_ready(self, page: Page) -> bool:
        """检测直播间聊天区是否已渲染"""
        try:
            await page.wait_for_selector('[class*="webcast-chatroom"]', timeout=8000)
            return True
        except Exception:
            return False

    async def _find_live_web_rid(self, page: Page, sec_uid: str) -> Optional[str]:
        """访问主播主页，从"直播中"入口提取真实的网页直播间号

        注意：页面第一个 live 链接可能是导航栏的 live.douyin.com/?from_nav=1，
        必须遍历所有链接，找带数字房间号的那一个。
        """
        try:
            await page.goto(f"{DOUYIN_HOME}/user/{sec_uid}", wait_until="domcontentloaded", timeout=30000)
            await _human_delay(3, 5)
            await page.wait_for_selector('a[href*="live.douyin.com"]', timeout=10000)
            hrefs = await page.eval_on_selector_all(
                'a[href*="live.douyin.com"]', "els => els.map(e => e.href)"
            )
            for h in hrefs:
                m = re.search(r"live\.douyin\.com/(\d{6,})", h or "")
                if m:
                    return m.group(1)
            return None
        except Exception:
            return None

    async def _capture_loop(self, on_danmaku):
        """弹幕采集循环：轮询 DOM 提取新消息"""
        # 抖音直播聊天区消息项（实测类名 webcast-chatroom___item，系统提示含 room-message）
        extract_js = """
            () => {
                const nodes = document.querySelectorAll('[class*="webcast-chatroom___item"]');
                const out = [];
                for (const n of nodes) {
                    if (n.querySelector('[class*="room-message"]')) continue;  // 跳过系统提示
                    const t = (n.innerText || '').trim();
                    if (t) out.push(t);
                }
                return out;
            }
        """
        # 去重集合要有上限：长场次弹幕上万条，无上限会持续吃内存。
        # 用 OrderedDict 当有界 FIFO 集合，淘汰最旧的记录。
        seen: "OrderedDict[str, None]" = OrderedDict()
        while self._capturing and self._capture_page:
            if self._capture_page.is_closed():
                # 直播间页面被手动关闭，结束采集
                self._capturing = False
                self._capture_page = None
                break
            try:
                texts = await self._capture_page.evaluate(extract_js)
                new_msgs = []
                for t in texts:
                    t = t.strip()
                    if not t or t in seen:
                        continue
                    seen[t] = None
                    if len(seen) > SEEN_LIMIT:
                        seen.popitem(last=False)
                    if "：" in t:
                        user, content = t.split("：", 1)
                    elif ":" in t:
                        user, content = t.split(":", 1)
                    else:
                        user, content = "观众", t
                    if content.strip():
                        new_msgs.append((user.strip() or "观众", content.strip()))
                for user, content in new_msgs:
                    if not self._capturing:
                        break
                    try:
                        await on_danmaku(user, content)
                    except Exception as e:
                        print(f"⚠️ 弹幕处理失败: {e}")
            except Exception:
                # 页面被手动关闭或跳转，稍后重试
                await asyncio.sleep(3)
                continue
            await asyncio.sleep(random.uniform(2.5, 4.0))

    async def stop_live_capture(self):
        """停止弹幕采集并关闭直播间页面"""
        self._capturing = False
        if self._capture_task:
            self._capture_task.cancel()
            self._capture_task = None
        if self._capture_page:
            try:
                await self._capture_page.close()
            except Exception:
                pass
            self._capture_page = None

    async def close(self):
        """关闭浏览器"""
        await self.stop_live_capture()
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._page = None


# 全局单例
douyin_client = DouyinClient()
