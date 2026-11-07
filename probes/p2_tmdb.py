"""Probe P2 (card #301): TMDB key from Keychain works. Never prints the key."""
import json, subprocess, sys, urllib.parse, urllib.request

def tmdb_key() -> str:
    return subprocess.run(["security", "find-generic-password", "-s", "curator-tmdb", "-w"],
                          capture_output=True, text=True, check=True).stdout.strip()

def get(path: str, **params) -> dict:
    params["api_key"] = tmdb_key()
    url = f"https://api.themoviedb.org/3{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)

if __name__ == "__main__":
    m = get("/search/movie", query="Se7en", year=1995)["results"][0]
    print("movie:", m["id"], m["title"], m["release_date"])
    t = get("/search/tv", query="Severance")["results"][0]
    ext = get(f"/tv/{t['id']}/external_ids")
    print("tv:", t["id"], t["name"], "imdb", ext.get("imdb_id"), "tvdb", ext.get("tvdb_id"))
    sys.exit(0)
