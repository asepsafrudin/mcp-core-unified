# Google Drive Integration for MCP Unified System

Integrasi Google Drive untuk MCP Unified Agent System menggunakan service account authentication.

## Setup

### 1. Credentials (Sudah Terkonfigurasi)

Credential sudah dikonfigurasi di `.env`:

```bash
GDRIVE_CREDENTIALS_PATH=/home/aseps/MCP/OneDrive_PUU/PUU_2026/MCP/credential/gdrive
GDRIVE_SERVICE_ACCOUNT_FILE=oval-fort-461712-c0-78646012bddb.json
GDRIVE_OAUTH_CLIENT_FILE=client_secret_*.apps.googleusercontent.com.json
```

### 2. Dependencies

Pastikan Google API client terinstall:

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

Atau tambahkan ke `requirements.txt`:

```
google-auth>=2.22.0
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.1.1
google-api-python-client>=2.95.0
```

### 3. Service Account Setup

Service account sudah dikonfigurasi. Untuk akses ke folder personal:

1. Buka file `oval-fort-461712-c0-78646012bddb.json`
2. Catat `client_email` (format: `...@oval-fort-461712-c0.iam.gserviceaccount.com`)
3. Share folder Google Drive Anda dengan email tersebut
4. Berikan permission "Editor" atau "Viewer" sesuai kebutuhan

## MCP Tools

### `gdrive_list_files`
List files dan folders dalam sebuah folder.

**Parameters:**
- `folder_id` (string, optional): Folder ID, default "root"
- `include_trashed` (boolean, optional): Include trashed files
- `page_size` (integer, optional): Max results, default 100

**Example:**
```json
{
  "folder_id": "root",
  "page_size": 50
}
```

### `gdrive_search_files`
Cari files berdasarkan nama.

**Parameters:**
- `query` (string, required): Search query
- `include_trashed` (boolean, optional)
- `page_size` (integer, optional)

**Example:**
```json
{
  "query": "laporan",
  "page_size": 20
}
```

### `gdrive_get_file_info`
Dapatkan informasi detail file/folder.

**Parameters:**
- `file_id` (string, required): File ID

### `gdrive_create_folder`
Buat folder baru.

**Parameters:**
- `name` (string, required): Folder name
- `parent_id` (string, optional): Parent folder ID, default "root"

### `gdrive_upload_file`
Upload file ke Google Drive.

**Parameters:**
- `file_path` (string, required): Local file path
- `parent_id` (string, optional): Destination folder ID
- `name` (string, optional): Custom filename

### `gdrive_download_file`
Download file dari Google Drive.

**Parameters:**
- `file_id` (string, required): File ID
- `destination_path` (string, required): Local save path

**Note:** Google Docs/Sheets akan di-export ke format Office (docx/xlsx)

### `gdrive_delete_file`
Hapus file atau folder.

**Parameters:**
- `file_id` (string, required): File ID
- `permanently` (boolean, optional): Delete permanently (bypass trash)

## Usage Examples

### Python Direct Usage

```python
from integrations.gdrive import get_gdrive_client

# Get client (auto-connect)
client = get_gdrive_client()

# List files in root
files = client.list_files(folder_id="root")
for f in files:
    print(f"{f.name} - {'Folder' if f.is_folder else 'File'}")

# Create folder
folder = client.create_folder("New Folder", parent_id="root")
print(f"Created: {folder.id}")

# Upload file
uploaded = client.upload_file(
    file_path="/path/to/file.pdf",
    parent_id=folder.id,
    name="Renamed.pdf"
)

# Download file
client.download_file(
    file_id="abc123",
    destination_path="/path/to/save.pdf"
)
```

### MCP Tool Usage

Tools dapat dipanggil melalui MCP protocol setelah diregister di `mcp_server.py`.

## Folder IDs

- **root**: My Drive root
- **Folder ID**: Didapat dari URL Google Drive
  - Contoh: `https://drive.google.com/drive/folders/1ABC123xyz` → Folder ID: `1ABC123xyz`

## Security Notes

1. Service account file (`oval-fort-*.json`) harus tetap di lokasi yang aman
2. Jangan commit credential files ke git
3. Service account hanya bisa akses folder yang di-share ke email-nya
4. Untuk production, pertimbangkan menggunakan key rotation

## Troubleshooting

### "Credentials file not found"
- Pastikan path di `.env` benar
- Verifikasi file ada di `OneDrive_PUU/PUU_2026/MCP/credential/gdrive/`

### "Insufficient permissions"
- Service account email belum di-share ke folder
- Check `client_email` di service account JSON
- Share folder dengan email tersebut di Google Drive UI

### "File not found"
- File ID mungkin salah atau file dihapus
- Cek dengan `gdrive_search_files` untuk mencari file

## File Structure

```
integrations/gdrive/
├── __init__.py      # Module exports
├── client.py        # GDriveClient class
├── tools.py         # MCP tool functions
└── README.md        # This file
```
