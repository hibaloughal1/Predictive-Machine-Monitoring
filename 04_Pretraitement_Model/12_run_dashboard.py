import argparse
import time
import urllib.request
import webbrowser
from threading import Thread
import uvicorn


def open_when_ready(url: str) -> None:
    """Open the browser only after the API is accepting connections."""
    health_url = f"{url}/api/health"
    for _ in range(120):
        try:
            with urllib.request.urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:
            time.sleep(0.25)
    print(f"Dashboard startup timed out. Open {url} after checking the error above.")


def main():
    p=argparse.ArgumentParser();p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8765);p.add_argument("--no-browser",action="store_true");a=p.parse_args()
    url=f"http://{a.host}:{a.port}"
    print(f"Starting AdoptAI at {url}")
    print("Keep this window open. Press Ctrl+C to stop the dashboard.")
    if not a.no_browser:
        Thread(target=open_when_ready,args=(url,),daemon=True).start()
    uvicorn.run("dashboard.app:app",host=a.host,port=a.port)
if __name__=="__main__":main()
