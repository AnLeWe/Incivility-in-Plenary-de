# Connecting VS Code to a Colab runtime

Exposes a live Colab kernel as a remote Jupyter server so VS Code's Jupyter extension can
connect to it directly, instead of working in the Colab browser UI. Fallback/GPU tier per
`docs/superpowers/specs/2026-07-07-repo-publishing-infra-design.md` Section D — not the
default dev environment, use when the M5 MacBook Pro isn't enough (e.g. CUDA-only libraries).

This is unofficial and a bit fragile: the tunnel dies whenever the Colab runtime resets, so
the Colab-side cell below has to be re-run at the start of every session.

## Prerequisites (one-time)

- A free ngrok account and authtoken: <https://dashboard.ngrok.com/get-started/your-authtoken>
- VS Code's Jupyter extension (`ms-toolsai.jupyter`) installed locally.

## Every Colab session

1. Open/create the notebook in Colab, then run this cell first:

   ```python
   !pip install -q jupyter_http_over_ws pyngrok
   !jupyter serverextension enable --py jupyter_http_over_ws

   from pyngrok import ngrok
   import time

   NGROK_AUTHTOKEN = "paste-your-token-here"
   ngrok.set_auth_token(NGROK_AUTHTOKEN)

   get_ipython().system_raw(
       'jupyter notebook --NotebookApp.allow_origin="https://colab.research.google.com" '
       '--port=8888 --NotebookApp.port_retries=0 --no-browser &'
   )
   time.sleep(5)
   print(ngrok.connect(8888, bind_tls=True))
   !jupyter notebook list   # copy the token from here
   ```

2. Combine the printed ngrok URL and token into `https://<ngrok-url>/?token=<token>`.

3. In VS Code: Command Palette → "Jupyter: Specify Jupyter server for connections" (or, from
   a notebook, "Select Kernel" → "Existing Jupyter Server") → paste that URL.

4. Pick the remote kernel from the connected server. Code now runs on Colab's hardware;
   `DATA_ROOT` access for a headless environment like this still needs `rclone`/`gdown`
   rather than the Drive desktop app (see the design spec, Section D).

## Caveats

- Free ngrok URLs rotate every session — redo steps 1–2 each time.
- Colab free-tier usage limits/timeouts still apply; this doesn't get around those.
- If this breaks (Google/ngrok/jupyter_http_over_ws changes), just work in the Colab browser
  UI directly instead of debugging the tunnel.
