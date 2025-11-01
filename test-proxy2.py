import requests

proxy = {
    "http": "http://7h8o8te9k6:LuDCEq3Rv7@85.185.120.203:42073",
    "https": "http://7h8o8te9k6:LuDCEq3Rv7@85.185.120.203:42073"
}

r = requests.get("https://rrk.ir/", proxies=proxy, timeout=30)
print(r.status_code)
print(r.text[:500])
