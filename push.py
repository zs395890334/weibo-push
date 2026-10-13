import os, re, json, html, requests

# 支持多个博主：WEIBO_UID 里用英文逗号分隔，例如  1357064103,1669879400
UIDS    = [u.strip() for u in os.environ["WEIBO_UID"].replace("，", ",").split(",") if u.strip()]
COOKIE  = os.environ["WEIBO_COOKIE"]     # 你自己的微博 Cookie
WEBHOOK = os.environ["FEISHU_WEBHOOK"]   # 飞书群机器人地址（同一个群）
STATE   = "state.json"                    # 记录每个博主已推送过的最新微博

def build_headers(uid):
    return {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Cookie": COOKIE,
        "Referer": f"https://m.weibo.cn/u/{uid}",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
    }

state = {}
if os.path.exists(STATE):
    try:
        state = json.load(open(STATE))
    except Exception:
        state = {}

total = 0
for uid in UIDS:
    api = f"https://m.weibo.cn/api/container/getIndex?type=uid&value={uid}&containerid=107603{uid}"
    try:
        r = requests.get(api, headers=build_headers(uid), timeout=20)
        data = r.json()
    except Exception as e:
        print(uid, "抓取失败：", e)
        continue

    cards = data.get("data", {}).get("cards", []) or []
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
        continue

    last = int(state.get(str(uid), 0))
    new = sorted([p for p in posts if p["id"] > last], key=lambda x: x["id"])
    who = name or uid
    for p in new:
        tip = p["text"][:180] if p["text"] else "[图片/视频/转发]"
        body = f"更新｜{who}：{tip}\nhttps://m.weibo.cn/detail/{p['id']}"
        resp = requests.post(WEBHOOK, json={"msg_type": "text", "content": {"text": body}}, timeout=10)
        print("推送", who, p["id"], resp.status_code)
        total += 1

    state[str(uid)] = max(p["id"] for p in posts)
    json.dump(state, open(STATE, "w"))

print("本次新微博合计：", total)
