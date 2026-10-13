import os, re, json, html, requests

UID     = os.environ["WEIBO_UID"]          # 博主 UID（在仓库 Secrets 里配）
COOKIE  = os.environ["WEIBO_COOKIE"]       # 你自己的微博 Cookie（在仓库 Secrets 里配）
WEBHOOK = os.environ["FEISHU_WEBHOOK"]     # 飞书群机器人地址（在仓库 Secrets 里配）
STATE   = "state.json"                      # 记录“已推送过的最新微博”，防止重复

API = f"https://m.weibo.cn/api/container/getIndex?type=uid&value={UID}&containerid=107603{UID}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Cookie": COOKIE,
    "Referer": f"https://m.weibo.cn/u/{UID}",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
}

r = requests.get(API, headers=HEADERS, timeout=20)
try:
    data = r.json()
except Exception:
    print("抓取失败，返回：", r.status_code, r.text[:200])
    raise SystemExit(1)

cards = data.get("data", {}).get("cards", []) or []
posts = []
for c in cards:
    mb = c.get("mblog")
    if not mb:
        continue
    text = re.sub(r"<[^>]+>", "", mb.get("text", ""))
    text = html.unescape(text).strip()
    posts.append({"id": int(mb["id"]), "text": text, "url": f"https://m.weibo.cn/detail/{mb['id']}"})

state = {}
if os.path.exists(STATE):
    state = json.load(open(STATE))
last = int(state.get(str(UID), 0))

new = sorted([p for p in posts if p["id"] > last], key=lambda x: x["id"])
for p in new:
    tip = p["text"][:180] if p["text"] else "[图片/视频/转发]"
    body = f"更新｜{tip}\n{p['url']}"
    resp = requests.post(WEBHOOK, json={"msg_type": "text", "content": {"text": body}}, timeout=10)
    print("推送", p["id"], resp.status_code)

if posts:
    state[str(UID)] = max(p["id"] for p in posts)
    json.dump(state, open(STATE, "w"))

print("本次新微博：", len(new))
