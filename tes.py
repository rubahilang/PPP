import requests
import json

url = "https://api.serphouse.com/serp/live"
payload = {
    "data": {
        "q": "sekar4d",
        "domain": "google.com",
        "loc": "Indonesia",
        "lang": "en",
        "device": "mobile",
        "serp_type": "web",
        "page": "1",
        "verbatim": "0"
    }
}
headers = {
    'accept': "application/json",
    'content-type': "application/json",
    'authorization': "Bearer RO7H9zb9tea0RTgTloYBqNMqsT7qGM5ygQo3biCwGNPT4ubUMoBbPpcwla63"
}

response = requests.post(url, json=payload, headers=headers)

if response.status_code == 200:
    data = response.json()
    # Simpan JSON ke rank.json
    with open('./rank.json', 'w') as file:
        json.dump(data, file, indent=4)
    print("Data berhasil disimpan ke ./rank.json")

    # Baca file rank.json
    with open('./rank.json', 'r') as file:
        rank_data = json.load(file)
        # Akses bagian "results" -> "results" -> "organic"
        organic_results = rank_data.get("results", {}).get("results", {}).get("organic", [])
        if organic_results:
            print("\n### Organic Results (position, site_title, link) ###")
            for item in organic_results:
                position = item.get("position")
                site_title = item.get("site_title")
                link = item.get("link")
                print(f"Position: {position}")
                print(f"Site Title: {site_title}")
                print(f"Link: {link}")
                print("-" * 50)
        else:
            print("Bagian 'organic' tidak ditemukan dalam 'results'.")
else:
    print(f"Failed to fetch data. Status Code: {response.status_code}")
    print(f"Response: {response.text}")
