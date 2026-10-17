import os, re, json, html, time, requests

# 支持多个博主：WEIBO_UID 里用英文逗号分隔，例如  1357064103,1669879400
UIDS    = [u.strip() for u in os.environ["WEIBO_UID"].replace("，", ",").split(",") if u.strip()]
COOKIE  = os.environ["WEIBO_COOKIE"]     # 你自己的微博 Cookie
WEBHOOK = os.environ["FEISHU_WEBHOOK"]   # 飞书群机器人地址
STATE   = "state.json"                    # 记录每个博主已推送过的最新微博
ALERT_GAP = 6 * 3600                      # 同一故障最多每 6 小时告警一次（防刷屏）

def build_headers(uid):
    return {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Cookie": COOKIE,
        "Referer": f"https://m.weibo.cn/u/{uid}",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
    }

def send(text):
    """发到飞书，失败不影响主流程"""
    try:
        r = requests.post(WEBHOOK, json={"msg_type": "text", "content": {"text": text}}, timeout=10)
        print("飞书 ->", r.status_code)
        return r.status_code
    except Exception as e:
        print("飞书发送失败：", e)
        return -1

def fetch(uid, retries=3):
    """带重试的抓取；返回 cards 列表，彻底失败返回 None"""
    api = f"https://m.weibo.cn/api/container/getIndex?type=uid&value={uid}&containerid=107603{uid}"
    for i in range(retries):
        try:
            r = requests.get(api, headers=build_headers(uid), timeout=20)
            data = r.json()
            return data.get("data", {}).get("cards", []) or []
        except Exception as e:
            print(f"{uid} 第{i+1}次抓取异常：{e}")
            time.sleep(2 + i * 3)   # 退避：2s / 5s / 8s
    return None

# ---- 读取进度 ----
state = {}
if os.path.exists(STATE):
    try:
        state = json.load(open(STATE))
    except Exception:
        state = {}

total = 0
fail_uids = []

for uid in UIDS:
    cards = fetch(uid)
    if cards is None:
        print(uid, "抓取失败（网络/接口异常）")
        fail_uids.append(uid)
        continue

    posts, name = [], ""
    for c in cards:
        mb = c.get("mblog")
        if not mb:
            continue
        if not name:
            name = (mb.get("user") or {}).get("screen_name", "") or ""
        text = html.unescape(re.sub(r"<[^>]+>", "", mb.get("text", ""))).strip()
        posts.append({"id": int(mb["id"]), "text": text})

    if not posts:
        print(uid, "没有抓到微博（Cookie 可能过期）")
        fail_uids.append(uid)
        continue

    last = int(state.get(str(uid), 0))
    new = sorted([p for p in posts if p["id"] > last], key=lambda x: x["id"])
    who = name or uid
    for p in new:
        tip = p["text"][:180] if p["text"] else "[图片/视频/转发]"
        body = f"更新｜{who}：{tip}\nhttps://m.weibo.cn/detail/{p['id']}"
        send(body)
        print("推送", who, p["id"])
        total += 1

    state[str(uid)] = max(p["id"] for p in posts)

# ---- 抓取失败 → 飞书告警（6 小时冷却，防刷屏）----
if fail_uids:
    now = int(time.time())
    last_alert = int(state.get("_alert_ts", 0))
    if now - last_alert > ALERT_GAP:
        send("⚠️ 微博抓取异常：{} / {} 个博主抓不到。\nUID：{}\n多半是 Cookie 失效，请更新 GitHub Secret「WEIBO_COOKIE」。".format(
            len(fail_uids), len(UIDS), ", ".join(fail_uids)))
        state["_alert_ts"] = now
        print("已发送失败告警")
    else:
        print("告警冷却中，跳过（距上次告警不足6小时）")

json.dump(state, open(STATE, "w"))
print("本次新微博合计：", total)
