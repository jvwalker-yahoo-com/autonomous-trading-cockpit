"""
Autonomous Trading Cockpit - Gradio SDK Entrypoint for Hugging Face Spaces.
Mounts the FastAPI trading engine and HTML5 dashboard directly inside a Gradio Space.
"""
import os
from pathlib import Path
from backend.server import app as fastapi_app
from fastapi.responses import FileResponse

try:
    import gradio as gr

    FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

    @fastapi_app.get("/cockpit-frame")
    def serve_cockpit_frame():
        return FileResponse(FRONTEND_DIR / "index.html")

    with gr.Blocks(title="Autonomous Trading Cockpit", theme=gr.themes.Default()) as demo:
        gr.Markdown("## ⚡ Autonomous Stock Trading Cockpit")
        gr.HTML('''
        <div style="width: 100%; height: 920px; border: 1px solid #333; border-radius: 8px; overflow: hidden; background: #0b0e14;">
            <iframe src="/cockpit-frame" style="width: 100%; height: 100%; border: none;"></iframe>
        </div>
        ''')

    # Mount Gradio onto FastAPI
    app = gr.mount_gradio_app(fastapi_app, demo, path="/")

    if __name__ == "__main__":
        port = int(os.environ.get("PORT", 7860))
        demo.launch(server_name="0.0.0.0", server_port=port)
except Exception as e:
    import uvicorn
    if __name__ == "__main__":
        port = int(os.environ.get("PORT", 7860))
        uvicorn.run("backend.server:app", host="0.0.0.0", port=port)
