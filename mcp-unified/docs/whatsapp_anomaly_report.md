# WhatsApp Anomaly Report Format

Use this format when one finding should be sent as one WhatsApp message and archived in log history.

## Format

```text
Assalamu’alaikum {recipient_name},

Saya dari MCP Unified ingin melaporkan temuan anomali data yang perlu dicek lebih lanjut.

Temuan:
{finding_title}

Ringkasan:
{finding_summary}

Kunci Data: {record_key}
Sumber: {source_label}
Referensi: {source_ref}
Dampak: {impact}
Rekomendasi: {recommendation}

Jika berkenan, mohon arahan apakah data ini perlu dikoreksi di sumber atau cukup difilter di tampilan.

Terima kasih.
Wassalamu’alaikum.
```

## Logging

Every WhatsApp send routed through `NotificationService.send_whatsapp(...)` now appends a JSONL record to:

`/home/aseps/MCP/logs/whatsapp_anomaly_reports.jsonl`

Each record includes:
- timestamp
- channel
- session
- recipient
- chat_id
- message
- status
- optional metadata

## Intended Usage

- One anomaly = one message.
- Keep the message focused on a single finding.
- Keep the raw evidence in `record_key`, `source_ref`, or `metadata`.
- If another anomaly is found, send a new message instead of merging findings.
