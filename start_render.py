# start_render.py — Production runner for Render
# Runs both the FastAPI backend and Streamlit UI in a single Render Web Service
import os
import sys
import time
import signal
import subprocess
import urllib.request

def main():
    os.makedirs("./data/chroma_db", exist_ok=True)

    # 1. Start FastAPI backend on internal port 8000
    backend_port = 8000
    print(f"[*] Starting FastAPI backend on internal port {backend_port}...")
    backend_env = os.environ.copy()
    backend_env["PORT"] = str(backend_port)
    backend_proc = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "api:app",
        "--host", "127.0.0.1",
        "--port", str(backend_port)
    ], env=backend_env)

    # 2. Wait until backend reports healthy
    health_url = f"http://127.0.0.1:{backend_port}/health"
    print("[*] Waiting for backend to initialize...")
    ready = False
    for attempt in range(40):
        try:
            with urllib.request.urlopen(health_url, timeout=2) as resp:
                if resp.status == 200:
                    ready = True
                    print("[+] Backend is ready and healthy!")
                    break
        except Exception:
            pass
        time.sleep(1)

    if not ready:
        print("[!] Backend did not report ready in 40s. Starting frontend anyway...")

    # 3. Start Streamlit UI on Render's assigned public $PORT
    public_port = os.environ.get("PORT", "8501")
    print(f"[*] Starting Streamlit UI on public port {public_port}...")

    frontend_env = os.environ.copy()
    frontend_env["BACKEND_API_URL"] = f"http://127.0.0.1:{backend_port}"

    frontend_cmd = [
        sys.executable, "-m", "streamlit", "run", "ui/app.py",
        "--server.port", str(public_port),
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false"
    ]

    frontend_proc = subprocess.Popen(frontend_cmd, env=frontend_env)

    # Clean shutdown handler
    def cleanup(signum, frame):
        print("\n[*] Received shutdown signal, terminating servers...")
        try:
            frontend_proc.terminate()
        except Exception:
            pass
        try:
            backend_proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    # Keep script alive while frontend is running
    frontend_proc.wait()
    try:
        backend_proc.terminate()
    except Exception:
        pass

if __name__ == "__main__":
    main()

