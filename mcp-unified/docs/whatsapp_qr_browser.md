# WhatsApp QR Browser Helper

Use `integrations/whatsapp/open_waha_qr.py` to open the WAHA page in a browser and capture the current screen.

## Purpose

- inspect whether WAHA is asking for login or showing QR
- save a screenshot for later review
- avoid guessing when the session is not reachable from a sandboxed runtime

## Example

```bash
cd /home/aseps/MCP/mcp-unified
python3 integrations/whatsapp/open_waha_qr.py
```

If you want to save to a custom file:

```bash
python3 integrations/whatsapp/open_waha_qr.py --output /tmp/waha_qr.png
```

If you want a headless capture:

```bash
python3 integrations/whatsapp/open_waha_qr.py --headless
```

## Notes

- The default URL is taken from `WHATSAPP_API_URL`.
- The helper is meant to run on the host machine, not in a sandboxed runtime that cannot access `localhost:3000`.
