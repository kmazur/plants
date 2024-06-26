from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import os
import mimetypes

app = FastAPI()
UPLOAD_FOLDER = 'uploads'
SECRET_AUTH_CODE = os.getenv('SECRET_AUTH_CODE')

# Create upload directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), auth_code: str = None):
    if auth_code != SECRET_AUTH_CODE:
        raise HTTPException(status_code=401, detail="Unauthorized")

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    return {"filename": file.filename}

@app.get("/download/{filename}")
async def download_file(filename: str, auth_code: str = None):
    if auth_code != SECRET_AUTH_CODE:
        raise HTTPException(status_code=401, detail="Unauthorized")

    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    return FileResponse(file_path, filename=filename, media_type=mime_type)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
