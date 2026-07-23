"""Deploy functions that run on your Mac without your laptop — Modal's `modal deploy`.

    herds deploy examples/deploy_app.py

After deploy:
  • `nightly_report` fires on your Mac every day at 03:00 (cron), no client needed.
  • `build` can be triggered any time over the API:
      curl -X POST $HERDS_URL/v1/apps/nightly/functions/build \
           -H 'Content-Type: application/json' -d '{"args":["release"]}'
  • `status` is a web endpoint — deploy gives it a public URL (shown in the dashboard).

Functions must be module-level (their source is shipped to the Mac).
"""

import herds

app = herds.App("nightly")


@app.function(schedule="0 3 * * *")
def nightly_report() -> dict:
    import platform
    import datetime
    return {"host": platform.node(), "at": datetime.datetime.now().isoformat()}


@app.function()
def build(target: str) -> str:
    return f"built {target}"


@app.web_endpoint(port=8077)
def status():
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    socketserver.TCPServer(("", 8077), Handler).serve_forever()


if __name__ == "__main__":
    # `herds deploy` introspects the app above and doesn't run this block.
    # Running the file directly deploys it too:
    herds.configure(url="https://you.herds.run", token="hx_...")   # from `herds host`
    app.deploy()
    print("deployed:", app.function_names())
